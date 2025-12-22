"""Logging configuration"""
import logging
import os
import colorlog


class ExternalLibraryFilter(logging.Filter):
    """Filter out noisy logs from external libraries"""
    
    def filter(self, record):
        msg = record.getMessage()
        # Filter out inotify event spam from watchdog
        if 'in-event' in msg.lower():
            return False
        return True


def setup_logging(level=None):
    """Setup colorful logging"""
    # Get log level from env var, default to INFO
    if level is None:
        level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)
    
    # Get root logger
    logger = logging.getLogger()
    
    # Remove all existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)-8s%(reset)s %(asctime)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            reset=True,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
            secondary_log_colors={},
            style="%",
        )
    )
    
    # Add filter to suppress ievent spam from watchdog
    handler.addFilter(ExternalLibraryFilter())
    
    logger.addHandler(handler)
    logger.setLevel(level)
    
    # Suppress watchdog's verbose inotify logs
    logging.getLogger('watchdog.observers.inotify_buffer').setLevel(logging.WARNING)
    
    return logger

def get_logger(name: str):
    """Get a logger instance"""
    return logging.getLogger(name)
