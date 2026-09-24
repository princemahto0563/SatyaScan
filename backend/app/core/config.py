"""
SatyaScan Backend Configuration
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "SatyaScan"
    VERSION: str = os.getenv("APP_VERSION", "1.0.4-phase4")
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Security (HS256 explicit)
    # In production, configure a 32+ character random secret via the JWT_SECRET environment variable.
    JWT_SECRET: str = os.getenv("JWT_SECRET", "satyascan_eval_demo_secret_key_change_in_production_2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours
    STRICT_AUTH: bool = os.getenv("STRICT_AUTH", "false").lower() in ("true", "1", "yes") or os.getenv("ENVIRONMENT", "development") == "production"
    
    # CORS Origin Whitelist (no wildcard with credentials)
    CORS_ALLOWED_ORIGINS: str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "https://satya-scan-phi.vercel.app,http://localhost:3000,http://127.0.0.1:3000"
    )

    # In-memory Rate Limiting (per IP per minute)
    LOGIN_RATE_LIMIT: int = int(os.getenv("LOGIN_RATE_LIMIT", "10"))
    SCREENING_RATE_LIMIT: int = int(os.getenv("SCREENING_RATE_LIMIT", "20"))

    # File Upload & Image Processing Security Caps
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    MAX_IMAGE_DIMENSION: int = 5000               # max width/height in px
    MAX_IMAGE_PIXELS: int = 25_000_000            # max total pixels (decompression bomb ceiling)
    
    # Storage & Root Paths
    BACKEND_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    PROJECT_ROOT: str = os.path.dirname(BACKEND_DIR)
    BASE_DIR: str = BACKEND_DIR
    STORAGE_DIR: str = os.path.join(BACKEND_DIR, "storage")
    UPLOAD_DIR: str = os.path.join(STORAGE_DIR, "uploads")
    HEATMAP_DIR: str = os.path.join(STORAGE_DIR, "heatmaps")
    REPORT_DIR: str = os.path.join(STORAGE_DIR, "reports")
    DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")
    
    # Database: SQLite by default for zero-config local execution, PostgreSQL when configured
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(PROJECT_ROOT, 'satyascan.db')}")
    
    # Hyperledger Fabric Permissioned Blockchain Anchor Configuration
    FABRIC_ENABLED: bool = os.getenv("FABRIC_ENABLED", "false").lower() in ("true", "1", "yes")
    FABRIC_GATEWAY_PEER: str = os.getenv("FABRIC_GATEWAY_PEER", "localhost:7051")
    FABRIC_CHANNEL: str = os.getenv("FABRIC_CHANNEL", "satyascan-channel")
    FABRIC_CHAINCODE: str = os.getenv("FABRIC_CHAINCODE", "screening_anchor")
    FABRIC_MSP_ID: str = os.getenv("FABRIC_MSP_ID", "Org1MSP")
    FABRIC_CRYPTO_PATH: str = os.getenv("FABRIC_CRYPTO_PATH", os.path.join(PROJECT_ROOT, "blockchain", "crypto-config"))
    FABRIC_CONNECTION_PROFILE: str = os.getenv("FABRIC_CONNECTION_PROFILE", os.path.join(PROJECT_ROOT, "blockchain", "connection-profile.json"))
    
    @property
    def cors_origins_list(self) -> list[str]:
        origins = [orig.strip() for orig in self.CORS_ALLOWED_ORIGINS.split(",") if orig.strip()]
        for req_orig in ("https://satya-scan-phi.vercel.app", "http://localhost:3000", "http://127.0.0.1:3000"):
            if req_orig not in origins:
                origins.append(req_orig)
        return origins

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.HEATMAP_DIR, exist_ok=True)
os.makedirs(settings.REPORT_DIR, exist_ok=True)
