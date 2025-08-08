"""
Sentinel satellite imagery download using the new Copernicus Data Space Ecosystem (CDSE).

This script replaces the deprecated Copernicus Open Access Hub with the new CDSE OData API.
Works with the current system as of 2025.
"""

import os
import json
import time
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote

import requests
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import pandas as pd

import config_cdse


def get_access_token() -> str:
    """
    Get access token from CDSE identity service.
    
    Returns:
        str: Access token for API authentication.
        
    Raises:
        ValueError: If credentials are not configured or authentication fails.
    """
    if not config_cdse.CDSE_USERNAME or not config_cdse.CDSE_PASSWORD:
        raise ValueError(
            "Please set CDSE_USERNAME and CDSE_PASSWORD in config_cdse.py. "
            "Register at https://dataspace.copernicus.eu/"
        )
    
    data = {
        "client_id": "cdse-public",
        "username": config_cdse.CDSE_USERNAME,
        "password": config_cdse.CDSE_PASSWORD,
        "grant_type": "password"
    }
    
    try:
        response = requests.post(
            config_cdse.CDSE_TOKEN_URL,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        response.raise_for_status()
        
        return response.json()["access_token"]
    
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to get access token: {e}")
    except KeyError:
        raise ValueError("Invalid response from token service - check credentials")


def geojson_to_wkt(geojson: Dict[str, Any]) -> str:
    """
    Convert GeoJSON polygon to WKT format for CDSE API.
    
    Args:
        geojson: GeoJSON polygon dict with 'type' and 'coordinates' keys.
        
    Returns:
        str: Well-Known Text (WKT) representation of the polygon.
    """
    if geojson["type"] != "Polygon":
        raise ValueError("Only Polygon geometry is supported")
    
    coords = geojson["coordinates"][0]  # Exterior ring
    wkt_coords = ", ".join([f"{lon} {lat}" for lon, lat in coords])
    
    return f"POLYGON(({wkt_coords}))"


def format_date_for_cdse(date_input: Any) -> str:
    """
    Format date for CDSE OData API.
    
    Args:
        date_input: Date as string (YYYYMMDD), date object, or datetime object.
        
    Returns:
        str: ISO 8601 formatted date string.
    """
    if isinstance(date_input, str):
        # Assume YYYYMMDD format
        return f"{date_input[:4]}-{date_input[4:6]}-{date_input[6:8]}T00:00:00.000Z"
    elif isinstance(date_input, (date, datetime)):
        return date_input.strftime("%Y-%m-%dT00:00:00.000Z")
    else:
        raise ValueError(f"Unsupported date format: {type(date_input)}")


def build_odata_filter(
    collection: str,
    area_wkt: str,
    start_date: str,
    end_date: str,
    product_type: str,
    max_cloud_cover: int
) -> str:
    """
    Build OData filter string for CDSE API.
    
    Args:
        collection: Data collection name (e.g., 'SENTINEL-2').
        area_wkt: Area of interest in WKT format.
        start_date: Start date in ISO format.
        end_date: End date in ISO format.
        product_type: Product type (e.g., 'S2MSI2A').
        max_cloud_cover: Maximum cloud cover percentage.
        
    Returns:
        str: OData filter string.
    """
    # URL encode the WKT string
    area_encoded = quote(area_wkt)
    
    filter_parts = [
        f"Collection/Name eq '{collection}'",
        f"OData.CSC.Intersects(area=geography'SRID=4326;{area_encoded}')",
        f"ContentDate/Start gt {start_date}",
        f"ContentDate/Start lt {end_date}",
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq '{product_type}')"
    ]
    
    # Add cloud cover filter for Sentinel-2
    if collection == "SENTINEL-2":
        filter_parts.append(
            f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le {max_cloud_cover})"
        )
    
    return " and ".join(filter_parts)


def search_products(
    access_token: str,
    area_wkt: str,
    start_date: str = "20250101",
    end_date: Optional[str] = None,
    collection: str = config_cdse.DEFAULT_COLLECTION,
    product_type: str = config_cdse.DEFAULT_PRODUCT_TYPE,
    max_cloud_cover: int = config_cdse.DEFAULT_MAX_CLOUD_COVER,
    max_results: int = 100
) -> pd.DataFrame:
    """
    Search for Sentinel products using CDSE OData API.
    
    Args:
        access_token: CDSE access token.
        area_wkt: Area of interest in WKT format.
        start_date: Start date in YYYYMMDD format.
        end_date: End date in YYYYMMDD format. If None, uses today's date.
        collection: Data collection name.
        product_type: Product type filter.
        max_cloud_cover: Maximum cloud cover percentage.
        max_results: Maximum number of results to return.
        
    Returns:
        pd.DataFrame: DataFrame containing search results.
        
    Raises:
        ValueError: If no products are found or API request fails.
    """
    if end_date is None:
        end_date = date.today().strftime("%Y%m%d")
    
    # Format dates for API
    start_date_iso = format_date_for_cdse(start_date)
    end_date_iso = format_date_for_cdse(end_date)
    
    # Build filter
    odata_filter = build_odata_filter(
        collection, area_wkt, start_date_iso, end_date_iso, 
        product_type, max_cloud_cover
    )
    
    # Build query URL
    params = {
        "$filter": odata_filter,
        "$orderby": "ContentDate/Start desc",
        "$top": max_results,
        "$count": "true"
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    print(f"Searching for {collection} products from {start_date} to {end_date}")
    print(f"Product type: {product_type}, Max cloud cover: {max_cloud_cover}%")
    
    try:
        response = requests.get(
            config_cdse.CDSE_ODATA_URL,
            params=params,
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("value"):
            raise ValueError(
                f"No products found for the specified criteria. "
                f"Try expanding the date range or increasing cloud cover threshold."
            )
        
        # Convert to DataFrame
        products_df = pd.DataFrame(data["value"])
        
        # Extract useful attributes
        if not products_df.empty:
            products_df = process_product_attributes(products_df)
        
        print(f"Found {len(products_df)} products")
        return products_df
        
    except requests.exceptions.RequestException as e:
        raise ValueError(f"API request failed: {e}")


def process_product_attributes(products_df: pd.DataFrame) -> pd.DataFrame:
    """
    Process and extract useful attributes from CDSE product results.
    
    Args:
        products_df: Raw DataFrame from CDSE API.
        
    Returns:
        pd.DataFrame: Processed DataFrame with extracted attributes.
    """
    processed_df = products_df.copy()
    
    # Extract common attributes
    for idx, row in processed_df.iterrows():
        attributes = row.get("Attributes", [])
        
        # Extract cloud cover
        cloud_cover = None
        product_type = None
        
        for attr in attributes:
            if attr.get("Name") == "cloudCover":
                cloud_cover = attr.get("Value")
            elif attr.get("Name") == "productType":
                product_type = attr.get("Value")
        
        processed_df.at[idx, "cloudcoverpercentage"] = cloud_cover
        processed_df.at[idx, "producttype"] = product_type
        processed_df.at[idx, "title"] = row.get("Name", "")
        processed_df.at[idx, "uuid"] = row.get("Id", "")
        processed_df.at[idx, "size"] = row.get("ContentLength", 0)
    
    return processed_df


def select_best_product(products_df: pd.DataFrame) -> Tuple[str, str]:
    """
    Select the best product from search results based on cloud cover.
    
    Args:
        products_df: DataFrame containing product metadata.
        
    Returns:
        Tuple[str, str]: Product ID and title of the selected product.
    """
    # Sort by cloud cover (ascending) and select the first product
    best_product = products_df.sort_values('cloudcoverpercentage').iloc[0]
    
    product_id = best_product['uuid']
    product_title = best_product['title']
    cloud_cover = best_product['cloudcoverpercentage']
    
    print(f"Selected product: {product_title}")
    print(f"Cloud cover: {cloud_cover:.1f}%")
    
    return product_id, product_title


def download_product_cdse(
    access_token: str,
    product_id: str,
    output_dir: str = ".",
    filename: Optional[str] = None
) -> str:
    """
    Download a product directly from CDSE.
    
    Args:
        access_token: CDSE access token.
        product_id: Product ID to download.
        output_dir: Directory to save the downloaded file.
        filename: Custom filename. If None, uses product ID.
        
    Returns:
        str: Path to the downloaded file.
    """
    if filename is None:
        filename = f"{product_id}.zip"
    
    file_path = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    
    download_url = f"{config_cdse.CDSE_DOWNLOAD_URL}({product_id})/$value"
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    print(f"Downloading product {product_id}...")
    print(f"URL: {download_url}")
    
    try:
        with requests.get(download_url, headers=headers, stream=True) as response:
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(file_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rProgress: {progress:.1f}%", end="", flush=True)
        
        print(f"\nDownload complete: {file_path}")
        return file_path
        
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Download failed: {e}")


def setup_aws_s3_client() -> boto3.client:
    """
    Set up AWS S3 client for accessing public Sentinel data.
    
    Returns:
        boto3.client: Configured S3 client with unsigned requests.
    """
    return boto3.client('s3', config=Config(signature_version=UNSIGNED))


def main() -> None:
    """
    Main function to execute the complete Sentinel imagery download workflow using CDSE.
    """
    try:
        # Step 1: Get access token
        print("🔐 Getting CDSE access token...")
        access_token = get_access_token()
        print("✅ Access token obtained")
        
        # Step 2: Define area of interest
        print("\n📍 Creating area of interest...")
        area_wkt = config_cdse.EXAMPLE_AOI_WKT
        # Alternative: convert from GeoJSON
        # area_wkt = geojson_to_wkt(config_cdse.EXAMPLE_AOI_GEOJSON)
        print(f"Area: {area_wkt}")
        
        # Step 3: Search for products
        print("\n🔍 Searching for Sentinel products...")
        products_df = search_products(access_token, area_wkt)
        
        # Step 4: Select best product
        print("\n⭐ Selecting best product...")
        product_id, product_title = select_best_product(products_df)
        
        # Step 5: Download product
        print("\n⬇️ Downloading product...")
        downloaded_file = download_product_cdse(
            access_token, 
            product_id, 
            output_dir="./downloads",
            filename=f"{product_title}.zip"
        )
        
        print("\n✅ Process completed successfully!")
        print(f"📁 File downloaded to: {downloaded_file}")
        print(f"📊 Product details:")
        print(f"   - Product ID: {product_id}")
        print(f"   - Product Title: {product_title}")
        
        # Optional: Show AWS S3 alternative
        print(f"\n💡 Note: You can also access this data via AWS S3 at:")
        print(f"   s3://{config_cdse.AWS_S3_BUCKET}/")
        
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        print("Please check your configuration and try again.")
        print("Make sure you've registered at https://dataspace.copernicus.eu/")


if __name__ == "__main__":
    main()
