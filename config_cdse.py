"""Configuration settings for Copernicus Data Space Ecosystem (CDSE) access."""

from typing import Optional

# Copernicus Data Space Ecosystem credentials
# Register at https://dataspace.copernicus.eu/
CDSE_USERNAME: Optional[str] = None  # Your CDSE username (email)
CDSE_PASSWORD: Optional[str] = None  # Your CDSE password

# CDSE API endpoints
CDSE_TOKEN_URL: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CDSE_ODATA_URL: str = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
CDSE_DOWNLOAD_URL: str = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"

# Default search parameters
DEFAULT_COLLECTION: str = "SENTINEL-2"
DEFAULT_PRODUCT_TYPE: str = "S2MSI2A"  # Level-2A (atmospherically corrected)
DEFAULT_MAX_CLOUD_COVER: int = 30

# Example Area of Interest (central London)
# Format for CDSE: Well-Known Text (WKT) format
EXAMPLE_AOI_WKT: str = "POLYGON((-0.15 51.48, -0.15 51.52, -0.10 51.52, -0.10 51.48, -0.15 51.48))"

# Alternative: GeoJSON format (can be converted to WKT)
EXAMPLE_AOI_GEOJSON = {
    "type": "Polygon",
    "coordinates": [[
        [-0.15, 51.48],  # Bottom-left
        [-0.15, 51.52],  # Top-left
        [-0.10, 51.52],  # Top-right
        [-0.10, 51.48],  # Bottom-right
        [-0.15, 51.48]   # Close polygon
    ]]
}

# AWS S3 settings for Sentinel data (still works with CDSE)
AWS_S3_BUCKET: str = "sentinel-s2-l2a"
