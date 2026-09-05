from unittest.mock import patch

import pytest
from fastapi import HTTPException

from core.security import get_api_key


class TestSecurity:
    """Test security and authentication functionality"""

    @pytest.mark.asyncio
    async def test_get_api_key_valid(self):
        """Test API key validation with valid key"""
        with patch("core.security.settings") as mock_settings:
            mock_settings.api_key = "valid_api_key"
            result = await get_api_key("valid_api_key")
            assert result == "valid_api_key"

    @pytest.mark.parametrize("invalid_key", ["invalid_api_key", None, ""])
    @pytest.mark.asyncio
    async def test_get_api_key_invalid(self, invalid_key):
        """Test API key validation with invalid, None, or empty key"""
        with patch("core.security.settings") as mock_settings:
            mock_settings.api_key = "valid_api_key"
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(invalid_key)

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "Could not validate credentials"
