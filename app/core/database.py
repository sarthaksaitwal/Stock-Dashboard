"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from pathlib import Path


def _resolve_database_url(url: str) -> str:
    """Resolve relative SQLite URLs to a stable absolute path in the project root."""
    if not url.startswith("sqlite:///"):
        return url

    if url.startswith("sqlite:///./"):
        relative_part = url.replace("sqlite:///./", "", 1)
        project_root = Path(__file__).resolve().parents[2]
        absolute_path = project_root / relative_part
        return f"sqlite:///{absolute_path.as_posix()}"

    return url


resolved_database_url = _resolve_database_url(settings.database_url)

# Create database engine
engine = create_engine(
    resolved_database_url,
    connect_args={"check_same_thread": False} if "sqlite" in resolved_database_url else {},
    echo=settings.debug
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency for getting a database session.
    Used in FastAPI endpoints.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from app.models import Base
    Base.metadata.create_all(bind=engine)
