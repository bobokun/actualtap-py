from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.security import get_api_key
from main import app

client = TestClient(app)


async def override_get_api_key():
    return "test_api_key"


@pytest.fixture
def mock_actual_service():
    with patch("api.transactions.actual_service") as mock:
        yield mock


def test_add_single_transaction_success(mock_actual_service):
    """
    Tests that a single valid transaction is successfully added.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        transaction_data = {
            "account": "Test Account",
            "amount": 100.0,
            "date": "2024-01-01",
            "payee": "Test Payee",
            "notes": "Test notes",
            "cleared": True,
        }
        response = client.post("/transactions", json=transaction_data)
        assert response.status_code == 200
        assert response.json() == {"message": "Transactions added successfully"}

        # Verify the service was called with the correct, inverted amount
        mock_actual_service.add_transactions.assert_called_once()
        called_with = mock_actual_service.add_transactions.call_args[0][0]
        assert len(called_with) == 1
        assert called_with[0].amount == Decimal("-100.0")
    finally:
        app.dependency_overrides.clear()


def test_add_batch_transactions_success(mock_actual_service):
    """
    Tests that a batch of valid transactions are successfully added.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        transactions_data = [
            {
                "account": "Test Account 1",
                "amount": 100.0,
                "date": "2024-01-01",
                "payee": "Test Payee 1",
                "notes": "Test notes 1",
                "cleared": True,
            },
            {
                "account": "Test Account 2",
                "amount": 200.0,
                "date": "2024-01-02",
                "payee": "Test Payee 2",
                "notes": "Test notes 2",
                "cleared": False,
            },
        ]
        response = client.post("/transactions", json=transactions_data)
        assert response.status_code == 200
        assert response.json() == {"message": "Transactions added successfully"}

        # Verify the service was called with the correct, inverted amounts
        mock_actual_service.add_transactions.assert_called_once()
        called_with = mock_actual_service.add_transactions.call_args[0][0]
        assert len(called_with) == 2
        assert called_with[0].amount == Decimal("-100.0")
        assert called_with[1].amount == Decimal("-200.0")
    finally:
        app.dependency_overrides.clear()


def test_add_transactions_empty_body(mock_actual_service):
    """
    Tests that a 400 error is returned when no body is provided.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        response = client.post("/transactions", json=None)
        assert response.status_code == 422
        assert "Field required" in response.json()["detail"][0]["msg"]
        mock_actual_service.add_transactions.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_add_transactions_empty_list(mock_actual_service):
    """
    Tests that a 400 error is returned when an empty list is provided.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        response = client.post("/transactions", json=[])
        assert response.status_code == 400
        assert "No transactions provided" in response.json()["detail"]
        mock_actual_service.add_transactions.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_add_transactions_validation_error(mock_actual_service):
    """
    Tests that a 422 error is returned for an invalid transaction payload.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        invalid_transaction = {
            "account": "Test Account",
            "amount": "not-a-number",  # Invalid data type
            "date": "2024-01-01",
            "payee": "Test Payee",
        }
        response = client.post("/transactions", json=invalid_transaction)
        assert response.status_code == 422
        mock_actual_service.add_transactions.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_add_transactions_service_value_error(mock_actual_service):
    """
    Tests that a 400 error is returned when the service raises a ValueError.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        mock_actual_service.add_transactions.side_effect = ValueError("Service Error")
        transaction_data = {
            "account": "Test Account",
            "amount": 100.0,
            "date": "2024-01-01",
            "payee": "Test Payee",
        }
        response = client.post("/transactions", json=transaction_data)
        assert response.status_code == 400
        assert "Service Error" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_add_transactions_service_generic_exception(mock_actual_service):
    """
    Tests that a 500 error is returned when the service raises a generic exception.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        mock_actual_service.add_transactions.side_effect = Exception("Generic Error")
        transaction_data = {
            "account": "Test Account",
            "amount": 100.0,
            "date": "2024-01-01",
            "payee": "Test Payee",
        }
        response = client.post("/transactions", json=transaction_data)
        assert response.status_code == 500
        assert "Generic Error" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_add_transaction_with_zero_amount(mock_actual_service):
    """
    Tests adding a transaction with a zero amount.
    """
    app.dependency_overrides[get_api_key] = override_get_api_key
    try:
        transaction_data = {"account": "Test Account", "amount": 0, "date": "2024-01-01", "payee": "Test Payee"}
        response = client.post("/transactions", json=transaction_data)
        assert response.status_code == 200
        # The inverted amount should be 0
        mock_actual_service.add_transactions.assert_called_once()
        called_with = mock_actual_service.add_transactions.call_args[0][0]
        assert called_with[0].amount == Decimal("0")
    finally:
        app.dependency_overrides.clear()
