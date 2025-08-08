
# Project Planning Document  

We're going to work with Sentinel satellite imagery. In the past, I've used SentinelHub to query sentinel imagery. However, this is a paid service and I want to look at free alternatives. 

Sentinel imagery itself is freely available. The AWS Registry of Open Data stores all of sentinel and it can be queried using python library sentinelsat. We're going to explore this.

### Python Requirements
We need the following python libraries: sentinelsat, boto3, geopandas, shapely, matplotlib, numpy, pandas.

### Sample Code
Here is sample code. I'm not sure it will work, but let's treat it as if it does & we can test it out.

```
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
from datetime import date
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import os

# 1. Set up Copernicus API credentials
username = 'YOUR_COPERNICUS_USERNAME'  # Replace with your Copernicus Open Access Hub username
password = 'YOUR_COPERNICUS_PASSWORD'  # Replace with your password
api = SentinelAPI(username, password, 'https://scihub.copernicus.eu/dhus')

# 2. Define Area of Interest (AOI) and query parameters
# Example: Bounding box around a small area (e.g., central London)
# Format: (min_lon, min_lat, max_lon, max_lat)
footprint = geojson_to_wkt({
    'type': 'Polygon',
    'coordinates': [[
        [-0.15, 51.48],  # Bottom-left
        [-0.15, 51.52],  # Top-left
        [-0.10, 51.52],  # Top-right
        [-0.10, 51.48],  # Bottom-right
        [-0.15, 51.48]   # Close polygon
    ]]
})

# 3. Query Sentinel-2 L2A imagery
products = api.query(
    footprint,
    date=('20250101', date(2025, 8, 7)),  # Date range (YYYYMMDD or date object)
    platformname='Sentinel-2',
    producttype='S2MSI2A',  # Level-2A (atmospherically corrected)
    cloudcoverpercentage=(0, 30)  # Filter for 0-30% cloud cover
)

# 4. Convert query results to a DataFrame and select the first product
products_df = api.to_dataframe(products)
if products_df.empty:
    print("No products found for the specified criteria.")
    exit()

# Select the first product (you can sort by cloud cover or date if needed)
product_id = products_df.iloc[0]['uuid']
product_title = products_df.iloc[0]['title']
print(f"Selected product: {product_title}")

# 5. Set up AWS S3 client (unsigned for public data)
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))

# 6. Download the product from AWS S3
bucket = 'sentinel-s2-l2a'
product_path = f"tiles/{product_title[11:13]}/{product_title[13:14]}/{product_title[14:16]}/{product_title[-4:]}/{product_title[-2:]}"

# List files in the product directory
objects = s3.list_objects_v2(Bucket=bucket, Prefix=product_path)
if 'Contents' not in objects:
    print("No files found in S3 path.")
    exit()

# Download each file (e.g., imagery bands, metadata)
output_dir = f"./{product_title}"
os.makedirs(output_dir, exist_ok=True)

for obj in objects['Contents']:
    file_key = obj['Key']
    file_name = os.path.join(output_dir, file_key.split('/')[-1])
    print(f"Downloading {file_key} to {file_name}")
    s3.download_file(bucket, file_key, file_name)

print(f"Download complete. Files saved to {output_dir}")
```

### Useful links:

https://dataspace.copernicus.eu/thank-you
https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings (myaccount via sentinel hub. Looks like htere is oauth here & might be able to use sentinelhub directly?)
sentinehub docs: 
  - https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html#python
  - https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S2L2A.html