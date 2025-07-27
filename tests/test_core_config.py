import sys
from unittest.mock import mock_open
from unittest.mock import patch

import pytest

from core.config import load_config


class TestCoreConfig:
    """Test core configuration functionality"""

    @patch("core.config.config_path")
    @patch("builtins.open", new_callable=mock_open, read_data="")
    def test_load_config_empty_file(self, mock_file, mock_config_path):
        """Test load_config with empty configuration file"""
        mock_config_path.exists.return_value = True

        with pytest.raises(ValueError) as exc_info:
            load_config()

        assert "Empty configuration file" in str(exc_info.value)

    @patch("pathlib.Path.exists")
    def test_config_file_not_found(self, mock_exists):
        """Test configuration file not found scenario"""
        # Mock all path.exists() calls to return False
        mock_exists.return_value = False

        # This should trigger the FileNotFoundError on line 31
        with pytest.raises(FileNotFoundError) as exc_info:
            # We need to reload the module to trigger the initialization code
            if "core.config" in sys.modules:
                del sys.modules["core.config"]
            import core.config  # noqa: F401

        assert "Configuration file not found" in str(exc_info.value)
