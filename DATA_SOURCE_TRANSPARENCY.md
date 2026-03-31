# Data Source Transparency - Implementation Summary

## Current Status: ✅ COMPLETE

Your application uses a **fallback chain with explicit user messaging**:

```
Alpha Vantage (PRIMARY) 
  → yfinance (FALLBACK) 
  → Synthetic MOCK Data (LAST RESORT)
```

All steps include clear messaging so users know when they're viewing demonstration data.

---

## 1. BACKEND: Data Population Logging

**File:** `populate_database.py`

When populating the database, output shows:
```
2026-03-31 17:20:32,200 - WARNING - Alpha Vantage response missing
2026-03-31 17:20:32,202 - WARNING - Alpha Vantage unavailable for INFY. Trying yfinance fallback...
2026-03-31 17:20:33,969 - INFO - Generated 262 synthetic records for INFY
```

**Each stock logs:**
- Which provider was attempted (Alpha Vantage)
- When it failed, which provider was tried (yfinance)
- Final result: "Using synthetic MOCK data for demonstration"
- How many records were generated

---

## 2. BACKEND: API Response Headers

**File:** `app/api/endpoints/stocks.py` (Session Day endpoint)

For `/data/session/{symbol}` requests:

```python
# When using live API:
X-Session-Source: live_api
X-Session-Message: Live intraday data loaded from Alpha Vantage API.

# When using fallback:
X-Session-Source: fallback_daily
X-Session-Message: Using fallback session data for demonstration because 
                   Alpha Vantage intraday time series missing. 
                   This may include MOCK/simulated data.
```

---

## 3. FRONTEND: User-Facing Banner

**File:** `frontend/static/js/app.js`

When Session Day mode is active and fallback data is displayed:

```jsx
// Conditions for showing warning:
- viewMode === "session" (user selected Session Day)
- sessionStatus?.source === "fallback_daily" (fallback data)

// Visual styling:
- Tan background (#fff8e8)
- Brown text (#7a4a00)
- Clear warning message from X-Session-Message header
```

**User sees:**
```
⚠️ Using fallback session data for demonstration because 
   Alpha Vantage intraday time series missing. 
   This may include MOCK/simulated data.
```

---

## 4. Configuration

**File:** `.env`
```
ALPHA_VANTAGE_API_KEY=YT0ER2O5D265VKR7
```

**File:** `config/settings.py`
```python
alpha_vantage_api_key: str = ""  # Loaded from .env
```

---

## Current Behavior (2026-03-31)

**Data Sources Used:** All 10 stocks using MOCK/synthetic data

**Reason:** Alpha Vantage API returns "timeseries missing" for `.NS` format symbols

**What Users See:**
1. ✅ Charts render with realistic data
2. ✅ Warning banner shows on Session Day mode
3. ✅ Message clearly states: "This may include MOCK/simulated data"
4. ✅ Background logs show fallback chain attempts

---

## How to Get Real Alpha Vantage Data

1. Register at https://www.alphavantage.co
2. Get a valid API key
3. Update `.env`:
   ```
   ALPHA_VANTAGE_API_KEY=[YOUR_NEW_KEY]
   ```
4. Re-run: `python populate_database.py`
5. Verify logs show: `Retrieved XXX records from Alpha Vantage for INFY`

---

## Files Implementing Transparency

- ✅ `populate_database.py` - Logs each fallback attempt
- ✅ `config/settings.py` - Loads API key from environment
- ✅ `app/api/endpoints/stocks.py` - Adds response headers
- ✅ `main.py` - Exposes headers via CORS
- ✅ `frontend/static/js/app.js` - Displays warning banner
- ✅ `frontend/static/css/style.css` - Styles warning banner
- ✅ `.env` - Stores API key

---

## Demo Mode Notice

Current status: **DEMONSTRATION MODE**
- All data is deterministically generated from seed values
- Charts are realistic but synthetic
- Perfect for testing UI/UX without external dependencies
- Easy switch to real data when API key is valid
