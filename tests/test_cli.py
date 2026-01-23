"""Tests for OpenCollective CLI."""

import json

import pytest
import responses
from click.testing import CliRunner

from opencollective.cli import cli

API_URL = "https://api.opencollective.com/graphql/v2"
UPLOAD_URL = "https://opencollective.com/api/graphql/v2"


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_token(tmp_path):
    """Create a mock token file."""
    token_dir = tmp_path / ".config" / "opencollective"
    token_dir.mkdir(parents=True)
    token_file = token_dir / "token.json"
    token_file.write_text(json.dumps({"access_token": "test_token"}))
    return str(token_file)


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
