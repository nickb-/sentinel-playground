"""Configuration settings for Sentinel satellite imagery processing."""

from typing import Optional

# Copernicus Open Access Hub credentials
# You need to register at https://scihub.copernicus.eu/dhus/
COPERNICUS_USERNAME: Optional[str] = ""  # Replace with your username
COPERNICUS_PASSWORD: Optional[str] = ""  # Replace with your password
COPERNICUS_API_URL: str = "https://scihub.copernicus.eu/dhus"

# AWS S3 settings for Sentinel data
AWS_S3_BUCKET: str = "sentinel-s2-l2a"

# Default query parameters
DEFAULT_PLATFORM: str = "Sentinel-2"
DEFAULT_PRODUCT_TYPE: str = "S2MSI2A"  # Level-2A (atmospherically corrected)
DEFAULT_MAX_CLOUD_COVER: int = 30

# Example Area of Interest (central London)
# Format: (min_lon, min_lat, max_lon, max_lat)
EXAMPLE_AOI = {
    "type": "Polygon",
    "coordinates": [[
        [-0.15, 51.48],  # Bottom-left
        [-0.15, 51.52],  # Top-left
        [-0.10, 51.52],  # Top-right
        [-0.10, 51.48],  # Bottom-right
        [-0.15, 51.48]   # Close polygon
    ]]
}
