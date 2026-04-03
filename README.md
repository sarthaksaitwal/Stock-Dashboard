# Stock Intelligence Dashboard

Stock Intelligence Dashboard is a FastAPI + React-style (Babel in browser) web app for exploring Indian stock trends with interactive charts, analytics, and short-horizon forecasts.

## What This Project Does

- Shows a welcome/intro dashboard on first load (no default stock preselected)
- Lets users pick a company and view:
	- session-day or rolling-range price charts
	- 52-week summary metrics and volatility band
	- correlation against another stock
	- top gainers and top losers
	- prediction curve with confidence bands
- Uses provider fallback flow so the app stays usable when primary API limits are hit
- Refreshes market data at startup and on a periodic background interval

## Current Data Strategy

### Provider flow

1. Alpha Vantage (primary)
2. NSELib (fallback)
3. Synthetic generation (fallback when live providers are unavailable)

### Refresh behavior

- At app startup, database tables are initialized and data is seeded/refreshed.
- During runtime, a scheduled background refresh runs every `DATA_UPDATE_INTERVAL` hours.
- Data is **not** repopulated on every request.

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Pydantic Settings
- DB: PostgreSQL (production), SQLite/PostgreSQL configurable for local
- Data/ML: pandas, numpy, xgboost
- Frontend: React (UMD + Babel), Chart.js, custom CSS
- Deployment: Docker, docker-compose, Render

## Core Features Implemented

- Company list and symbol search
- Session view and rolling window view (30/90 days)
- 52-week summary API and dashboard cards
- Correlation analytics API + gauge UI
- Top gainers/top losers analytics panels
- Forecast API (`/data/prediction/{symbol}`) with model metadata
- Provider status endpoint and user-facing data source remarks
- Loading shimmer for stock analysis section
- Responsive layout for desktop and mobile
- Welcome card shown only before stock selection

## API Docs

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

On deployed Render service:

- `https://stock-dashboard-z4hw.onrender.com/api/docs`
- `https://stock-dashboard-z4hw.onrender.com/api/redoc`

## Key API Routes

- `GET /companies`
- `GET /data/{symbol}?days=30|90`
- `GET /data/session/{symbol}?trade_date=YYYY-MM-DD&interval=5min`
- `GET /data/summary/{symbol}`
- `GET /data/analytics/top-gainers?days=1&limit=5`
- `GET /data/analytics/top-losers?days=1&limit=5`
- `GET /data/analytics/correlation?symbol1=INFY&symbol2=TCS&days=30`
- `GET /data/prediction/{symbol}?history_days=180&horizon=7`
- `GET /data/provider-status/{symbol}`
- `GET /health`

## Local Setup

### 1) Install dependencies

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt
```

### 2) Configure environment

Create/update `.env` (example fields):

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/stock_dashboard
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True
ALPHA_VANTAGE_API_KEY=
DATA_UPDATE_INTERVAL=24
LOG_LEVEL=INFO
```

### 3) Run app

```bash
python main.py
```

## Docker Compose

```bash
docker compose up --build
```

Optional one-time seed profile:

```bash
docker compose --profile seed up seed
```

## Project Structure (Relevant)

```text
stock-dashboard/
├── app/
│   ├── api/endpoints/
│   ├── core/database.py
│   ├── models/
│   └── services/prediction_service.py
├── config/settings.py
├── frontend/
│   ├── static/
│   │   ├── css/style.css
│   │   ├── js/app.js
│   │   └── favicon.svg
│   └── templates/index.html
├── data/models/
├── docker-compose.yml
├── main.py
└── README.md
```

## Notes

- If browser changes are not visible, hard refresh once after deployment due to static asset caching.
- Prediction endpoint requires enough usable historical rows after feature engineering.
