"""
Main application entry point.
Stock Dashboard FastAPI Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from config.settings import settings
from app.core.database import init_db
from app.api.endpoints import companies_router, stocks_router
import logging
import logging.config
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATE_FILE = FRONTEND_DIR / "templates" / "index.html"

def _configure_logging() -> None:
    """Configure application and server logging to console + file."""
    configured_path = Path(settings.log_file)
    log_path = configured_path if configured_path.is_absolute() else (BASE_DIR / configured_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": settings.log_level,
                },
                "file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "level": settings.log_level,
                    "filename": str(log_path),
                    "encoding": "utf-8",
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": settings.log_level,
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["console", "file"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console", "file"],
                    "level": settings.log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console", "file"],
                    "level": settings.log_level,
                    "propagate": False,
                },
            },
        }
    )


_configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup and clean up on shutdown."""
    logger.info("Starting up application...")
    init_db()
    logger.info("Database initialized successfully")
    yield

# Create FastAPI app
app = FastAPI(
    title="Stock Dashboard API",
    description="A financial data platform for stock market analysis",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Source", "X-Session-Message"],
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Include routers
app.include_router(companies_router)
app.include_router(stocks_router)


@app.get("/")
async def root():
    """Root endpoint - serve index.html."""
    if TEMPLATE_FILE.exists():
        return FileResponse(str(TEMPLATE_FILE))
    return {"message": "Stock Dashboard API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Stock Dashboard API on {settings.api_host}:{settings.api_port}")
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
