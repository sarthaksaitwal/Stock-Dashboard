"""Realtime quote service with Alpha Vantage primary source and DB fallback."""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import requests
import logging
from sqlalchemy.orm import Session
from app.models import StockData

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

logger = logging.getLogger(__name__)


class RealtimeQuoteService:
    """Fetches near-realtime price snapshots with short-lived in-memory caching."""

    def __init__(self) -> None:
        self._cache: Dict[str, Tuple[datetime, dict]] = {}

    def _provider_symbol(self, symbol: str) -> str:
        return ALPHA_VANTAGE_SYMBOLS.get(symbol.upper(), f"{symbol.upper()}.BSE")

    def _from_cache(self, cache_key: str) -> Optional[dict]:
        item = self._cache.get(cache_key)
        if not item:
            return None
        expires_at, payload = item
        if datetime.utcnow() >= expires_at:
            self._cache.pop(cache_key, None)
            logger.debug("Realtime cache expired for %s", cache_key)
            return None
        logger.debug("Realtime cache hit for %s", cache_key)
        return payload

    def _put_cache(self, cache_key: str, payload: dict, ttl_seconds: int) -> None:
        self._cache[cache_key] = (datetime.utcnow() + timedelta(seconds=ttl_seconds), payload)

    def _fetch_alpha_quote(self, symbol: str, api_key: str) -> Tuple[Optional[dict], Optional[str]]:
        logger.info("Fetching Alpha Vantage realtime quote for %s", symbol.upper())
        try:
            response = requests.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": self._provider_symbol(symbol),
                    "apikey": api_key,
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()

            if "Note" in payload:
                logger.warning("Alpha Vantage rate limit reached for %s", symbol.upper())
                return None, "Alpha Vantage rate limit reached"
            if "Error Message" in payload:
                logger.warning("Alpha Vantage returned error response for %s", symbol.upper())
                return None, "Alpha Vantage returned error response"

            quote = payload.get("Global Quote") or {}
            price_raw = quote.get("05. price")
            if not price_raw:
                logger.warning("Alpha Vantage quote payload missing price for %s", symbol.upper())
                return None, "Alpha Vantage quote payload missing price"

            price = float(price_raw)
            change_percent_raw = quote.get("10. change percent", "").replace("%", "").strip()
            change_percent = float(change_percent_raw) if change_percent_raw else None
            latest_trading_day = quote.get("07. latest trading day")

            return {
                "symbol": symbol.upper(),
                "price": round(price, 4),
                "change_percent": round(change_percent, 4) if change_percent is not None else None,
                "latest_trading_day": latest_trading_day,
                "as_of": datetime.utcnow().isoformat(),
                "source": "alpha_vantage",
                "is_delayed": True,
                "message": "Realtime-prep quote from Alpha Vantage GLOBAL_QUOTE.",
            }, None
        except requests.RequestException:
            logger.exception("Alpha Vantage request failed for %s", symbol.upper())
            return None, "Alpha Vantage request failed"
        except (TypeError, ValueError):
            logger.exception("Alpha Vantage response parse failed for %s", symbol.upper())
            return None, "Alpha Vantage response parse failed"

    def _latest_db_quote(self, db: Session, symbol: str, reason: str) -> Optional[dict]:
        logger.info("Using DB fallback quote for %s because %s", symbol.upper(), reason)
        latest = db.query(StockData).filter(
            StockData.symbol == symbol.upper()
        ).order_by(StockData.date.desc()).first()

        if not latest or latest.close_price is None:
            return None

        return {
            "symbol": symbol.upper(),
            "price": round(float(latest.close_price), 4),
            "change_percent": None,
            "latest_trading_day": latest.date.date().isoformat(),
            "as_of": datetime.utcnow().isoformat(),
            "source": "db_fallback",
            "is_delayed": True,
            "message": f"Fallback quote from stored DB close because {reason}.",
        }

    def get_quote_snapshot(
        self,
        db: Session,
        symbol: str,
        api_key: str,
        cache_ttl_seconds: int,
    ) -> dict:
        cache_key = symbol.upper()
        cached = self._from_cache(cache_key)
        if cached:
            return cached

        reason = "ALPHA_VANTAGE_API_KEY not configured"
        payload = None

        if api_key:
            payload, alpha_reason = self._fetch_alpha_quote(symbol, api_key)
            if payload:
                self._put_cache(cache_key, payload, max(1, cache_ttl_seconds))
                logger.info("Realtime quote source for %s: alpha_vantage", symbol.upper())
                return payload
            reason = alpha_reason or "Alpha Vantage quote unavailable"

        payload = self._latest_db_quote(db, symbol, reason)
        if not payload:
            logger.error("No realtime quote available for %s", symbol.upper())
            payload = {
                "symbol": symbol.upper(),
                "price": None,
                "change_percent": None,
                "latest_trading_day": None,
                "as_of": datetime.utcnow().isoformat(),
                "source": "unavailable",
                "is_delayed": True,
                "message": f"No quote available: {reason}, and DB has no historical fallback.",
            }
        else:
            logger.info("Realtime quote source for %s: db_fallback", symbol.upper())

        self._put_cache(cache_key, payload, max(1, cache_ttl_seconds))
        return payload
