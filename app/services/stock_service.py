"""Service for stock data business logic."""

from sqlalchemy.orm import Session
from app.models import StockData, Company
import logging

logger = logging.getLogger(__name__)


class StockService:
    """
    Service for stock-related business logic.
    Handles queries and data processing from database.
    """
    
    @staticmethod
    def get_all_companies(db: Session) -> list:
        """Get all tracked companies."""
        try:
            companies = db.query(Company).all()
            return [{"symbol": c.symbol, "name": c.name} for c in companies]
        except Exception as e:
            logger.error(f"Error fetching companies: {str(e)}")
            raise
    
    @staticmethod
    def get_stock_data(db: Session, symbol: str, days: int = 30) -> list:
        """Get recent stock data for a symbol."""
        try:
            data = db.query(StockData).filter(
                StockData.symbol == symbol
            ).order_by(StockData.date.desc()).limit(days).all()
            
            return data[::-1]  # Return in ascending date order
        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
            raise
    
    @staticmethod
    def get_52week_summary(db: Session, symbol: str) -> dict:
        """Get 52-week high, low, and average close for a symbol."""
        try:
            data = db.query(StockData).filter(
                StockData.symbol == symbol
            ).order_by(StockData.date.desc()).limit(252).all()  # ~52 weeks
            
            if not data:
                return None
            
            close_prices = [d.close_price for d in data]
            
            return {
                "symbol": symbol,
                "week_52_high": max(close_prices),
                "week_52_low": min(close_prices),
                "avg_close": sum(close_prices) / len(close_prices),
                "latest_price": data[0].close_price,
                "latest_date": data[0].date
            }
        except Exception as e:
            logger.error(f"Error calculating summary for {symbol}: {str(e)}")
            raise
