"""Tests for OpenCollective CLI."""

import json

import pytest
import responses
from click.testing import CliRunner

from opencollective.cli import cli

from .conftest import API_URL, UPLOAD_URL


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestApproveCommand:
    """Tests for oc approve command."""

    @responses.activate
    def test_approve_expense(self, runner, mock_token, monkeypatch):
        """Can approve a pending expense."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp-123",
                        "legacyId": 12345,
                        "description": "Test expense",
                        "status": "APPROVED",
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(cli, ["approve", "exp-123"])

        assert result.exit_code == 0
        assert "Approved expense #12345" in result.output
        assert "APPROVED" in result.output

    @responses.activate
    def test_approve_expense_by_legacy_id(self, runner, mock_token, monkeypatch):
        """Can approve using a numeric legacy ID."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp-123",
                        "legacyId": 295107,
                        "description": "Test expense",
                        "status": "APPROVED",
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(cli, ["approve", "295107"])

        assert result.exit_code == 0
        assert "Approved expense #295107" in result.output
        body = json.loads(responses.calls[0].request.body.decode())
        assert body["variables"]["expense"] == {"legacyId": 295107}

    @responses.activate
    def test_approve_expense_error(self, runner, mock_token, monkeypatch):
        """Handles approval errors gracefully."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={"errors": [{"message": "You don't have permission"}]},
            status=200,
        )

        result = runner.invoke(cli, ["approve", "exp-123"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestRejectCommand:
    """Tests for oc reject command."""

    @responses.activate
    def test_reject_expense(self, runner, mock_token, monkeypatch):
        """Can reject a pending expense."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp-456",
                        "legacyId": 67890,
                        "description": "Bad expense",
                        "status": "REJECTED",
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(cli, ["reject", "exp-456", "-m", "Missing receipt"])

        assert result.exit_code == 0
        assert "Rejected expense #67890" in result.output
        assert "REJECTED" in result.output

    @responses.activate
    def test_reject_expense_without_message(self, runner, mock_token, monkeypatch):
        """Can reject without a message."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp-789",
                        "legacyId": 11111,
                        "status": "REJECTED",
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(cli, ["reject", "exp-789"])

        assert result.exit_code == 0
        assert "Rejected expense #11111" in result.output


class TestMeCommand:
    """Tests for oc me command."""

    @responses.activate
    def test_me_command(self, runner, mock_token, monkeypatch):
        """Can show current user info."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        # Mock get_me
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "me": {"id": "user-1", "slug": "test-user", "name": "Test User"}
                }
            },
            status=200,
        )
        # Mock get_payout_methods
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "account": {
                        "payoutMethods": [
                            {"id": "pm-1", "type": "BANK_ACCOUNT"},
                            {"id": "pm-2", "type": "PAYPAL"},
                        ]
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(cli, ["me"])

        assert result.exit_code == 0
        assert "Test User" in result.output
        assert "@test-user" in result.output
        assert "BANK_ACCOUNT" in result.output


class TestDeleteCommand:
    """Tests for oc delete command."""

    @responses.activate
    def test_delete_expense(self, runner, mock_token, monkeypatch):
        """Can delete an expense."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"deleteExpense": {"id": "exp-del", "legacyId": 99999}}},
            status=200,
        )

        result = runner.invoke(cli, ["delete", "exp-del"])

        assert result.exit_code == 0
        assert "Deleted expense #99999" in result.output


class TestEditCommand:
    """Tests for oc edit command."""

    @responses.activate
    def test_edit_expense(self, runner, mock_token, monkeypatch):
        """Can edit basic expense fields."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "editExpense": {
                        "id": "exp-123",
                        "legacyId": 12345,
                        "description": "NYC Axiom trip",
                        "amount": 55952,
                        "currency": "USD",
                        "type": "RECEIPT",
                        "status": "PENDING",
                        "tags": ["travel", "axiom"],
                        "items": [],
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(
            cli,
            [
                "edit",
                "exp-123",
                "--description",
                "NYC Axiom trip",
                "-t",
                "travel",
                "-t",
                "axiom",
            ],
        )

        assert result.exit_code == 0
        assert "Updated expense #12345" in result.output
        body = json.loads(responses.calls[0].request.body.decode())
        assert body["variables"]["expense"]["description"] == "NYC Axiom trip"
        assert body["variables"]["expense"]["tags"] == ["travel", "axiom"]

    def test_edit_requires_a_field(self, runner, mock_token, monkeypatch):
        """Edit requires a field option."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        result = runner.invoke(cli, ["edit", "exp-123"])

        assert result.exit_code == 1
        assert "Nothing to edit" in result.output


class TestAddItemCommand:
    """Tests for oc add-item command."""

    @responses.activate
    def test_add_item(self, runner, mock_token, monkeypatch, tmp_path):
        """Can add a receipt line item to an existing expense."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)
        receipt = tmp_path / "taxi.pdf"
        receipt.write_bytes(b"taxi receipt")

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expense": {
                        "id": "exp-public",
                        "legacyId": 295107,
                        "description": "NYC Axiom trip",
                        "amount": 55952,
                        "currency": "USD",
                        "type": "RECEIPT",
                        "status": "PENDING",
                        "createdAt": "2026-04-24T00:00:00Z",
                        "payee": {"name": "Max Ghenis", "slug": "max-ghenis"},
                        "createdByAccount": {
                            "name": "Max Ghenis",
                            "slug": "max-ghenis",
                        },
                        "tags": ["travel"],
                        "items": [
                            {
                                "id": "item-train",
                                "description": "Amtrak outbound",
                                "amount": 13600,
                                "url": "https://example.com/train.pdf",
                                "incurredAt": "2026-04-23T00:00:00Z",
                            }
                        ],
                    }
                }
            },
            status=200,
        )
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {
                            "file": {
                                "id": "file-taxi",
                                "url": "https://example.com/taxi.pdf",
                            }
                        }
                    ]
                }
            },
            status=200,
        )
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "editExpense": {
                        "id": "exp-public",
                        "legacyId": 295107,
                        "description": "NYC Axiom trip",
                        "amount": 57822,
                        "currency": "USD",
                        "type": "RECEIPT",
                        "status": "PENDING",
                        "tags": ["travel"],
                        "items": [],
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(
            cli,
            [
                "add-item",
                "295107",
                "Taxi",
                "18.70",
                str(receipt),
                "--incurred-at",
                "2026-04-25",
            ],
        )

        assert result.exit_code == 0
        assert "Adding item to expense 295107 for $18.70" in result.output
        assert "Added item to expense #295107" in result.output
        body = json.loads(responses.calls[2].request.body.decode())
        items = body["variables"]["expense"]["items"]
        assert items[1]["description"] == "Taxi"
        assert items[1]["amount"] == 1870
        assert items[1]["url"] == "https://example.com/taxi.pdf"
        assert items[1]["incurredAt"] == "2026-04-25T00:00:00Z"


class TestRemoveItemCommand:
    """Tests for oc remove-item command."""

    @responses.activate
    def test_remove_item_by_index(self, runner, mock_token, monkeypatch):
        """Can remove a line item by 1-based index."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expense": {
                        "id": "exp-public",
                        "legacyId": 295107,
                        "description": "NYC Axiom trip",
                        "amount": 55952,
                        "currency": "USD",
                        "type": "RECEIPT",
                        "status": "PENDING",
                        "createdAt": "2026-04-24T00:00:00Z",
                        "payee": {"name": "Max Ghenis", "slug": "max-ghenis"},
                        "createdByAccount": {
                            "name": "Max Ghenis",
                            "slug": "max-ghenis",
                        },
                        "tags": ["travel"],
                        "items": [
                            {
                                "id": "item-train",
                                "description": "Amtrak outbound",
                                "amount": 13600,
                                "url": "https://example.com/train.pdf",
                                "incurredAt": "2026-04-23T00:00:00Z",
                            },
                            {
                                "id": "item-hotel",
                                "description": "Hotel",
                                "amount": 17418,
                                "url": "https://example.com/hotel.pdf",
                                "incurredAt": "2026-04-24T00:00:00Z",
                            },
                        ],
                    }
                }
            },
            status=200,
        )
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "editExpense": {
                        "id": "exp-public",
                        "legacyId": 295107,
                        "description": "NYC Axiom trip",
                        "amount": 42352,
                        "currency": "USD",
                        "type": "RECEIPT",
                        "status": "PENDING",
                        "tags": ["travel"],
                        "items": [],
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(cli, ["remove-item", "295107", "--index", "1"])

        assert result.exit_code == 0
        assert "Removed item from expense #295107" in result.output
        assert "Amtrak outbound" in result.output
        body = json.loads(responses.calls[1].request.body.decode())
        assert body["variables"]["expense"]["items"][0]["id"] == "item-hotel"

    def test_remove_item_requires_one_selector(self, runner, mock_token, monkeypatch):
        """remove-item requires exactly one selector."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)

        result = runner.invoke(
            cli, ["remove-item", "295107", "--index", "1", "--contains", "Amtrak"]
        )

        assert result.exit_code == 1
        assert "Provide exactly one selector" in result.output


class TestReimbursementCommand:
    """Tests for oc reimbursement command."""

    @responses.activate
    def test_decimal_amount_parsing_preserves_cents(
        self, runner, mock_token, monkeypatch, tmp_path
    ):
        """Amounts like 4.10 should be sent as 410 cents."""
        monkeypatch.setattr("opencollective.cli.TOKEN_FILE", mock_token)
        receipt = tmp_path / "receipt.pdf"
        receipt.write_bytes(b"receipt pdf")

        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"id": "user-1", "slug": "max-ghenis"}}},
            status=200,
        )
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"account": {"payoutMethods": [{"id": "pm-1"}]}}},
            status=200,
        )
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {"file": {"id": "file-1", "url": "https://example.com/r.pdf"}}
                    ]
                }
            },
            status=200,
        )
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-1",
                        "legacyId": 123,
                        "description": "Bus",
                        "amount": 410,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        result = runner.invoke(
            cli,
            [
                "reimbursement",
                "Bus",
                "4.10",
                str(receipt),
                "-c",
                "policyengine",
            ],
        )

        assert result.exit_code == 0
        assert "Submitting reimbursement for $4.10" in result.output
        create_body = json.loads(responses.calls[3].request.body.decode())
        assert create_body["variables"]["expense"]["items"][0]["amount"] == 410
