"""
Application settings and configuration management.
Follows 12-factor app principles and uses environment variables.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Settings class for managing all configuration.
    Reads from .env file and environment variables.
    """
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # Database Configuration
    database_url: str = "postgresql+psycopg2://postgres:2004%23%40Sarthakk@localhost:5432/stock_dashboard"
    
    # Stock Configuration
    stocks_to_track: List[str] = [
        "INFY", "TCS", "WIPRO", "RELIANCE", "BAJAJFINSV",
        "LT", "HINDUNILVR", "ITC", "MARUTI", "M&M"
    ]
    date_range_days: int = 365
    
    # Data Update Schedule
    data_update_interval: int = 24  # hours
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create settings instance
settings = Settings()
