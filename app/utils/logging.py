import os
import sys
import logging
import platform
from logging.handlers import RotatingFileHandler

def setup_logging():
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO"))
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            RotatingFileHandler(
                "logs/bot.log", 
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            ),
            logging.StreamHandler()
        ]
    )
    
    # Set lower log level for some verbose libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Log system info
    logger = logging.getLogger(__name__)
    logger.info(f"Python version: {platform.python_version()}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Python path: {sys.executable}")
    logger.info(f"Environment: {'RENDER' if os.environ.get('RENDER') else 'LOCAL'}") 