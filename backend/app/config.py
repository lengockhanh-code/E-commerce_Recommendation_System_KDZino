"""Application Configuration Settings"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings:
    PROJECT_NAME: str = "MerRec E-Commerce Recommender API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database Settings
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/merrec"
    )

    # Parquet Catalog Fallback
    MERREC_CATALOG_PATH: str = os.environ.get(
        "MERREC_CATALOG_PATH",
        str(ROOT_DIR / "data/processed/recommender/serving/item_catalog_full.parquet"),
    )
    MERREC_FORCE_PARQUET: bool = os.environ.get("MERREC_FORCE_PARQUET", "0") == "1"

    # JWT Authentication Secrets
    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY", "MERREC_SUPER_SECRET_JWT_KEY_2026_CHANGE_IN_PRODUCTION"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Google OAuth 2.0 Credentials (Fill keys in .env)
    GOOGLE_CLIENT_ID: str = os.environ.get(
        "GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID_PLACEHOLDER.apps.googleusercontent.com"
    )
    GOOGLE_CLIENT_SECRET: str = os.environ.get(
        "GOOGLE_CLIENT_SECRET", "YOUR_GOOGLE_CLIENT_SECRET_PLACEHOLDER"
    )


settings = Settings()
