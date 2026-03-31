"""
Companies API endpoints.
Handles retrieving and managing company information.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models import Company, StockData
from app.schemas.company import CompanySchema
from typing import List

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
    responses={404: {"description": "Company not found"}}
)


@router.get("", response_model=List[CompanySchema])
async def get_all_companies(db: Session = Depends(get_db)):
    """
    Get list of all tracked companies.
    
    Returns:
        List of companies with symbol, name, and details
        
    Example:
        GET /companies
        
        [
            {
                "id": 1,
                "symbol": "INFY",
                "name": "Infosys Limited",
                "sector": "Information Technology",
                "description": "..."
            },
            ...
        ]
    """
    try:
        companies = db.query(Company).order_by(Company.symbol).all()
        
        if not companies:
            raise HTTPException(
                status_code=404,
                detail="No companies found. Please populate database first."
            )
        
        return companies
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching companies: {str(e)}"
        )


@router.get("/{symbol}", response_model=CompanySchema)
async def get_company_by_symbol(symbol: str, db: Session = Depends(get_db)):
    """
    Get company details by stock symbol.
    
    Path Parameters:
        symbol: Stock symbol (e.g., "INFY", "TCS")
        
    Returns:
        Company object with all details
        
    Example:
        GET /companies/INFY
        
        {
            "id": 1,
            "symbol": "INFY",
            "name": "Infosys Limited",
            "sector": "Information Technology",
            "description": "..."
        }
    """
    try:
        company = db.query(Company).filter(
            Company.symbol.ilike(symbol)
        ).first()
        
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with symbol '{symbol}' not found"
            )
        
        return company
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching company: {str(e)}"
        )


@router.get("/stats/overview")
async def get_companies_overview(db: Session = Depends(get_db)):
    """
    Get overview statistics of all tracked companies.
    
    Returns:
        Statistics including count and data availability
        
    Example:
        GET /companies/stats/overview
        
        {
            "total_companies": 10,
            "total_stock_records": 2500,
            "data_coverage": {
                "INFY": 252,
                "TCS": 252,
                ...
            }
        }
    """
    try:
        total_companies = db.query(func.count(Company.id)).scalar()
        total_records = db.query(func.count(StockData.id)).scalar()
        
        # Get record count per company
        coverage = db.query(
            Company.symbol,
            func.count(StockData.id).label("count")
        ).join(StockData).group_by(Company.symbol).all()
        
        data_coverage = {symbol: count for symbol, count in coverage}
        
        return {
            "total_companies": total_companies,
            "total_stock_records": total_records,
            "data_coverage": data_coverage
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching overview: {str(e)}"
        )
