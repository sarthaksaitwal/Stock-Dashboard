"""Pydantic schemas for company validation."""

from pydantic import BaseModel
from typing import Optional


class CompanySchema(BaseModel):
    """Schema for company data response."""
    
    id: int
    symbol: str
    name: str
    sector: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        from_attributes = True
