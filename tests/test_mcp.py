"""Tests for OpenCollective MCP server."""

import pytest

# Skip all tests if MCP not installed
pytest.importorskip("mcp")


@pytest.fixture(autouse=True)
def _patch_mcp_token(mock_token, monkeypatch):
    """Point the MCP server's TOKEN_FILE to the shared mock token."""
    monkeypatch.setattr("opencollective.mcp_server.TOKEN_FILE", mock_token)


class TestMCPServer:
    """Tests for MCP server creation."""

    def test_create_server(self):
        """Can create MCP server."""
        from opencollective.mcp_server import create_server

        server = create_server()
        assert server is not None
        assert server.name == "opencollective"

    def test_server_has_name(self):
        """Server has correct name."""
        from opencollective.mcp_server import create_server

        server = create_server()
        assert server.name == "opencollective"


class TestMCPImports:
    """Tests for MCP module imports."""

    def test_has_mcp_flag(self):
        """Module tracks MCP availability."""
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

    def test_get_client_with_token(self):
        """get_client returns client when token exists."""
        from opencollective.mcp_server import get_client

        client = get_client()
        assert client is not None
        assert client.access_token == "test_token"
