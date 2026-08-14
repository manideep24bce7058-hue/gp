# config.py
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load secrets from the .env file
load_dotenv()

# Base directory configuration
BASE_DIR = Path(__file__).resolve().parent

# Your offline local SQLite database
LOCAL_DATABASE_URL = f"sqlite:///{BASE_DIR / 'google_photos.db'}"

# Your online Aiven PostgreSQL database loaded securely from .env
CLOUD_DATABASE_URL = os.getenv("CLOUD_DATABASE_URL")

# Browser automation settings
HEADLESS = False
BROWSER_TIMEOUT_MS = 100000