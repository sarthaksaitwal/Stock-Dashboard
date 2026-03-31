"""
Database population script.
Fetches stock data from Alpha Vantage (primary) and populates the database.

Usage:
    python populate_database.py
    
This script will:
1. Create all database tables
2. Fetch company information
3. Fetch historical stock data (365 days)
4. Calculate metrics (Daily Return, Moving Averages)
5. Store everything in the database
"""

import sys
import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from app.core.database import engine, SessionLocal, init_db
from app.models import Company, StockData, Base
from sqlalchemy import delete

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Company information - adding real Indian companies with details
COMPANIES_INFO = {
    "INFY": {
        "name": "Infosys Limited",
        "sector": "Information Technology",
        "description": "IT consulting and services company"
    },
    "TCS": {
        "name": "Tata Consultancy Services",
        "sector": "Information Technology",
        "description": "Global IT services and consulting"
    },
    "WIPRO": {
        "name": "Wipro Limited",
        "sector": "Information Technology",
        "description": "IT consulting and business process services"
    },
    "RELIANCE": {
        "name": "Reliance Industries",
        "sector": "Energy & Petrochemicals",
        "description": "Conglomerate in energy, chemicals, and retail"
    },
    "BAJAJFINSV": {
        "name": "Bajaj Finserv",
        "sector": "Financial Services",
        "description": "Finance and insurance company"
    },
    "LT": {
        "name": "Larsen & Toubro",
        "sector": "Engineering & Construction",
        "description": "Engineering, construction, and services"
    },
    "HINDUNILVR": {
        "name": "Hindustan Unilever",
        "sector": "Consumer Goods",
        "description": "FMCG and consumer products"
    },
    "ITC": {
        "name": "ITC Limited",
        "sector": "Consumer Goods",
        "description": "Tobacco, hotels, and agribusiness"
    },
    "MARUTI": {
        "name": "Maruti Suzuki",
        "sector": "Automobiles",
        "description": "Passenger vehicle manufacturer"
    },
    "MM": {
        "name": "Mahindra & Mahindra",
        "sector": "Automobiles",
        "description": "Automotive and farm equipment manufacturer"
    },
}


BASE_PRICES = {
    "INFY": 1500.0,
    "TCS": 3900.0,
    "WIPRO": 500.0,
    "RELIANCE": 2800.0,
    "BAJAJFINSV": 1600.0,
    "LT": 3500.0,
    "HINDUNILVR": 2400.0,
    "ITC": 450.0,
    "MARUTI": 10500.0,
    "MM": 2200.0,
}


ALPHA_VANTAGE_SYMBOLS = {
    "INFY": "INFY.BSE",
    "TCS": "TCS.BSE",
    "WIPRO": "WIPRO.BSE",
    "RELIANCE": "RELIANCE.BSE",
    "BAJAJFINSV": "BAJAJFINSV.BSE",
    "LT": "LT.BSE",
    "HINDUNILVR": "HINDUNILVR.BSE",
    "ITC": "ITC.BSE",
    "MARUTI": "MARUTI.BSE",
    "MM": "M&M.BSE",
}


def init_database():
    """Initialize database tables."""
    logger.info("Creating database tables...")
    Base.metadata.drop_all(bind=engine)  # Clear existing data
    init_db()
    logger.info("✅ Database tables created successfully")


def populate_companies(db):
    """Add company reference data to database."""
    logger.info("Populating company data...")
    
    companies = []
    for symbol, info in COMPANIES_INFO.items():
        company = Company(
            symbol=symbol,
            name=info["name"],
            sector=info["sector"],
            description=info["description"]
        )
        companies.append(company)
        logger.info(f"  Added: {symbol} - {info['name']}")
    
    db.add_all(companies)
    db.commit()
    logger.info(f"✅ Added {len(companies)} companies")


def fetch_and_clean_data(symbol: str, days: int = 365) -> pd.DataFrame:
    """
    Fetch stock data from Alpha Vantage and clean it.
    
    Args:
        symbol: Stock symbol
        days: Number of days of history
        
    Returns:
        Cleaned DataFrame with calculated metrics
    """
    try:
        logger.info(f"  Fetching data for {symbol}...")

        # Primary provider: Alpha Vantage
        alpha_data = fetch_from_alpha_vantage(symbol, days)
        if alpha_data is not None and not alpha_data.empty:
            logger.info(f"    Retrieved {len(alpha_data)} records from Alpha Vantage for {symbol}")
            return alpha_data

        logger.warning(f"    Alpha Vantage unavailable for {symbol}. Trying yfinance fallback...")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        data = yf.download(
            f"{symbol}.NS",
            start=start_date,
            end=end_date,
            progress=False
        )

        if data.empty:
            logger.warning(
                f"    No live provider data found for {symbol}. Using synthetic MOCK data for demonstration."
            )
            return generate_synthetic_data(symbol, days)

        data = data.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        data = data.ffill()

        data['Daily_Return'] = ((data['Close'] - data['Open']) / data['Open'] * 100).round(2)
        data['MA7'] = data['Close'].rolling(window=7).mean().round(2)
        data['MA30'] = data['Close'].rolling(window=30).mean().round(2)

        data = data.reset_index()

        logger.info(f"    Retrieved {len(data)} records from yfinance fallback for {symbol}")
        return data
        
    except Exception as e:
        logger.error(f"    Error fetching {symbol}: {str(e)}")
        logger.warning(
            f"    Falling back to synthetic MOCK data for {symbol} (demonstration mode)"
        )
        return generate_synthetic_data(symbol, days)


def fetch_from_alpha_vantage(symbol: str, days: int) -> pd.DataFrame:
    """Fetch daily historical OHLCV data from Alpha Vantage."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not api_key:
        logger.warning("    ALPHA_VANTAGE_API_KEY not set")
        return None

    provider_symbol = ALPHA_VANTAGE_SYMBOLS.get(symbol, f"{symbol}.BSE")
    try:
        response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": provider_symbol,
                "outputsize": "full",
                "apikey": api_key,
            },
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()

        if "Error Message" in payload:
            logger.warning(f"    Alpha Vantage error for {symbol}: {payload['Error Message']}")
            return None

        if "Note" in payload:
            logger.warning(f"    Alpha Vantage rate limit hit for {symbol}: {payload['Note']}")
            return None

        ts_key = next((k for k in payload.keys() if "Time Series" in k), None)
        if not ts_key or ts_key not in payload:
            logger.warning(f"    Alpha Vantage response missing timeseries for {symbol}")
            return None

        rows = []
        for date_str, values in payload[ts_key].items():
            rows.append(
                {
                    "Date": pd.to_datetime(date_str),
                    "Open": float(values.get("1. open", 0)),
                    "High": float(values.get("2. high", 0)),
                    "Low": float(values.get("3. low", 0)),
                    "Close": float(values.get("4. close", 0)),
                    "Volume": int(float(values.get("6. volume", 0))),
                }
            )

        data = pd.DataFrame(rows)
        if data.empty:
            return None

        data = data.sort_values("Date").tail(days).reset_index(drop=True)
        data = data.dropna(subset=["Close", "Open", "High", "Low", "Volume"])

        if data.empty:
            return None

        data["Daily_Return"] = ((data["Close"] - data["Open"]) / data["Open"] * 100).round(2)
        data["MA7"] = data["Close"].rolling(window=7).mean().round(2)
        data["MA30"] = data["Close"].rolling(window=30).mean().round(2)

        return data
    except Exception as err:
        logger.warning(f"    Alpha Vantage request failed for {symbol}: {str(err)}")
        return None


def generate_synthetic_data(symbol: str, days: int = 365) -> pd.DataFrame:
    """Generate deterministic synthetic market data when live feeds are unavailable."""
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

    data = pd.DataFrame(
        {
            "Date": dates,
            "Open": open_series.values,
            "High": high_series.values,
            "Low": low_series.values,
            "Close": close_series.values,
            "Volume": volume_series,
        }
    )

    data["Daily_Return"] = ((data["Close"] - data["Open"]) / data["Open"] * 100).round(2)
    data["MA7"] = data["Close"].rolling(window=7).mean().round(2)
    data["MA30"] = data["Close"].rolling(window=30).mean().round(2)

    logger.info(f"    Generated {len(data)} synthetic records for {symbol}")
    return data


def populate_stock_data(db):
    """Fetch and populate stock data for all companies."""
    logger.info("Populating stock data...")
    
    db_session = SessionLocal()
    total_records = 0

    company_lookup = {
        symbol: company_id
        for symbol, company_id in db_session.query(Company.symbol, Company.id).all()
    }
    
    for symbol in COMPANIES_INFO.keys():
        try:
            logger.info(f"Processing {symbol}...")
            
            # Fetch data
            data = fetch_and_clean_data(symbol, days=365)
            
            if data is None:
                logger.warning(f"  Skipped {symbol} - no data available")
                continue
            
            # Insert into database
            stock_records = []
            company_id = company_lookup.get(symbol)
            if not company_id:
                logger.warning(f"  Skipped {symbol} - company id not found")
                continue

            for idx, row in data.iterrows():
                record = StockData(
                    company_id=company_id,
                    symbol=symbol,
                    date=pd.to_datetime(row['Date']),
                    open_price=float(row['Open']),
                    high_price=float(row['High']),
                    low_price=float(row['Low']),
                    close_price=float(row['Close']),
                    volume=int(row['Volume']),
                    daily_return=float(row['Daily_Return']) if pd.notna(row['Daily_Return']) else None,
                    moving_avg_7=float(row['MA7']) if pd.notna(row['MA7']) else None,
                    moving_avg_30=float(row['MA30']) if pd.notna(row['MA30']) else None
                )
                stock_records.append(record)
            
            db_session.add_all(stock_records)
            db_session.commit()
            
            total_records += len(stock_records)
            logger.info(f"  ✅ Added {len(stock_records)} records for {symbol}")
            
        except Exception as e:
            logger.error(f"  ❌ Error processing {symbol}: {str(e)}")
            db_session.rollback()
            continue
    
    db_session.close()
    logger.info(f"✅ Populated {total_records} stock records in total")


def print_database_summary():
    """Print summary of populated database."""
    db = SessionLocal()
    
    try:
        company_count = db.query(Company).count()
        record_count = db.query(StockData).count()
        
        logger.info("\n" + "="*50)
        logger.info("DATABASE SUMMARY")
        logger.info("="*50)
        logger.info(f"Total Companies: {company_count}")
        logger.info(f"Total Stock Records: {record_count}")
        
        if company_count > 0 and record_count > 0:
            companies = db.query(Company).all()
            logger.info("\nCompanies loaded:")
            for company in companies:
                record_count_per_company = db.query(StockData).filter(
                    StockData.symbol == company.symbol
                ).count()
                logger.info(f"  • {company.symbol}: {record_count_per_company} records")
        
        logger.info("="*50)
        logger.info("\n✅ Database population complete!\n")
        logger.info("You can now start the API server:")
        logger.info("  python main.py")
        logger.info("\nThen visit:")
        logger.info("  • API: http://localhost:8000")
        logger.info("  • Docs: http://localhost:8000/api/docs")
        logger.info("  • ReDoc: http://localhost:8000/api/redoc\n")
        
    finally:
        db.close()


def main():
    """Main function to run database population."""
    try:
        logger.info("\n" + "="*50)
        logger.info("STOCK DASHBOARD - DATABASE POPULATION")
        logger.info("="*50 + "\n")
        
        # Initialize database
        init_database()
        
        # Get database session
        db = SessionLocal()
        
        try:
            # Populate data
            populate_companies(db)
            populate_stock_data(db)
            
            # Print summary
            print_database_summary()
            
        finally:
            db.close()
        
        logger.info("\n🎉 Setup complete! Database is ready to use.\n")
        
    except Exception as e:
        logger.error(f"\n❌ ERROR: {str(e)}")
        logger.error("Database population failed!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
