"""Pydantic schemas for stock data validation."""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class StockDataSchema(BaseModel):
    """Schema for stock data response."""
    
    symbol: str
    date: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    daily_return: Optional[float] = None
    moving_avg_7: Optional[float] = None
    moving_avg_30: Optional[float] = None
    
    class Config:
        from_attributes = True


class StockSummarySchema(BaseModel):
    """Schema for stock summary (52-week stats)."""
    
    symbol: str
    current_price: float
    week_52_high: float
    week_52_low: float
    avg_close: float
    volatility_30d: float
    volatility_band: str
    latest_date: datetime
    
    class Config:
        from_attributes = True


class PredictionPointSchema(BaseModel):
    """Single forecast point for prediction horizon."""

    step: int
    label: str
    predicted_close: float
    lower_95: float
    upper_95: float


class PredictionMetadataSchema(BaseModel):
    """Metadata about model version, features, and evaluation."""

    model_config = ConfigDict(protected_namespaces=())

    model_type: str
    pipeline_version: str
    trained_at: datetime
    history_days: int
    feature_names: List[str]
    training_rows: int
    test_rows: int
    metrics: dict
    artifact_path: str
    data_as_of_date: str
    residual_std: float
    cache_hit: bool


class PredictionResponseSchema(BaseModel):
    """Prediction response schema for stock forecast endpoint."""

    symbol: str
    horizon: int
    predictions: List[PredictionPointSchema]
    metadata: PredictionMetadataSchema
