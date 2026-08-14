from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SQLALCHEMY_DATABASE_URL = f"sqlite:///{BASE_DIR / 'google_photos.db'}"

HEADLESS = False

BROWSER_TIMEOUT_MS = 100000