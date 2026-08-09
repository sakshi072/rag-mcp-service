"""
Centralized configuration using Pydantic Settings

Benefits:
1. Type-safe configuration (autocomplete + validation)
2. Automatic .env loading (no manual load_dotenv())
3. Validation at startup (fail fast with clear errors)
4. Single source of truth for all config
5. Environment-aware (dev/staging/prod)
"""

from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseSettings):
    """
    PostgreSQL database configuration
    Separate class for logical grouping
    """

    # Required fields (will raise error if missing)
    db:str = Field(..., description="Database name")
    user:str = Field(..., description="Database user")
    password:str = Field(..., description="Database password")

    # Optional with defaults
    host:str = Field(default="localhost", description="Database host")
    port:int = Field(default=5432, description="Database port")

    # Computed Property
    @property
    def url(self) -> str:
        """
        Build database url dynamically
        """
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="POSTGRES_",
        case_sensitive=False,
        extra="ignore"
    )
class MinIOSettings(BaseSettings):
    """MinIo object storage configuration"""

    endpoint:str = Field(default="localhost:9000")
    root_user:str = Field(default="minioadmin")
    root_password:str = Field(default="minioadmin")
    bucket:str = Field(default="document-storage")
    secure:bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MINIO_",
        case_sensitive=False,
        extra="ignore"
    )
class Settings(BaseSettings):
    """
    Main settings class - aggregates all configuration
    """
    env:Literal["development", "staging", "production"] = Field(
        default="development"
    )
    debug:bool = Field(default=True)

    # Nested Settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",
        extra="ignore",
        case_sensitive=False
    )

@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance
    
    - Settings only loaded once (performance)
    - Same instance reused everywhere (consistency)
    - Can be easily mocked in tests
    """
    return Settings()

settings = get_settings()