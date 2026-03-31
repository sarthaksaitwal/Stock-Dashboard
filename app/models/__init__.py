"""Database models."""
from sqlalchemy.orm import declarative_base

Base = declarative_base()

from .stock_data import StockData
from .company import Company

__all__ = ["Base", "StockData", "Company"]
