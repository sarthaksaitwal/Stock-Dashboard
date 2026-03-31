"""Service for fetching and processing stock data."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataService:
    """
    Service for handling stock data operations.
    Fetches data from yfinance, processes and cleans it.
    """
    
    @staticmethod
    def fetch_stock_data(symbol: str, days: int = 365) -> pd.DataFrame:
        """
        Fetch historical stock data using yfinance.
        
        Args:
            symbol: Stock symbol (e.g., 'INFY')
            days: Number of days of history to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Fetch data from yfinance
            data = yf.download(
                f"{symbol}.NS",  # .NS for NSE (India)
                start=start_date,
                end=end_date,
                progress=False
            )
            
            logger.info(f"Successfully fetched {len(data)} records for {symbol}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            raise
    
    @staticmethod
    def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical metrics for stock data.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added calculated metrics
        """
        try:
            # Make a copy to avoid modifying original
            df = df.copy()
            
            # Daily Return = (Close - Open) / Open * 100
            df['Daily_Return'] = ((df['Close'] - df['Open']) / df['Open'] * 100).round(2)
            
            # 7-day Moving Average
            df['MA7'] = df['Close'].rolling(window=7).mean().round(2)
            
            # 30-day Moving Average
            df['MA30'] = df['Close'].rolling(window=30).mean().round(2)
            
            logger.info("Metrics calculated successfully")
            return df
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            raise
    
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean stock data (handle missing values, format dates).
        
        Args:
            df: Raw stock data
            
        Returns:
            Cleaned DataFrame
        """
        try:
            # Remove rows with missing critical values
            df = df.dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
            
            # Forward fill any remaining NaN values
            df = df.fillna(method='ffill')
            
            # Reset index to get date as column
            df = df.reset_index()
            
            logger.info(f"Data cleaned. {len(df)} records retained.")
            return df
            
        except Exception as e:
            logger.error(f"Error cleaning data: {str(e)}")
            raise
