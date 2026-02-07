from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Paths
    raw_data_path: Path = Path("./data/raw")
    processed_data_path: Path = Path("./data/processed")
    chunks_data_path: Path = Path("./data/chunks")
    
    # Docling options
    output_format: Literal["markdown", "json", "text"] = "markdown"
    export_tables: bool = True  # Changed from EXPORT_TABLES
    export_images: bool = False  # Changed from EXPORT_IMAGES
    
    # Logging
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False  # This makes it work with EXPORT_TABLES or export_tables
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they don't exist
        self.raw_data_path.mkdir(parents=True, exist_ok=True)
        self.processed_data_path.mkdir(parents=True, exist_ok=True)
        self.chunks_data_path.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()