"""Logging configuration."""

import logging
from config.settings import settings


def setup_logger(name: str) -> logging.Logger:
    """Configure and return logger instance."""
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.getLevelName(settings.log_level))
    
    # File handler
    fh = logging.FileHandler(settings.log_file)
    fh.setLevel(logging.getLevelName(settings.log_level))
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.getLevelName(settings.log_level))
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger
