from unittest.mock import patch

from core.logs import MyLogger


class TestCoreLogger:
    """Test core logging functionality"""

    def test_logger_info(self):
        """Test logger info method"""
        logger = MyLogger()
        with patch.object(logger.logger, "info") as mock_info:
            logger.info("Test info message")
            mock_info.assert_called_once_with("Test info message")

    def test_logger_debug(self):
        """Test logger debug method"""
        logger = MyLogger()
        with patch.object(logger.logger, "debug") as mock_debug:
            logger.debug("Test debug message")
            mock_debug.assert_called_once_with("Test debug message")

    def test_logger_warning(self):
        """Test logger warning method"""
        logger = MyLogger()
        with patch.object(logger.logger, "warning") as mock_warning:
            logger.warning("Test warning message")
            mock_warning.assert_called_once_with("Test warning message")

    def test_logger_critical(self):
        """Test logger critical method"""
        logger = MyLogger()
        with patch.object(logger.logger, "critical") as mock_critical:
            logger.critical("Test critical message")
            mock_critical.assert_called_once_with("Test critical message")
