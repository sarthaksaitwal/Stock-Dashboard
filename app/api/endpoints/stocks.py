"""
Stock data API endpoints.
Handles stock price data, summaries, and comparisons.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from math import sqrt, sin, pi
import random
import asyncio
import requests
from app.core.database import get_db, SessionLocal
from app.models import StockData, Company
from app.schemas.stock import StockDataSchema, StockSummarySchema, PredictionResponseSchema
from app.services.prediction_service import PredictionService
from app.services.realtime_service import RealtimeQuoteService
from config.settings import settings
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data",
    tags=["stock-data"],
    responses={404: {"description": "Stock data not found"}}
)

realtime_quote_service = RealtimeQuoteService()


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


def _alpha_symbol(symbol: str) -> str:
    return ALPHA_VANTAGE_SYMBOLS.get(symbol.upper(), f"{symbol.upper()}.BSE")


def _alpha_daily_available(symbol: str) -> tuple[bool, str]:
    """Quick probe to determine whether Alpha Vantage daily data is available."""
    api_key = settings.alpha_vantage_api_key.strip()
    if not api_key:
        return False, "ALPHA_VANTAGE_API_KEY is not configured"

    try:
        provider_response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": _alpha_symbol(symbol),
                "outputsize": "compact",
                "apikey": api_key,
            },
            timeout=15,
        )
        provider_response.raise_for_status()
        payload = provider_response.json()

        if "Error Message" in payload:
            return False, "Alpha Vantage returned an error response"
        if "Note" in payload:
            return False, "Alpha Vantage rate limit reached"

        ts_key = next((k for k in payload.keys() if "Time Series" in k), None)
        if not ts_key or not payload.get(ts_key):
            return False, "Alpha Vantage daily time series missing"

        return True, "Live Alpha Vantage daily data is available"
    except requests.RequestException:
        return False, "Alpha Vantage request failed"


@router.get("/provider-status/{symbol}", response_model=dict)
async def get_provider_status(symbol: str):
    """Return whether live provider data is currently available for a symbol."""
    is_live, reason = _alpha_daily_available(symbol)
    return {
        "symbol": symbol.upper(),
        "is_live": is_live,
        "mode": "live" if is_live else "demo",
        "message": reason,
    }


def _build_session_points_from_daily(
    db: Session,
    symbol: str,
    selected_date,
    interval: str,
) -> List[dict]:
    """Fallback: synthesize intraday session points from stored daily candle."""
    interval_minutes = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}[interval]

    daily_row = db.query(StockData).filter(
        StockData.symbol == symbol.upper(),
        func.date(StockData.date) <= selected_date
    ).order_by(StockData.date.desc()).first()

    if not daily_row:
        return []

    market_start = datetime.combine(selected_date, datetime.strptime("09:15", "%H:%M").time())
    market_end = datetime.combine(selected_date, datetime.strptime("15:30", "%H:%M").time())

    total_minutes = int((market_end - market_start).total_seconds() // 60)
    points = (total_minutes // interval_minutes) + 1
    if points < 2:
        points = 2

    open_price = float(daily_row.open_price)
    close_price = float(daily_row.close_price)
    day_high = float(daily_row.high_price)
    day_low = float(daily_row.low_price)
    volume = int(daily_row.volume or 0)
    span = max(day_high - day_low, max(open_price, close_price) * 0.002)

    seed = abs(hash(f"{symbol.upper()}-{selected_date.isoformat()}-{interval}")) % (2**32)
    rng = random.Random(seed)

    rows = []
    for idx in range(points):
        ratio = idx / (points - 1)
        ts = market_start + timedelta(minutes=idx * interval_minutes)

        # Brownian-bridge style drift from open->close with intraday wave + noise.
        base_close = open_price + (close_price - open_price) * ratio
        wave = sin(2 * pi * ratio) * span * (0.12 + rng.uniform(0.02, 0.08))
        noise = rng.uniform(-1.0, 1.0) * span * (0.05 + 0.06 * (1 - abs(0.5 - ratio) * 2))
        close_i = base_close + wave + noise
        close_i = max(day_low, min(day_high, close_i))

        open_i = open_price if idx == 0 else rows[-1]["close_price"]
        high_i = max(open_i, close_i)
        low_i = min(open_i, close_i)

        if idx == max(1, points // 3):
            high_i = max(high_i, day_high)
        if idx == max(1, (2 * points) // 3):
            low_i = min(low_i, day_low)

        # Ensure first/last bars anchor to daily open/close.
        if idx == 0:
            open_i = open_price
            close_i = max(day_low, min(day_high, open_price))
            high_i = max(high_i, open_i, close_i)
            low_i = min(low_i, open_i, close_i)
        if idx == points - 1:
            close_i = max(day_low, min(day_high, close_price))
            high_i = max(high_i, open_i, close_i)
            low_i = min(low_i, open_i, close_i)

        volume_i = int(volume / points) if volume > 0 else 0

        rows.append(
            {
                "symbol": symbol.upper(),
                "date": ts.isoformat(),
                "open_price": round(float(open_i), 4),
                "high_price": round(float(high_i), 4),
                "low_price": round(float(low_i), 4),
                "close_price": round(float(close_i), 4),
                "volume": volume_i,
                "daily_return": None,
                "moving_avg_7": None,
                "moving_avg_30": None,
            }
        )

    return rows


def _pearson_correlation(values_a: List[float], values_b: List[float]) -> float:
    """Compute Pearson correlation coefficient for two numeric series."""
    if len(values_a) != len(values_b) or len(values_a) < 2:
        return 0.0

    mean_a = sum(values_a) / len(values_a)
    mean_b = sum(values_b) / len(values_b)

    numerator = sum((a - mean_a) * (b - mean_b) for a, b in zip(values_a, values_b))
    denominator_a = sum((a - mean_a) ** 2 for a in values_a)
    denominator_b = sum((b - mean_b) ** 2 for b in values_b)

    denominator = (denominator_a * denominator_b) ** 0.5
    if denominator == 0:
        return 0.0

    return numerator / denominator


@router.get("/session/{symbol}", response_model=List[dict])
async def get_market_session_data(
    symbol: str,
    trade_date: str = Query(..., description="Session date in YYYY-MM-DD format"),
    interval: str = Query("5min", description="Alpha Vantage intraday interval"),
    api_response: Response = None,
    db: Session = Depends(get_db),
):
    """Get all intraday points for one market session date for a stock symbol."""
    try:
        company = db.query(Company).filter(Company.symbol.ilike(symbol)).first()
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with symbol '{symbol}' not found")

        try:
            selected_date = datetime.strptime(trade_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid trade_date. Use YYYY-MM-DD format")

        allowed_intervals = {"1min", "5min", "15min", "30min", "60min"}
        if interval not in allowed_intervals:
            raise HTTPException(status_code=400, detail="Invalid interval. Use one of 1min, 5min, 15min, 30min, 60min")

        rows: List[dict] = []
        source = "fallback_daily"
        fallback_reason = "live intraday data unavailable"
        api_key = settings.alpha_vantage_api_key.strip()

        if api_key:
            try:
                provider_response = requests.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "TIME_SERIES_INTRADAY",
                        "symbol": _alpha_symbol(symbol),
                        "interval": interval,
                        "outputsize": "compact",
                        "apikey": api_key,
                    },
                    timeout=25,
                )
                provider_response.raise_for_status()
                payload = provider_response.json()

                ts_key = f"Time Series ({interval})"
                timeseries = payload.get(ts_key)

                if "Error Message" in payload:
                    fallback_reason = "Alpha Vantage returned an error response"
                elif "Note" in payload:
                    fallback_reason = "Alpha Vantage rate limit reached"
                elif not timeseries:
                    fallback_reason = "Alpha Vantage intraday time series missing"
                else:
                    for ts_str, point in timeseries.items():
                        try:
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            continue
                        if ts.date() != selected_date:
                            continue
                        rows.append(
                            {
                                "symbol": symbol.upper(),
                                "date": ts.isoformat(),
                                "open_price": float(point.get("1. open", 0)),
                                "high_price": float(point.get("2. high", 0)),
                                "low_price": float(point.get("3. low", 0)),
                                "close_price": float(point.get("4. close", 0)),
                                "volume": int(float(point.get("5. volume", 0))),
                                "daily_return": None,
                                "moving_avg_7": None,
                                "moving_avg_30": None,
                            }
                        )
                    if rows:
                        source = "live_api"
                    else:
                        fallback_reason = f"no intraday points returned for selected date {trade_date}"
            except requests.RequestException as e:
                fallback_reason = "Alpha Vantage request failed"
                logger.warning(f"Intraday provider request failed for {symbol}: {str(e)}")
        else:
            fallback_reason = "ALPHA_VANTAGE_API_KEY is not configured"

        if not rows:
            rows = _build_session_points_from_daily(db, symbol, selected_date, interval)
            source = "fallback_daily"

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No session points found for {symbol.upper()} on {trade_date}",
            )

        rows.sort(key=lambda item: item["date"])

        if api_response is not None:
            if source == "live_api":
                api_response.headers["X-Session-Source"] = "live_api"
                api_response.headers["X-Session-Message"] = "Live intraday data loaded from Alpha Vantage API."
            else:
                api_response.headers["X-Session-Source"] = "fallback_daily"
                api_response.headers["X-Session-Message"] = (
                    "Using fallback session data for demonstration because "
                    f"{fallback_reason}. This may include MOCK/simulated data."
                )

        logger.info(f"Retrieved {len(rows)} intraday points for {symbol.upper()} on {trade_date}")
        return rows

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching market session data for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching market session data: {str(e)}")


@router.get("/{symbol}", response_model=List[StockDataSchema])
async def get_stock_data(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    db: Session = Depends(get_db)
):
    """
    Get historical stock data for a specific symbol.
    
    Path Parameters:
        symbol: Stock symbol (e.g., "INFY", "TCS")
        
    Query Parameters:
        days: Number of days to retrieve (1-365, default: 30)
        
    Returns:
        List of StockData objects with OHLCV data and calculated metrics
        
    Example:
        GET /data/INFY?days=30
        
        [
            {
                "symbol": "INFY",
                "date": "2026-03-25T00:00:00",
                "open_price": 1500.50,
                "high_price": 1520.00,
                "low_price": 1498.00,
                "close_price": 1515.00,
                "volume": 1000000,
                "daily_return": 1.31,
                "moving_avg_7": 1505.42,
                "moving_avg_30": 1510.15
            },
            ...
        ]
    """
    try:
        # Verify company exists
        company = db.query(Company).filter(
            Company.symbol.ilike(symbol)
        ).first()
        
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with symbol '{symbol}' not found"
            )
        
        # Get data for specified number of days
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        data = db.query(StockData).filter(
            StockData.symbol == symbol,
            StockData.date >= cutoff_date
        ).order_by(StockData.date.asc()).all()
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No stock data found for '{symbol}' in the last {days} days"
            )
        
        logger.info(f"Retrieved {len(data)} records for {symbol}")
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching stock data: {str(e)}"
        )


@router.get("/summary/{symbol}", response_model=StockSummarySchema)
async def get_stock_summary(
    symbol: str,
    db: Session = Depends(get_db)
):
    """
    Get 52-week summary statistics for a stock.
    
    Path Parameters:
        symbol: Stock symbol (e.g., "INFY")
        
    Returns:
        Summary with 52-week high, low, average close, and current price
        
    Example:
        GET /summary/INFY
        
        {
            "symbol": "INFY",
            "current_price": 1515.00,
            "week_52_high": 1600.00,
            "week_52_low": 1400.00,
            "avg_close": 1505.42,
            "latest_date": "2026-03-28T00:00:00"
        }
    """
    try:
        # Verify company exists
        company = db.query(Company).filter(
            Company.symbol.ilike(symbol)
        ).first()
        
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with symbol '{symbol}' not found"
            )
        
        # Get last 52 weeks of data (approximately 252 trading days)
        cutoff_date = datetime.utcnow() - timedelta(days=365)
        
        data = db.query(StockData).filter(
            StockData.symbol == symbol,
            StockData.date >= cutoff_date
        ).all()
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No 52-week data available for '{symbol}'"
            )
        
        close_prices = [d.close_price for d in data if d.close_price]
        
        if not close_prices:
            raise HTTPException(
                status_code=500,
                detail="No valid price data available"
            )
        
        latest = max(data, key=lambda x: x.date)

        recent_data = sorted(data, key=lambda x: x.date)[-30:]
        recent_closes = [float(d.close_price) for d in recent_data if d.close_price]
        daily_returns = []
        for idx in range(1, len(recent_closes)):
            prev_close = recent_closes[idx - 1]
            curr_close = recent_closes[idx]
            if prev_close:
                daily_returns.append((curr_close - prev_close) / prev_close)

        if len(daily_returns) > 1:
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((ret - mean_return) ** 2 for ret in daily_returns) / (len(daily_returns) - 1)
            volatility_30d = (variance ** 0.5) * sqrt(252) * 100
        else:
            volatility_30d = 0.0

        if volatility_30d < 20:
            volatility_band = "Low"
        elif volatility_30d < 35:
            volatility_band = "Moderate"
        else:
            volatility_band = "High"
        
        summary = {
            "symbol": symbol,
            "current_price": float(latest.close_price),
            "week_52_high": float(max(close_prices)),
            "week_52_low": float(min(close_prices)),
            "avg_close": float(sum(close_prices) / len(close_prices)),
            "volatility_30d": round(float(volatility_30d), 2),
            "volatility_band": volatility_band,
            "latest_date": latest.date
        }
        
        logger.info(f"Retrieved summary for {symbol}")
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating summary for {symbol}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating summary: {str(e)}"
        )


@router.get("/compare/", response_model=dict)
async def compare_stocks(
    symbol1: str = Query(..., description="First stock symbol"),
    symbol2: str = Query(..., description="Second stock symbol"),
    days: int = Query(30, ge=1, le=365, description="Number of days to compare"),
    db: Session = Depends(get_db)
):
    """
    Compare performance of two stocks.
    
    Query Parameters:
        symbol1: First stock symbol (required)
        symbol2: Second stock symbol (required)
        days: Number of days to compare (1-365, default: 30)
        
    Returns:
        Comparison object with data for both stocks
        
    Example:
        GET /compare?symbol1=INFY&symbol2=TCS&days=30
        
        {
            "symbol1": "INFY",
            "symbol2": "TCS",
            "comparison_period_days": 30,
            "stock1_data": [...],
            "stock2_data": [...],
            "symbol1_change_percent": 2.5,
            "symbol2_change_percent": -1.2,
            "outperformer": "INFY"
        }
    """
    try:
        # Verify both companies exist
        company1 = db.query(Company).filter(
            Company.symbol.ilike(symbol1)
        ).first()
        company2 = db.query(Company).filter(
            Company.symbol.ilike(symbol2)
        ).first()
        
        if not company1:
            raise HTTPException(
                status_code=404,
                detail=f"Company with symbol '{symbol1}' not found"
            )
        if not company2:
            raise HTTPException(
                status_code=404,
                detail=f"Company with symbol '{symbol2}' not found"
            )
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get data for both stocks
        data1 = db.query(StockData).filter(
            StockData.symbol == symbol1,
            StockData.date >= cutoff_date
        ).order_by(StockData.date.asc()).all()
        
        data2 = db.query(StockData).filter(
            StockData.symbol == symbol2,
            StockData.date >= cutoff_date
        ).order_by(StockData.date.asc()).all()
        
        if not data1 or not data2:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient data to compare {symbol1} and {symbol2}"
            )
        
        # Calculate performance metrics
        price1_start = data1[0].close_price
        price1_end = data1[-1].close_price
        change1 = ((price1_end - price1_start) / price1_start) * 100 if price1_start else 0
        
        price2_start = data2[0].close_price
        price2_end = data2[-1].close_price
        change2 = ((price2_end - price2_start) / price2_start) * 100 if price2_start else 0
        
        outperformer = symbol1 if change1 > change2 else symbol2
        
        comparison = {
            "symbol1": symbol1,
            "symbol2": symbol2,
            "comparison_period_days": days,
            "symbol1_start_price": float(price1_start),
            "symbol1_end_price": float(price1_end),
            "symbol1_change_percent": round(change1, 2),
            "symbol2_start_price": float(price2_start),
            "symbol2_end_price": float(price2_end),
            "symbol2_change_percent": round(change2, 2),
            "outperformer": outperformer,
            "performance_difference": round(abs(change1 - change2), 2)
        }
        
        logger.info(f"Compared {symbol1} and {symbol2}")
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing stocks: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error comparing stocks: {str(e)}"
        )


@router.get("/analytics/top-gainers", response_model=List[dict])
async def get_top_gainers(
    days: int = Query(1, ge=1, le=30, description="Period to check"),
    limit: int = Query(5, ge=1, le=20, description="Number of results"),
    db: Session = Depends(get_db)
):
    """
    Get top performing stocks in a given period.
    
    Query Parameters:
        days: Number of days to analyze (default: 1 for today vs yesterday)
        limit: Number of results to return (default: 5)
        
    Returns:
        List of top gaining stocks with performance metrics
        
    Example:
        GET /analytics/top-gainers?days=1&limit=5
        
        [
            {
                "symbol": "INFY",
                "start_price": 1500.50,
                "end_price": 1520.00,
                "change_percent": 1.31,
                "change_amount": 19.50
            },
            ...
        ]
    """
    try:
        # For days=1, compare today vs yesterday; for days>1, use normal range
        if days == 1:
            cutoff_date = datetime.utcnow() - timedelta(days=2)
        else:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all stocks and their performance
        stocks = db.query(Company.symbol).all()
        gainers = []
        
        for (symbol,) in stocks:
            data = db.query(StockData).filter(
                StockData.symbol == symbol,
                StockData.date >= cutoff_date
            ).order_by(StockData.date.asc()).all()
            
            if len(data) >= 2:
                start_price = data[0].close_price
                end_price = data[-1].close_price
                change = end_price - start_price
                change_percent = (change / start_price * 100) if start_price else 0
                
                gainers.append({
                    "symbol": symbol,
                    "start_price": float(start_price),
                    "end_price": float(end_price),
                    "change_percent": round(change_percent, 2),
                    "change_amount": round(change, 2)
                })
        
        # Sort by change percentage and return top N
        gainers = sorted(gainers, key=lambda x: x["change_percent"], reverse=True)
        
        logger.info(f"Retrieved top {limit} gainers for {days} day(s)")
        return gainers[:limit]
        
    except Exception as e:
        logger.error(f"Error fetching top gainers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching top gainers: {str(e)}"
        )


@router.get("/analytics/top-losers", response_model=List[dict])
async def get_top_losers(
    days: int = Query(1, ge=1, le=30, description="Period to check"),
    limit: int = Query(5, ge=1, le=20, description="Number of results"),
    db: Session = Depends(get_db)
):
    """
    Get worst performing stocks in a given period.
    
    Query Parameters:
        days: Number of days to analyze (default: 1 for today vs yesterday)
        limit: Number of results to return (default: 5)
        
    Returns:
        List of top losing stocks with performance metrics
        
    Example:
        GET /analytics/top-losers?days=1&limit=5
        
        [
            {
                "symbol": "WIPRO",
                "start_price": 350.00,
                "end_price": 340.00,
                "change_percent": -2.86,
                "change_amount": -10.00
            },
            ...
        ]
    """
    try:
        # For days=1, compare today vs yesterday; for days>1, use normal range
        if days == 1:
            cutoff_date = datetime.utcnow() - timedelta(days=2)
        else:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all stocks and their performance
        stocks = db.query(Company.symbol).all()
        losers = []
        
        for (symbol,) in stocks:
            data = db.query(StockData).filter(
                StockData.symbol == symbol,
                StockData.date >= cutoff_date
            ).order_by(StockData.date.asc()).all()
            
            if len(data) >= 2:
                start_price = data[0].close_price
                end_price = data[-1].close_price
                change = end_price - start_price
                change_percent = (change / start_price * 100) if start_price else 0
                
                losers.append({
                    "symbol": symbol,
                    "start_price": float(start_price),
                    "end_price": float(end_price),
                    "change_percent": round(change_percent, 2),
                    "change_amount": round(change, 2)
                })
        
        # Sort by change percentage (ascending for losers)
        losers = sorted(losers, key=lambda x: x["change_percent"])
        
        logger.info(f"Retrieved top {limit} losers for {days} day(s)")
        return losers[:limit]
        
    except Exception as e:
        logger.error(f"Error fetching top losers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching top losers: {str(e)}"
        )


@router.get("/analytics/correlation", response_model=dict)
async def get_stock_correlation(
    symbol1: str = Query(..., description="First stock symbol"),
    symbol2: str = Query(..., description="Second stock symbol"),
    days: int = Query(90, ge=30, le=365, description="Lookback window for correlation"),
    db: Session = Depends(get_db)
):
    """Get Pearson correlation between two stocks using aligned daily returns."""
    try:
        if symbol1.upper() == symbol2.upper():
            raise HTTPException(
                status_code=400,
                detail="Please choose two different stock symbols"
            )

        company1 = db.query(Company).filter(Company.symbol.ilike(symbol1)).first()
        company2 = db.query(Company).filter(Company.symbol.ilike(symbol2)).first()

        if not company1:
            raise HTTPException(status_code=404, detail=f"Company with symbol '{symbol1}' not found")
        if not company2:
            raise HTTPException(status_code=404, detail=f"Company with symbol '{symbol2}' not found")

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        data1 = db.query(StockData).filter(
            StockData.symbol == company1.symbol,
            StockData.date >= cutoff_date
        ).order_by(StockData.date.asc()).all()

        data2 = db.query(StockData).filter(
            StockData.symbol == company2.symbol,
            StockData.date >= cutoff_date
        ).order_by(StockData.date.asc()).all()

        if len(data1) < 2 or len(data2) < 2:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient data to calculate correlation for {symbol1} and {symbol2}"
            )

        closes1 = {row.date.date().isoformat(): float(row.close_price) for row in data1 if row.close_price}
        closes2 = {row.date.date().isoformat(): float(row.close_price) for row in data2 if row.close_price}

        common_dates = sorted(set(closes1.keys()) & set(closes2.keys()))
        if len(common_dates) < 3:
            raise HTTPException(
                status_code=404,
                detail="Not enough overlapping dates to calculate correlation"
            )

        returns1 = []
        returns2 = []
        for idx in range(1, len(common_dates)):
            prev_date = common_dates[idx - 1]
            curr_date = common_dates[idx]

            prev_close_1 = closes1[prev_date]
            curr_close_1 = closes1[curr_date]
            prev_close_2 = closes2[prev_date]
            curr_close_2 = closes2[curr_date]

            if prev_close_1 and prev_close_2:
                returns1.append((curr_close_1 - prev_close_1) / prev_close_1)
                returns2.append((curr_close_2 - prev_close_2) / prev_close_2)

        if len(returns1) < 2 or len(returns2) < 2:
            raise HTTPException(
                status_code=404,
                detail="Not enough valid return points to calculate correlation"
            )

        correlation = _pearson_correlation(returns1, returns2)

        if correlation >= 0.7:
            relationship = "Strong positive"
        elif correlation >= 0.3:
            relationship = "Moderate positive"
        elif correlation > -0.3:
            relationship = "Weak / neutral"
        elif correlation > -0.7:
            relationship = "Moderate negative"
        else:
            relationship = "Strong negative"

        return {
            "symbol1": company1.symbol,
            "symbol2": company2.symbol,
            "days": days,
            "correlation": round(float(correlation), 4),
            "relationship": relationship,
            "overlap_points": len(returns1)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating correlation for {symbol1} and {symbol2}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating correlation: {str(e)}"
        )


@router.get("/prediction/{symbol}", response_model=PredictionResponseSchema)
async def get_stock_prediction(
    symbol: str,
    history_days: int = Query(365, ge=120, le=1825, description="Lookback window for model training"),
    horizon: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
    db: Session = Depends(get_db)
):
    """Train backend XGBoost model and return forecast with reproducibility metadata."""
    try:
        company = db.query(Company).filter(Company.symbol.ilike(symbol)).first()
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with symbol '{symbol}' not found"
            )

        result = PredictionService.train_and_predict(
            db=db,
            symbol=company.symbol,
            history_days=history_days,
            horizon=horizon,
        )

        return {
            "symbol": result.symbol,
            "horizon": result.horizon,
            "predictions": result.predictions,
            "metadata": result.metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating prediction for {symbol}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating prediction: {str(e)}"
        )


@router.get("/realtime/{symbol}", response_model=dict)
async def get_realtime_quote(
    symbol: str,
    db: Session = Depends(get_db),
):
    """Realtime-ready quote endpoint kept dormant behind feature flag."""
    if not settings.realtime_feature_enabled:
        raise HTTPException(
            status_code=503,
            detail="Realtime feature is disabled. Enable REALTIME_FEATURE_ENABLED to activate.",
        )

    company = db.query(Company).filter(Company.symbol.ilike(symbol)).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company with symbol '{symbol}' not found")

    quote = realtime_quote_service.get_quote_snapshot(
        db=db,
        symbol=company.symbol,
        api_key=settings.alpha_vantage_api_key.strip(),
        cache_ttl_seconds=settings.realtime_cache_ttl_seconds,
    )
    return quote


@router.websocket("/ws/realtime/{symbol}")
async def stream_realtime_quote(websocket: WebSocket, symbol: str):
    """Realtime-ready stream endpoint kept dormant behind feature flag."""
    await websocket.accept()

    if not settings.realtime_feature_enabled:
        await websocket.send_json(
            {
                "type": "error",
                "detail": "Realtime feature is disabled. Enable REALTIME_FEATURE_ENABLED to activate.",
            }
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.symbol.ilike(symbol)).first()
        if not company:
            await websocket.send_json({"type": "error", "detail": f"Company with symbol '{symbol}' not found"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        while True:
            quote = realtime_quote_service.get_quote_snapshot(
                db=db,
                symbol=company.symbol,
                api_key=settings.alpha_vantage_api_key.strip(),
                cache_ttl_seconds=settings.realtime_cache_ttl_seconds,
            )

            await websocket.send_json(
                {
                    "type": "quote",
                    "symbol": company.symbol,
                    "payload": quote,
                }
            )
            await asyncio.sleep(max(1, settings.realtime_poll_seconds))
    except WebSocketDisconnect:
        logger.info(f"Realtime websocket disconnected for symbol {symbol}")
    finally:
        db.close()
