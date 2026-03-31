"""Database model for company information."""

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from . import Base


class Company(Base):
    """
    Model for storing company information.
    Reference data for all tracked companies.
    """
    
    __tablename__ = "company"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=True)
    description = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Company(symbol={self.symbol}, name={self.name})>"
