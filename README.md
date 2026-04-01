# 📈 Stock Dashboard - Financial Data Intelligence Platform

A modern, scalable stock market data platform built with Python, FastAPI, and real-time data visualization.

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Features](#features)
- [Development](#development)

## 🎯 Overview

Stock Dashboard is a comprehensive financial data platform that:
- Collects and processes real stock market data
- Provides REST APIs for data access
- Visualizes market insights through interactive dashboards
- Calculates technical metrics and indicators

## 🛠 Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Data Processing**: Pandas, NumPy
- **Data Source**: yfinance
- **Frontend**: HTML5, JavaScript, Chart.js
- **Deployment**: Docker (optional)

## 📁 Project Structure

```
stock-dashboard/
├── app/                          # Main application package
│   ├── api/                      # API endpoints
│   │   └── endpoints/            # Route definitions
│   ├── models/                   # Database models (ORM)
│   ├── schemas/                  # Pydantic validation schemas
│   ├── services/                 # Business logic
│   ├── core/                     # Core functionality (database, config)
│   └── utils/                    # Utility functions
├── frontend/                     # Frontend application
│   ├── static/                   # CSS, JS, images
│   │   ├── css/
│   │   └── js/
│   └── templates/                # HTML templates
├── config/                       # Configuration management
├── tests/                        # Unit and integration tests
├── data/                         # Data storage
├── logs/                         # Application logs
├── main.py                       # Application entry point
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

## 🚀 Installation

### Prerequisites
- Python 3.8+
- pip

### Step 1: Clone and Setup

```bash
# Navigate to project
cd stock-dashboard

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (optional)
```

## ⚙️ Configuration

The application uses environment variables via `.env` file:

```env
# Database
DATABASE_URL=sqlite:///./stock_data.db

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True

# Stock Configuration
STOCKS_TO_TRACK=INFY,TCS,WIPRO,RELIANCE
DATE_RANGE_DAYS=100

# Logging
LOG_LEVEL=INFO
```

## 🎮 Running the Application

```bash
# Make sure virtual environment is activated
python main.py

# Or use uvicorn directly
uvicorn main:app --reload
```

Access the application:
- 📊 API: http://localhost:8000
- 📚 API Docs: http://localhost:8000/docs
- 🪄 ReDoc: http://localhost:8000/redoc

## 📡 API Endpoints

### Companies
- `GET /companies` - List all tracked companies
- `GET /company/{symbol}` - Get company details

### Stock Data
- `GET /data/{symbol}` - Get last 30 days of stock data
- `GET /summary/{symbol}` - Get 52-week statistics

### Compare & Analytics
- `GET /compare?symbol1=INFY&symbol2=TCS` - Compare two stocks
- `GET /top-gainers` - Top performing stocks
- `GET /top-losers` - Worst performing stocks

## ✨ Features

### Core Features ✅
- [x] Real-time stock data fetching
- [x] Data cleaning and validation
- [x] Technical indicators (MA7, MA30, Daily Return)
- [x] REST API with pagination
- [x] Swagger/OpenAPI documentation

### Bonus Features (In Progress)
- [ ] Interactive dashboard with Chart.js
- [ ] Stock comparison visualization
- [ ] Top gainers/losers analytics
- [ ] Price prediction with ML
- [ ] Docker containerization
- [ ] Cloud deployment

## 🔧 Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black app/

# Check lint
flake8 app/

# Type checking
mypy app/
```

### Database Migrations

```bash
# Initialize alembic
alembic init migrations

# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head
```

## 📝 License

MIT License

## 📞 Support

For issues or questions, contact: support@jarnox.com

---

**Built with ❤️ for the Jarnox Internship Program**
