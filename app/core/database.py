"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from pathlib import Path


def _resolve_database_url(url: str) -> str:
    """Resolve relative SQLite URLs to a stable absolute path in the project root."""
    if not url.startswith("sqlite:///"):
        return url

    if url.startswith("sqlite:///./"):
        relative_part = url.replace("sqlite:///./", "", 1)
        project_root = Path(__file__).resolve().parents[2]
        absolute_path = project_root / relative_part
        return f"sqlite:///{absolute_path.as_posix()}"

    return url


resolved_database_url = _resolve_database_url(settings.database_url)

# Create database engine
engine = create_engine(
    resolved_database_url,
    connect_args={"check_same_thread": False} if "sqlite" in resolved_database_url else {},
    echo=settings.debug
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency for getting a database session.
    Used in FastAPI endpoints.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from app.models import Base
    Base.metadata.create_all(bind=engine)


def is_database_empty() -> bool:
    """Check if database has any companies (indicating if seed is needed)."""
    try:
        from app.models import Company
        db = SessionLocal()
        try:
            count = db.query(Company).count()
            return count == 0
        finally:
            db.close()
    except Exception:
        return True


def seed_database_if_empty():
    """Automatically seed database on first startup if it's empty."""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_database_empty():
        logger.info("Database already populated. Skipping seed.")
        return
    
    logger.info("Database is empty. Starting auto-seed...")
    
    try:
        # Import here to avoid circular imports
        from app.models import Company, StockData, Base
        import sys
        import os
        from datetime import datetime, timedelta
        import requests
        import pandas as pd
        import numpy as np
        from dotenv import load_dotenv
        
        try:
            from nselib import capital_market
        except ImportError:
            capital_market = None
        
        load_dotenv()
        
        # Company information
        COMPANIES_INFO = {
            "INFY": {"name": "Infosys Limited", "sector": "Information Technology", "description": "IT consulting and services company"},
            "TCS": {"name": "Tata Consultancy Services", "sector": "Information Technology", "description": "Global IT services and consulting"},
            "WIPRO": {"name": "Wipro Limited", "sector": "Information Technology", "description": "IT consulting and business process services"},
            "RELIANCE": {"name": "Reliance Industries", "sector": "Energy & Petrochemicals", "description": "Conglomerate in energy, chemicals, and retail"},
            "BAJAJFINSV": {"name": "Bajaj Finserv", "sector": "Financial Services", "description": "Finance and insurance company"},
            "LT": {"name": "Larsen & Toubro", "sector": "Engineering & Construction", "description": "Engineering, construction, and services"},
            "HINDUNILVR": {"name": "Hindustan Unilever", "sector": "Consumer Goods", "description": "FMCG and consumer products"},
            "ITC": {"name": "ITC Limited", "sector": "Consumer Goods", "description": "Tobacco, hotels, and agribusiness"},
            "MARUTI": {"name": "Maruti Suzuki", "sector": "Automobiles", "description": "Passenger vehicle manufacturer"},
            "MM": {"name": "Mahindra & Mahindra", "sector": "Automobiles", "description": "Automotive and farm equipment manufacturer"},
        }
        
        BASE_PRICES = {
            "INFY": 1500.0, "TCS": 3900.0, "WIPRO": 500.0, "RELIANCE": 2800.0, "BAJAJFINSV": 1600.0,
            "LT": 3500.0, "HINDUNILVR": 2400.0, "ITC": 450.0, "MARUTI": 10500.0, "MM": 2200.0,
        }
        
        db = SessionLocal()
        try:
            # Populate companies
            logger.info("Populating companies...")
            for symbol, info in COMPANIES_INFO.items():
                if db.query(Company).filter(Company.symbol == symbol).first() is None:
                    company = Company(symbol=symbol, name=info["name"], sector=info["sector"], description=info["description"])
                    db.add(company)
                    logger.info(f"  Added: {symbol}")
            db.commit()
            logger.info("✅ Companies populated")
            
            # Populate synthetic stock data for each company
            logger.info("Populating stock data (synthetic for now)...")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=100)
            
            for symbol in COMPANIES_INFO.keys():
                base_price = BASE_PRICES.get(symbol, 1000.0)
                current_date = start_date
                
                while current_date <= end_date:
                    price = base_price * (1 + np.random.normal(0, 0.02))
                    price = max(price, base_price * 0.8)
                    
                    stock_record = StockData(
                        symbol=symbol,
                        date=current_date.date(),
                        opening_price=price * (1 + np.random.uniform(-0.01, 0.01)),
                        closing_price=price,
                        high_price=price * (1 + abs(np.random.uniform(0, 0.02))),
                        low_price=price * (1 - abs(np.random.uniform(0, 0.02))),
                        volume=int(np.random.uniform(100000, 1000000)),
                        daily_return=(price - base_price) / base_price if base_price else 0
                    )
                    
                    if db.query(StockData).filter(
                        StockData.symbol == symbol,
                        StockData.date == current_date.date()
                    ).first() is None:
                        db.add(stock_record)
                    
                    current_date += timedelta(days=1)
                
                db.commit()
                logger.info(f"  Added stock data for {symbol}")
            
            logger.info("✅ Stock data populated")
            logger.info("🎉 Auto-seed complete!")
            
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"❌ Auto-seed failed: {str(e)}", exc_info=True)
