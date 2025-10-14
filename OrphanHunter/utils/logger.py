"""Logging utilities for System Mapper."""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal

class LogSignals(QObject):
    """Signals for log messages."""
    log_message = pyqtSignal(str, str)  # message, level

class Logger:
    """Enhanced logger with GUI integration."""
    
    def __init__(self, log_file: Optional[str] = None):
        self.signals = LogSignals()
        self.log_file = Path(log_file) if log_file else Path("system-mapper.log")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup file logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('SystemMapper')
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)
        self.signals.log_message.emit(message, "DEBUG")
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
        self.signals.log_message.emit(message, "INFO")
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
        self.signals.log_message.emit(message, "WARNING")
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
        self.signals.log_message.emit(message, "ERROR")
    
    def critical(self, message: str):
        """Log critical message."""
        self.logger.critical(message)
        self.signals.log_message.emit(message, "CRITICAL")
    
    def separator(self):
        """Log a separator line."""
        sep = "=" * 80
        self.logger.info(sep)
        self.signals.log_message.emit(sep, "INFO")

