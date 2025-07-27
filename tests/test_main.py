from unittest.mock import patch

from fastapi.testclient import TestClient

from core.security import get_api_key
from main import app

client = TestClient(app)

# Test with valid API key


async def override_get_api_key_valid():
    return "valid_api_key"


# Test with invalid API key


async def override_get_api_key_invalid():
    from fastapi import HTTPException

    raise HTTPException(status_code=403, detail="Could not validate credentials")


class TestMainEndpoints:
    """Test main application endpoints"""

    def test_root_endpoint_success(self):
        """Test root endpoint with valid API key"""
        app.dependency_overrides[get_api_key] = override_get_api_key_valid
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Welcome to the ActualTap API"}
        app.dependency_overrides.clear()

    def test_root_endpoint_unauthorized(self):
        """Test root endpoint with invalid API key"""
        app.dependency_overrides[get_api_key] = override_get_api_key_invalid
        response = client.get("/")
        assert response.status_code == 403
        assert "Could not validate credentials" in response.json()["detail"]
        app.dependency_overrides.clear()

    def test_settings_endpoint_success(self):
        """Test settings endpoint with valid API key"""
        app.dependency_overrides[get_api_key] = override_get_api_key_valid

        response = client.get("/settings")
        assert response.status_code == 200
        # Just verify that response is valid JSON
        response_data = response.json()
        assert isinstance(response_data, dict)
        # Should contain some expected keys from settings
        assert "actual_backup_payee" in response_data or "account_mappings" in response_data
        app.dependency_overrides.clear()

    def test_settings_endpoint_unauthorized(self):
        """Test settings endpoint with invalid API key"""
        app.dependency_overrides[get_api_key] = override_get_api_key_invalid
        response = client.get("/settings")
        assert response.status_code == 403
        app.dependency_overrides.clear()

    def test_docs_endpoint_success(self):
        """Test docs endpoint with valid API key"""
        app.dependency_overrides[get_api_key] = override_get_api_key_valid
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        app.dependency_overrides.clear()

    def test_redoc_endpoint_success(self):
        """Test redoc endpoint with valid API key"""
        app.dependency_overrides[get_api_key] = override_get_api_key_valid
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        app.dependency_overrides.clear()

    def test_openapi_endpoint_success(self):
        """Test openapi.json endpoint with valid API key"""
        app.dependency_overrides[get_api_key] = override_get_api_key_valid
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        openapi_spec = response.json()
        assert "openapi" in openapi_spec
        assert "info" in openapi_spec
        app.dependency_overrides.clear()


class TestExceptionHandlers:
    """Test custom exception handlers"""

    def test_validation_exception_handler_date_format(self):
        """Test validation exception handler with date format error"""
        app.dependency_overrides[get_api_key] = override_get_api_key_valid

        invalid_transaction = {
            "account": "Test Account",
            "amount": 100.0,
            "date": "invalid-date-format",
            "payee": "Test Payee",
        }

        with patch("api.transactions.actual_service"):
            response = client.post("/transactions", json=invalid_transaction)
            assert response.status_code == 422
            # Should contain custom date format message
            detail = response.json()["detail"]
            assert any("Invalid date format" in str(error.get("msg", "")) for error in detail)

        app.dependency_overrides.clear()

    def test_http_exception_handler_request_body_error(self):
        """Test HTTP exception handler when request body cannot be read"""
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from main import http_exception_handler

        # Create a mock request that will fail when trying to read JSON
        mock_request = AsyncMock()
        mock_request.method = "POST"
        mock_request.url = "http://test/transactions"
        mock_request.json.side_effect = Exception("JSON parse error")

        # Create an HTTPException with status 400
        exc = HTTPException(status_code=400, detail="Test error")

        # Call the handler directly to test the exception path
        import asyncio

        async def run_test():
            result = await http_exception_handler(mock_request, exc)
            return result

        # This should trigger lines 102-104 in main.py
        result = asyncio.run(run_test())
        assert result.status_code == 400

    def test_http_exception_handler_400(self):
        """Test HTTP exception handler for 400 errors"""
        app.dependency_overrides[get_api_key] = override_get_api_key_valid

        with patch("api.transactions.actual_service") as mock_service:
            mock_service.add_transactions.side_effect = ValueError("Test error")

            transaction_data = {
                "account": "Test Account",
                "amount": 100.0,
                "date": "2024-01-01",
                "payee": "Test Payee",
            }

            response = client.post("/transactions", json=transaction_data)
            assert response.status_code == 400
            assert "Test error" in response.json()["detail"]

        app.dependency_overrides.clear()
