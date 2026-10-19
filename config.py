"""
Configuration Module for Developer Activity Tracker.
Loads and validates settings from environment variables using python-dotenv.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()


class Config:
    """Application configuration parameters."""

    # FerretDB Configuration (MongoDB wire-protocol compatible)
    FERRETDB_URI = os.getenv("FERRETDB_URI", "mongodb://127.0.0.1:27017/")
    FERRETDB_DB_NAME = os.getenv("FERRETDB_DB_NAME", "developer_tracker")
    FERRETDB_COLLECTION_NAME = os.getenv("FERRETDB_COLLECTION_NAME", "activities")

    # Redis Cache Configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

    # Web Server Configuration
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "True").strip().lower() in ("true", "1", "yes")

    # Valid statuses for developer activities
    VALID_STATUSES = ["Success", "Pending", "Failed"]
