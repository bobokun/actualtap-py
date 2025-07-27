import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from core.security import get_api_key


class TestSecurity:
    """Test security and authentication functionality"""

    def test_get_api_key_valid(self):
        """Test API key validation with valid key"""

        async def run_test():
            with patch("core.security.settings") as mock_settings:
                mock_settings.api_key = "valid_api_key"

                result = await get_api_key("valid_api_key")
                assert result == "valid_api_key"

        asyncio.run(run_test())

    def test_get_api_key_invalid(self):
        """Test API key validation with invalid key"""

        async def run_test():
            with patch("core.security.settings") as mock_settings:
                mock_settings.api_key = "valid_api_key"

                with pytest.raises(HTTPException) as exc_info:
                    await get_api_key("invalid_api_key")

                assert exc_info.value.status_code == 403
                assert exc_info.value.detail == "Could not validate credentials"

        asyncio.run(run_test())

    def test_get_api_key_none(self):
        """Test API key validation with None key"""

        async def run_test():
            with patch("core.security.settings") as mock_settings:
                mock_settings.api_key = "valid_api_key"

                with pytest.raises(HTTPException) as exc_info:
                    await get_api_key(None)

                assert exc_info.value.status_code == 403
                assert exc_info.value.detail == "Could not validate credentials"

        asyncio.run(run_test())

    def test_get_api_key_empty_string(self):
        """Test API key validation with empty string"""

        async def run_test():
            with patch("core.security.settings") as mock_settings:
                mock_settings.api_key = "valid_api_key"

                with pytest.raises(HTTPException) as exc_info:
                    await get_api_key("")

                assert exc_info.value.status_code == 403
                assert exc_info.value.detail == "Could not validate credentials"

        asyncio.run(run_test())
