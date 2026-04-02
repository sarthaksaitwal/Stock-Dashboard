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
        from app.models import Company, StockData
        import sys
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
        
        NSELIB_SYMBOLS = {"MM": "M&M"}
        
        def _parse_numeric(val):
            """Parse numeric values from Indian formats (1,234.56 or "1,234.56")."""
            if pd.isna(val):
                return None
            val_str = str(val).strip()
            if not val_str:
                return None
            try:
                return float(val_str.replace(",", ""))
            except ValueError:
                return None
        
        def fetch_from_nselib(symbol: str, days: int = 100) -> pd.DataFrame:
            """Fetch real data from NSELib."""
            if capital_market is None:
                return None
            try:
                provider_symbol = NSELIB_SYMBOLS.get(symbol, symbol)
                to_date = datetime.now().strftime("%d-%m-%Y")
                from_date = (datetime.now() - timedelta(days=max(days + 30, 45))).strftime("%d-%m-%Y")

                raw = capital_market.price_volume_and_deliverable_position_data(
                    symbol=provider_symbol,
                    from_date=from_date,
                    to_date=to_date,
                )

                data = raw if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw)
                if data.empty:
                    return None

                data.columns = [str(col).replace("\ufeff", "").replace('"', "").strip() for col in data.columns]
                required_cols = {"Date", "OpenPrice", "HighPrice", "LowPrice", "ClosePrice", "TotalTradedQuantity"}
                if not required_cols.issubset(set(data.columns)):
                    return None

                data = data.loc[:, ["Date", "OpenPrice", "HighPrice", "LowPrice", "ClosePrice", "TotalTradedQuantity"]].copy()
                data["Date"] = pd.to_datetime(data["Date"], format="%d-%b-%Y", errors="coerce")
                data["Open"] = data["OpenPrice"].apply(_parse_numeric)
                data["High"] = data["HighPrice"].apply(_parse_numeric)
                data["Low"] = data["LowPrice"].apply(_parse_numeric)
                data["Close"] = data["ClosePrice"].apply(_parse_numeric)
                data["Volume"] = data["TotalTradedQuantity"].apply(_parse_numeric)

                data = data.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"])
                if data.empty:
                    return None

                data = data.sort_values("Date").tail(days).reset_index(drop=True)
                data["Volume"] = data["Volume"].astype(int)
                data["Daily_Return"] = ((data["Close"] - data["Open"]) / data["Open"] * 100).round(2)
                data["MA7"] = data["Close"].rolling(window=7).mean().round(2)
                data["MA30"] = data["Close"].rolling(window=30).mean().round(2)
                return data[["Date", "Open", "High", "Low", "Close", "Volume", "Daily_Return", "MA7", "MA30"]]
            except Exception as e:
                logger.warning(f"NSELib fetch failed for {symbol}: {e}")
                return None
        
        def generate_synthetic_data(symbol: str, days: int = 100) -> pd.DataFrame:
            """Generate realistic synthetic market data."""
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            dates = pd.bdate_range(start=start_date, end=end_date)
            
            if len(dates) == 0:
                return None
            
            seed = abs(hash(symbol)) % (2**32)
            rng = np.random.default_rng(seed)
            base_price = BASE_PRICES.get(symbol, 1000.0)
            
            close_prices = [base_price]
            for _ in range(1, len(dates)):
                daily_move = rng.normal(loc=0.0006, scale=0.015)
                next_close = max(1.0, close_prices[-1] * (1 + daily_move))
                close_prices.append(next_close)
            
            close_series = pd.Series(close_prices)
            open_series = close_series.shift(1).fillna(close_series.iloc[0] * (1 + rng.normal(0, 0.003, 1)[0]))
            high_series = pd.concat([open_series, close_series], axis=1).max(axis=1) * (1 + rng.uniform(0.001, 0.02, len(dates)))
            low_series = pd.concat([open_series, close_series], axis=1).min(axis=1) * (1 - rng.uniform(0.001, 0.02, len(dates)))
            volume_series = rng.integers(250_000, 3_500_000, len(dates))
            
            data = pd.DataFrame({
                "Date": dates,
                "Open": open_series.values,
                "High": high_series.values,
                "Low": low_series.values,
                "Close": close_series.values,
                "Volume": volume_series,
            })
            
            data["Daily_Return"] = ((data["Close"] - data["Open"]) / data["Open"] * 100).round(2)
            data["MA7"] = data["Close"].rolling(window=7).mean().round(2)
            data["MA30"] = data["Close"].rolling(window=30).mean().round(2)
            return data
        
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
            
            # Populate stock data (try NSELib first, fallback to synthetic)
            logger.info("Populating stock data...")
            for symbol in COMPANIES_INFO.keys():
                logger.info(f"  Fetching data for {symbol}...")
                
                # Try NSELib (most reliable)
                data = fetch_from_nselib(symbol, days=100)
                if data is None or data.empty:
                    logger.info(f"    NSELib unavailable. Using synthetic data for {symbol}")
                    data = generate_synthetic_data(symbol, days=100)
                else:
                    logger.info(f"    Retrieved {len(data)} records from NSELib")
                
                if data is not None and not data.empty:
                    for _, row in data.iterrows():
                        stock_record = StockData(
                            symbol=symbol,
                            date=row["Date"].date(),
                            opening_price=float(row["Open"]),
                            closing_price=float(row["Close"]),
                            high_price=float(row["High"]),
                            low_price=float(row["Low"]),
                            volume=int(row["Volume"]),
                            daily_return=float(row["Daily_Return"])
                        )
                        if db.query(StockData).filter(
                            StockData.symbol == symbol,
                            StockData.date == row["Date"].date()
                        ).first() is None:
                            db.add(stock_record)
                    db.commit()
                    logger.info(f"  ✅ Added {len(data)} records for {symbol}")
            
            logger.info("✅ Stock data populated")
            logger.info("🎉 Auto-seed complete!")
            
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"❌ Auto-seed failed: {str(e)}", exc_info=True)
