"""Simple script to download Sentinel satellite imagery using free alternatives to SentinelHub."""

import os
from datetime import date
from typing import Dict, Any, List, Optional

import boto3
from botocore import UNSIGNED
from botocore.config import Config
import pandas as pd
from sentinelsat import SentinelAPI, geojson_to_wkt

import config


def setup_copernicus_api() -> SentinelAPI:
    """
    Set up connection to Copernicus Open Access Hub API.
    
    Returns:
        SentinelAPI: Configured API client for querying Sentinel products.
        
    Raises:
        ValueError: If credentials are not configured in config.py
    """
    if not config.COPERNICUS_USERNAME or not config.COPERNICUS_PASSWORD:
        raise ValueError(
            "Please set COPERNICUS_USERNAME and COPERNICUS_PASSWORD in config.py. "
            "Register at https://scihub.copernicus.eu/dhus/"
        )
    
    api = SentinelAPI(
        config.COPERNICUS_USERNAME, 
        config.COPERNICUS_PASSWORD, 
        config.COPERNICUS_API_URL
    )
    return api


def create_area_of_interest(coordinates: Dict[str, Any]) -> str:
    """
    Convert GeoJSON polygon coordinates to WKT format for Sentinel API queries.
    
    Args:
        coordinates: GeoJSON polygon coordinates dict with 'type' and 'coordinates' keys.
        
    Returns:
        str: Well-Known Text (WKT) representation of the polygon.
    """
    return geojson_to_wkt(coordinates)


def query_sentinel_products(
    api: SentinelAPI,
    footprint: str,
    start_date: str = "20250101",
    end_date: Optional[str] = None,
    platform: str = config.DEFAULT_PLATFORM,
    product_type: str = config.DEFAULT_PRODUCT_TYPE,
    max_cloud_cover: int = config.DEFAULT_MAX_CLOUD_COVER
) -> pd.DataFrame:
    """
    Query Sentinel products from Copernicus Open Access Hub.
    
    Args:
        api: Configured SentinelAPI client.
        footprint: WKT representation of the area of interest.
        start_date: Start date in YYYYMMDD format.
        end_date: End date in YYYYMMDD format. If None, uses today's date.
        platform: Sentinel platform name (e.g., 'Sentinel-2').
        product_type: Product type (e.g., 'S2MSI2A' for Level-2A).
        max_cloud_cover: Maximum cloud cover percentage (0-100).
        
    Returns:
        pd.DataFrame: DataFrame containing query results with product metadata.
        
    Raises:
        ValueError: If no products are found for the specified criteria.
    """
    if end_date is None:
        end_date = date.today()
    
    print(f"Querying {platform} products from {start_date} to {end_date}")
    print(f"Product type: {product_type}, Max cloud cover: {max_cloud_cover}%")
    
    products = api.query(
        footprint,
        date=(start_date, end_date),
        platformname=platform,
        producttype=product_type,
        cloudcoverpercentage=(0, max_cloud_cover)
    )
    
    products_df = api.to_dataframe(products)
    
    if products_df.empty:
        raise ValueError(
            f"No products found for the specified criteria. "
            f"Try expanding the date range or increasing cloud cover threshold."
        )
    
    print(f"Found {len(products_df)} products")
    return products_df


def select_best_product(products_df: pd.DataFrame) -> tuple[str, str]:
    """
    Select the best product from query results based on cloud cover.
    
    Args:
        products_df: DataFrame containing product metadata.
        
    Returns:
        tuple[str, str]: Product UUID and title of the selected product.
    """
    # Sort by cloud cover (ascending) and select the first product
    best_product = products_df.sort_values('cloudcoverpercentage').iloc[0]
    
    product_id = best_product['uuid']
    product_title = best_product['title']
    cloud_cover = best_product['cloudcoverpercentage']
    
    print(f"Selected product: {product_title}")
    print(f"Cloud cover: {cloud_cover:.1f}%")
    
    return product_id, product_title


def setup_aws_s3_client() -> boto3.client:
    """
    Set up AWS S3 client for accessing public Sentinel data.
    
    Returns:
        boto3.client: Configured S3 client with unsigned requests.
    """
    return boto3.client('s3', config=Config(signature_version=UNSIGNED))


def construct_s3_path(product_title: str) -> str:
    """
    Construct S3 path for Sentinel-2 L2A product based on product title.
    
    Args:
        product_title: Full product title from Sentinel query.
        
    Returns:
        str: S3 path prefix for the product.
        
    Example:
        For product 'S2A_MSIL2A_20250101T103421_N0511_R008_T30UXC_20250101T123456',
        returns 'tiles/10/S/UG/2025/1/1/'
    """
    # Extract tile information from product title
    # Format: S2X_MSIL2A_YYYYMMDDTHHMMSS_NXXXX_RXXX_TXXXXX_YYYYMMDDTHHMMSS
    tile_id = product_title[38:44]  # Extract TXXXXX part
    utm_zone = tile_id[1:3]        # Extract zone (e.g., '30')
    latitude_band = tile_id[3:4]   # Extract latitude band (e.g., 'U')
    square = tile_id[4:6]          # Extract square (e.g., 'XC')
    
    # Extract date information
    date_part = product_title[11:19]  # Extract YYYYMMDD
    year = date_part[:4]
    month = str(int(date_part[4:6]))  # Remove leading zero
    day = str(int(date_part[6:8]))    # Remove leading zero
    
    s3_path = f"tiles/{utm_zone}/{latitude_band}/{square}/{year}/{month}/{day}/"
    return s3_path


def list_product_files(s3_client: boto3.client, s3_path: str) -> List[str]:
    """
    List available files for a Sentinel product in S3.
    
    Args:
        s3_client: Configured S3 client.
        s3_path: S3 path prefix for the product.
        
    Returns:
        List[str]: List of S3 object keys for the product files.
        
    Raises:
        ValueError: If no files are found at the specified S3 path.
    """
    print(f"Listing files at s3://{config.AWS_S3_BUCKET}/{s3_path}")
    
    response = s3_client.list_objects_v2(
        Bucket=config.AWS_S3_BUCKET, 
        Prefix=s3_path
    )
    
    if 'Contents' not in response:
        raise ValueError(f"No files found at S3 path: {s3_path}")
    
    file_keys = [obj['Key'] for obj in response['Contents']]
    print(f"Found {len(file_keys)} files")
    
    return file_keys


def download_product_files(
    s3_client: boto3.client, 
    file_keys: List[str], 
    product_title: str,
    output_dir: Optional[str] = None
) -> str:
    """
    Download Sentinel product files from S3 to local directory.
    
    Args:
        s3_client: Configured S3 client.
        file_keys: List of S3 object keys to download.
        product_title: Product title for creating output directory.
        output_dir: Custom output directory. If None, uses product title.
        
    Returns:
        str: Path to the output directory containing downloaded files.
    """
    if output_dir is None:
        output_dir = f"./{product_title}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Downloading {len(file_keys)} files to {output_dir}")
    
    for file_key in file_keys:
        file_name = os.path.join(output_dir, file_key.split('/')[-1])
        print(f"Downloading {file_key.split('/')[-1]}")
        
        s3_client.download_file(
            config.AWS_S3_BUCKET, 
            file_key, 
            file_name
        )
    
    print(f"Download complete. Files saved to {output_dir}")
    return output_dir


def main() -> None:
    """
    Main function to execute the complete Sentinel imagery download workflow.
    """
    try:
        # Step 1: Set up API connection
        print("Setting up Copernicus API connection...")
        api = setup_copernicus_api()
        
        # Step 2: Define area of interest
        print("Creating area of interest...")
        footprint = create_area_of_interest(config.EXAMPLE_AOI)
        
        # Step 3: Query products
        print("Querying Sentinel products...")
        products_df = query_sentinel_products(api, footprint)
        
        # Step 4: Select best product
        print("Selecting best product...")
        product_id, product_title = select_best_product(products_df)
        
        # Step 5: Set up AWS S3 client
        print("Setting up AWS S3 client...")
        s3_client = setup_aws_s3_client()
        
        # Step 6: Construct S3 path and list files
        print("Constructing S3 path...")
        s3_path = construct_s3_path(product_title)
        file_keys = list_product_files(s3_client, s3_path)
        
        # Step 7: Download files
        print("Starting download...")
        output_dir = download_product_files(s3_client, file_keys, product_title)
        
        print("\n✅ Process completed successfully!")
        print(f"📁 Files downloaded to: {output_dir}")
        
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        print("Please check your configuration and try again.")



if __name__ == "__main__":
    main()
