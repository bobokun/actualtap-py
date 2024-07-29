import logging
from logging.handlers import RotatingFileHandler

from core.config import config_path


class MyLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logging()
        return cls._instance

    def _setup_logging(self):
        self.logger = logging.getLogger("ActualTap")
        self.logger.setLevel(logging.INFO)

        # File handler
        log_file_path = config_path.parent.joinpath("ActualTap.log")
        file_handler = RotatingFileHandler(log_file_path, maxBytes=1048576, backupCount=5)  # 1MB per file, with 5 backups
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def info(self, msg):
        self.logger.info(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)
