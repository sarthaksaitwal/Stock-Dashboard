"""Backend prediction service with feature engineering and XGBoost training."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models import StockData


@dataclass
class ForecastResult:
    """Container for prediction payload and metadata."""

    symbol: str
    horizon: int
    predictions: List[Dict]
    metadata: Dict


class PredictionService:
    """Train and serve reproducible backend forecasts with persisted artifacts."""

    PIPELINE_VERSION = "v1.0.0"
    MODEL_TYPE = "xgboost-regressor"
    FEATURE_NAMES = [
        "daily_return",
        "volume_change",
        "volatility_7",
        "ma_slope_7",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_hist",
    ]

    @staticmethod
    def _artifact_dir(symbol: str) -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "models" / symbol.lower() / PredictionService.PIPELINE_VERSION

    @staticmethod
    def _load_xgb_regressor():
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:
            raise RuntimeError("xgboost is required for backend prediction. Install dependencies from requirements.txt") from exc
        return XGBRegressor

    @staticmethod
    def _load_cached_model(symbol: str, history_days: int, data_as_of_date: str):
        artifact_dir = PredictionService._artifact_dir(symbol)
        model_path = artifact_dir / "model.json"
        metadata_path = artifact_dir / "metadata.json"

        if not model_path.exists() or not metadata_path.exists():
            return None, None

        try:
            with metadata_path.open("r", encoding="utf-8") as file:
                metadata = json.load(file)
        except Exception:
            return None, None

        if (
            metadata.get("pipeline_version") != PredictionService.PIPELINE_VERSION
            or metadata.get("history_days") != history_days
            or metadata.get("data_as_of_date") != data_as_of_date
        ):
            return None, None

        XGBRegressor = PredictionService._load_xgb_regressor()
        model = XGBRegressor()
        model.load_model(model_path)
        return model, metadata

    @staticmethod
    def _build_frame(rows: List[StockData]) -> pd.DataFrame:
        frame = pd.DataFrame(
            [
                {
                    "date": row.date,
                    "close": float(row.close_price),
                    "volume": float(row.volume),
                }
                for row in rows
                if row.close_price is not None and row.volume is not None
            ]
        )
        if frame.empty:
            return frame

        frame = frame.sort_values("date").reset_index(drop=True)
        frame["daily_return"] = frame["close"].pct_change()
        frame["volume_change"] = frame["volume"].pct_change()
        frame["volatility_7"] = frame["daily_return"].rolling(7).std()
        frame["ma_7"] = frame["close"].rolling(7).mean()
        frame["ma_slope_7"] = frame["ma_7"].diff()

        delta = frame["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        frame["rsi_14"] = 100 - (100 / (1 + rs))

        frame["ema_12"] = frame["close"].ewm(span=12, adjust=False).mean()
        frame["ema_26"] = frame["close"].ewm(span=26, adjust=False).mean()
        frame["macd"] = frame["ema_12"] - frame["ema_26"]
        frame["macd_signal"] = frame["macd"].ewm(span=9, adjust=False).mean()
        frame["macd_hist"] = frame["macd"] - frame["macd_signal"]

        frame["target_next_close"] = frame["close"].shift(-1)
        frame = frame.replace([np.inf, -np.inf], np.nan)
        return frame

    @staticmethod
    def _train_model(features: pd.DataFrame, target: pd.Series) -> tuple[object, Dict, float, int, int]:
        XGBRegressor = PredictionService._load_xgb_regressor()

        split_index = int(len(features) * 0.8)
        split_index = max(20, min(split_index, len(features) - 5))

        x_train = features.iloc[:split_index]
        y_train = target.iloc[:split_index]
        x_test = features.iloc[split_index:]
        y_test = target.iloc[split_index:]

        model = XGBRegressor(
            n_estimators=350,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="reg:squarederror",
            random_state=42,
        )
        model.fit(x_train, y_train)

        if len(x_test) > 0:
            test_pred = model.predict(x_test)
            residuals = y_test.to_numpy() - test_pred
            mae = float(np.mean(np.abs(residuals)))
            rmse = float(np.sqrt(np.mean(residuals**2)))
            residual_std = float(np.std(residuals))
            metrics = {"mae": round(mae, 4), "rmse": round(rmse, 4)}
            test_rows = len(x_test)
        else:
            train_pred = model.predict(x_train)
            residuals = y_train.to_numpy() - train_pred
            residual_std = float(np.std(residuals))
            metrics = {"mae": 0.0, "rmse": 0.0}
            test_rows = 0

        return model, metrics, residual_std, len(x_train), test_rows

    @staticmethod
    def _latest_feature_vector(frame: pd.DataFrame) -> pd.Series:
        valid = frame.dropna(subset=PredictionService.FEATURE_NAMES)
        if valid.empty:
            raise ValueError("Not enough valid feature rows for forecasting")
        return valid.iloc[-1][PredictionService.FEATURE_NAMES]

    @staticmethod
    def _engineer_next_row(history: pd.DataFrame, next_close: float, next_date: datetime) -> pd.DataFrame:
        next_volume = float(history["volume"].tail(5).mean())
        if not np.isfinite(next_volume):
            next_volume = float(history["volume"].iloc[-1])

        next_row = pd.DataFrame(
            [{"date": next_date, "close": float(next_close), "volume": next_volume}]
        )
        combined = pd.concat([history[["date", "close", "volume"]], next_row], ignore_index=True)
        return PredictionService._build_frame_from_minimal(combined)

    @staticmethod
    def _build_frame_from_minimal(minimal_frame: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, row in minimal_frame.iterrows():
            rows.append(
                type(
                    "Row",
                    (),
                    {
                        "date": row["date"],
                        "close_price": row["close"],
                        "volume": row["volume"],
                    },
                )
            )
        return PredictionService._build_frame(rows)

    @staticmethod
    def train_and_predict(
        db: Session,
        symbol: str,
        history_days: int = 365,
        horizon: int = 7,
    ) -> ForecastResult:
        cutoff_date = datetime.utcnow() - timedelta(days=history_days)
        rows = (
            db.query(StockData)
            .filter(StockData.symbol == symbol, StockData.date >= cutoff_date)
            .order_by(StockData.date.asc())
            .all()
        )

        frame = PredictionService._build_frame(rows)
        if frame.empty:
            raise ValueError(f"No historical data found for {symbol}")

        data_as_of_date = pd.to_datetime(frame["date"].iloc[-1]).date().isoformat()

        train_frame = frame.dropna(subset=PredictionService.FEATURE_NAMES + ["target_next_close"]).copy()
        if len(train_frame) < 40:
            raise ValueError("Insufficient data for model training; need at least 40 feature rows")

        model, cached_metadata = PredictionService._load_cached_model(
            symbol=symbol,
            history_days=history_days,
            data_as_of_date=data_as_of_date,
        )

        if model is not None and cached_metadata is not None:
            metrics = cached_metadata.get("metrics", {"mae": 0.0, "rmse": 0.0})
            residual_std = float(cached_metadata.get("residual_std", 0.0))
            train_rows = int(cached_metadata.get("training_rows", 0))
            test_rows = int(cached_metadata.get("test_rows", 0))
            trained_at = cached_metadata.get("trained_at", datetime.utcnow().isoformat())
            cache_hit = True
            model_path = Path(cached_metadata.get("artifact_path", ""))
        else:
            features = train_frame[PredictionService.FEATURE_NAMES]
            target = train_frame["target_next_close"]
            model, metrics, residual_std, train_rows, test_rows = PredictionService._train_model(features, target)
            cache_hit = False

            artifact_dir = PredictionService._artifact_dir(symbol)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            model_path = artifact_dir / "model.json"
            model.save_model(model_path)
            trained_at = datetime.utcnow().isoformat()

        history_frame = frame.copy()
        last_known_close = float(history_frame["close"].iloc[-1])
        last_known_date = pd.to_datetime(history_frame["date"].iloc[-1]).to_pydatetime()

        prediction_points = []
        for step in range(1, horizon + 1):
            latest_features = PredictionService._latest_feature_vector(history_frame)
            predicted_close = float(model.predict(np.array([latest_features.to_numpy()]))[0])
            predicted_close = max(predicted_close, 0.0)

            uncertainty = 1.96 * (residual_std if residual_std > 0 else max(1.0, abs(predicted_close * 0.01))) * np.sqrt(step)
            lower_95 = max(0.0, predicted_close - uncertainty)
            upper_95 = predicted_close + uncertainty

            prediction_points.append(
                {
                    "step": step,
                    "label": f"P+{step}",
                    "predicted_close": round(predicted_close, 2),
                    "lower_95": round(float(lower_95), 2),
                    "upper_95": round(float(upper_95), 2),
                }
            )

            next_date = last_known_date + timedelta(days=step)
            history_frame = PredictionService._engineer_next_row(history_frame, predicted_close, next_date)

        artifact_dir = PredictionService._artifact_dir(symbol)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = artifact_dir / "metadata.json"

        metadata = {
            "model_type": PredictionService.MODEL_TYPE,
            "pipeline_version": PredictionService.PIPELINE_VERSION,
            "trained_at": trained_at,
            "history_days": history_days,
            "feature_names": PredictionService.FEATURE_NAMES,
            "training_rows": train_rows,
            "test_rows": test_rows,
            "metrics": metrics,
            "artifact_path": str(model_path.as_posix()),
            "data_as_of_date": data_as_of_date,
            "residual_std": round(float(residual_std), 6),
            "cache_hit": cache_hit,
            "last_known_close": round(last_known_close, 2),
        }

        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2)

        return ForecastResult(
            symbol=symbol,
            horizon=horizon,
            predictions=prediction_points,
            metadata=metadata,
        )
