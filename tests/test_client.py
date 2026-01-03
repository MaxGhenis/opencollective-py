"""Tests for OpenCollective client."""

import pytest
import responses
from opencollective import OpenCollectiveClient


API_URL = "https://api.opencollective.com/graphql/v2"


class TestOpenCollectiveClient:
    """Tests for the OpenCollective API client."""

    def test_client_init_with_token(self):
        """Client can be initialized with an access token."""
        client = OpenCollectiveClient(access_token="test_token")
        assert client.access_token == "test_token"

    def test_client_init_without_token_raises(self):
        """Client raises error without token."""
        with pytest.raises(ValueError, match="access_token is required"):
            OpenCollectiveClient()

    @responses.activate
    def test_get_collective(self):
        """Can fetch collective information."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "collective": {
                        "id": "abc123",
                        "slug": "policyengine",
                        "name": "PolicyEngine",
                        "description": "Computing public policy",
                        "currency": "USD",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        collective = client.get_collective("policyengine")

        assert collective["slug"] == "policyengine"
        assert collective["name"] == "PolicyEngine"
        assert collective["currency"] == "USD"

    @responses.activate
    def test_get_expenses(self):
        """Can fetch expenses for a collective."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 2,
                        "nodes": [
                            {
                                "id": "exp1",
                                "legacyId": 123,
                                "description": "Cloud services",
                                "amount": 10000,
                                "currency": "USD",
                                "status": "PAID",
                                "createdAt": "2025-01-01T00:00:00Z",
                                "payee": {"name": "Max Ghenis", "slug": "max-ghenis"},
                            },
                            {
                                "id": "exp2",
                                "legacyId": 124,
                                "description": "Travel",
                                "amount": 50000,
                                "currency": "USD",
                                "status": "PENDING",
                                "createdAt": "2025-01-02T00:00:00Z",
                                "payee": {"name": "Jane Doe", "slug": "jane-doe"},
                            },
                        ],
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.get_expenses("policyengine", limit=10)

        assert result["totalCount"] == 2
        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["description"] == "Cloud services"
        assert result["nodes"][0]["amount"] == 10000

    @responses.activate
    def test_get_expenses_with_status_filter(self):
        """Can filter expenses by status."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 1,
                        "nodes": [
                            {
                                "id": "exp2",
                                "legacyId": 124,
                                "description": "Travel",
                                "amount": 50000,
                                "currency": "USD",
                                "status": "PENDING",
                                "createdAt": "2025-01-02T00:00:00Z",
                                "payee": {"name": "Jane Doe", "slug": "jane-doe"},
                            },
                        ],
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.get_expenses("policyengine", status="PENDING")

        assert result["totalCount"] == 1
        assert result["nodes"][0]["status"] == "PENDING"

    @responses.activate
    def test_approve_expense(self):
        """Can approve a pending expense."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp2",
                        "legacyId": 124,
                        "description": "Travel",
                        "status": "APPROVED",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.approve_expense("exp2")

        assert result["status"] == "APPROVED"

    @responses.activate
    def test_reject_expense(self):
        """Can reject a pending expense."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp2",
                        "legacyId": 124,
                        "description": "Travel",
                        "status": "REJECTED",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.reject_expense("exp2", message="Invalid receipt")

        assert result["status"] == "REJECTED"

    @responses.activate
    def test_create_expense(self):
        """Can create a new expense."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp3",
                        "legacyId": 125,
                        "description": "Software subscription",
                        "amount": 2000,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Software subscription",
            amount_cents=2000,
        )

        assert result["description"] == "Software subscription"
        assert result["status"] == "DRAFT"

    @responses.activate
    def test_api_error_handling(self):
        """Client handles API errors gracefully."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "errors": [
                    {"message": "Unauthorized", "extensions": {"code": "UNAUTHORIZED"}}
                ]
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="invalid_token")

        with pytest.raises(Exception, match="API error"):
            client.get_collective("policyengine")

    @responses.activate
    def test_http_error_handling(self):
        """Client handles HTTP errors."""
        responses.add(
            responses.POST,
            API_URL,
            status=500,
        )

        client = OpenCollectiveClient(access_token="test_token")

        with pytest.raises(Exception):
            client.get_collective("policyengine")
