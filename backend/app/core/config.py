"""
SatyaScan Backend Configuration
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "SatyaScan"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "satyascan_production_sec_key_2026_sih_secure_993817")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours
    
    # Database: SQLite by default for zero-config local execution, PostgreSQL when configured
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./satyascan.db")
    
    # Storage Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    STORAGE_DIR: str = os.path.join(BASE_DIR, "storage")
    UPLOAD_DIR: str = os.path.join(STORAGE_DIR, "uploads")
    HEATMAP_DIR: str = os.path.join(STORAGE_DIR, "heatmaps")
    REPORT_DIR: str = os.path.join(STORAGE_DIR, "reports")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.HEATMAP_DIR, exist_ok=True)
os.makedirs(settings.REPORT_DIR, exist_ok=True)
