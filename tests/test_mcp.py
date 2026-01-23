"""Tests for OpenCollective MCP server."""

import json

import pytest

# Skip all tests if MCP not installed
pytest.importorskip("mcp")


@pytest.fixture
def mock_token(tmp_path, monkeypatch):
    """Create a mock token file."""
    token_dir = tmp_path / ".config" / "opencollective"
    token_dir.mkdir(parents=True)
    token_file = token_dir / "token.json"
    token_file.write_text(json.dumps({"access_token": "test_token"}))
    monkeypatch.setattr("opencollective.mcp_server.TOKEN_FILE", str(token_file))
    return str(token_file)


class TestMCPServer:
    """Tests for MCP server creation."""

    def test_create_server(self, mock_token):
        """Can create MCP server."""
        from opencollective.mcp_server import create_server

        server = create_server()
        assert server is not None
        assert server.name == "opencollective"

    def test_server_has_name(self, mock_token):
        """Server has correct name."""
        from opencollective.mcp_server import create_server

        server = create_server()
        assert server.name == "opencollective"


class TestMCPImports:
    """Tests for MCP module imports."""

    def test_has_weasyprint_flag(self):
        """Module tracks weasyprint availability."""
        from opencollective.mcp_server import HAS_MCP

        assert HAS_MCP is True

    def test_get_client_without_token_raises(self, tmp_path, monkeypatch):
        """get_client raises when no token file exists."""
        from opencollective.mcp_server import get_client

        monkeypatch.setattr(
            "opencollective.mcp_server.TOKEN_FILE",
            str(tmp_path / "nonexistent.json"),
        )

        with pytest.raises(ValueError, match="No token found"):
            get_client()

    def test_get_client_with_token(self, mock_token):
        """get_client returns client when token exists."""
        from opencollective.mcp_server import get_client

        client = get_client()
        assert client is not None
        assert client.access_token == "test_token"
