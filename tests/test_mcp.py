"""Tests for OpenCollective MCP server."""

import asyncio
import os
import tempfile
from unittest.mock import MagicMock

import pytest
import responses

# Skip all tests if MCP not installed
pytest.importorskip("mcp")

from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest

from .conftest import API_URL, UPLOAD_URL


@pytest.fixture(autouse=True)
def _patch_mcp_token(mock_token, monkeypatch):
    """Point the MCP server's TOKEN_FILE to the shared mock token."""
    monkeypatch.setattr("opencollective.mcp_server.TOKEN_FILE", mock_token)


def _get_tools(server):
    """Get list of tools from a server synchronously."""
    handler = server.request_handlers[ListToolsRequest]
    req = MagicMock()
    result = asyncio.run(handler(req))
    return result.root.tools


def _call_tool(server, name, arguments):
    """Call a tool on the server synchronously, returning content list."""
    handler = server.request_handlers[CallToolRequest]
    req = MagicMock()
    req.params = CallToolRequestParams(name=name, arguments=arguments)
    result = asyncio.run(handler(req))
    return result.root.content


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


class TestListToolsIncludesNewTools:
    """Tests that list_tools includes the new tools."""

    def test_list_tools_has_submit_multi_item_reimbursement(self):
        """list_tools includes submit_multi_item_reimbursement."""
        from opencollective.mcp_server import create_server

        server = create_server()
        tools = _get_tools(server)
        tool_names = [t.name for t in tools]
        assert "submit_multi_item_reimbursement" in tool_names

    def test_list_tools_has_get_expense_items(self):
        """list_tools includes get_expense_items."""
        from opencollective.mcp_server import create_server

        server = create_server()
        tools = _get_tools(server)
        tool_names = [t.name for t in tools]
        assert "get_expense_items" in tool_names

    def test_submit_multi_item_reimbursement_schema(self):
        """submit_multi_item_reimbursement has correct input schema."""
        from opencollective.mcp_server import create_server

        server = create_server()
        tools = _get_tools(server)

        tool = next(t for t in tools if t.name == "submit_multi_item_reimbursement")
        schema = tool.inputSchema
        assert "collective_slug" in schema["properties"]
        assert "description" in schema["properties"]
        assert "items" in schema["properties"]
        assert schema["properties"]["items"]["type"] == "array"
        assert "collective_slug" in schema["required"]
        assert "description" in schema["required"]
        assert "items" in schema["required"]

    def test_get_expense_items_schema(self):
        """get_expense_items has correct input schema."""
        from opencollective.mcp_server import create_server

        server = create_server()
        tools = _get_tools(server)

        tool = next(t for t in tools if t.name == "get_expense_items")
        schema = tool.inputSchema
        assert "expense_id" in schema["properties"]
        assert schema["properties"]["expense_id"]["type"] == "integer"
        assert "expense_id" in schema["required"]


class TestSubmitMultiItemReimbursement:
    """Tests for the submit_multi_item_reimbursement tool."""

    @responses.activate
    def test_submit_multi_item_reimbursement_success(self):
        """Can submit a multi-item reimbursement."""
        from opencollective.mcp_server import create_server

        # Mock get_me
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"id": "user-123", "slug": "max-ghenis"}}},
            status=200,
        )
        # Mock get_payout_methods
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "account": {
                        "payoutMethods": [{"id": "pm-123", "type": "BANK_ACCOUNT"}]
                    }
                }
            },
            status=200,
        )
        # Mock upload_file for item 1
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {
                            "file": {
                                "id": "file-1",
                                "url": "https://example.com/receipt1.pdf",
                            }
                        }
                    ]
                }
            },
            status=200,
        )
        # Mock upload_file for item 2
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {
                            "file": {
                                "id": "file-2",
                                "url": "https://example.com/receipt2.pdf",
                            }
                        }
                    ]
                }
            },
            status=200,
        )
        # Mock createExpense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-multi",
                        "legacyId": 50001,
                        "description": "Multi-item expense",
                        "amount": 15000,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        # Create temp receipt files
        tmp1 = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp1.write(b"receipt 1")
        tmp1.close()
        tmp2 = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp2.write(b"receipt 2")
        tmp2.close()

        try:
            server = create_server()
            result = _call_tool(
                server,
                "submit_multi_item_reimbursement",
                {
                    "collective_slug": "policyengine",
                    "description": "Multi-item expense",
                    "items": [
                        {
                            "amount_cents": 10000,
                            "description": "Hotel stay",
                            "receipt_file": tmp1.name,
                            "incurred_at": "2026-01-15",
                        },
                        {
                            "amount_cents": 5000,
                            "description": "Taxi fare",
                            "receipt_file": tmp2.name,
                            "incurred_at": "2026-01-16",
                        },
                    ],
                    "tags": ["travel"],
                },
            )

            # Should return success text
            assert len(result) == 1
            text = result[0].text
            assert "50001" in text
            assert "PENDING" in text
        finally:
            os.unlink(tmp1.name)
            os.unlink(tmp2.name)

    @responses.activate
    def test_submit_multi_item_reimbursement_with_currency(self):
        """Can submit multi-item reimbursement with explicit currency."""
        from opencollective.mcp_server import create_server

        # Mock get_me
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"slug": "max-ghenis"}}},
            status=200,
        )
        # Mock get_payout_methods
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "account": {
                        "payoutMethods": [{"id": "pm-1", "type": "BANK_ACCOUNT"}]
                    }
                }
            },
            status=200,
        )
        # Mock upload for single item
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {
                            "file": {
                                "id": "f1",
                                "url": "https://example.com/r.pdf",
                            }
                        }
                    ]
                }
            },
            status=200,
        )
        # Mock createExpense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-gbp",
                        "legacyId": 50002,
                        "description": "GBP expense",
                        "amount": 10000,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(b"receipt")
        tmp.close()

        try:
            server = create_server()
            result = _call_tool(
                server,
                "submit_multi_item_reimbursement",
                {
                    "collective_slug": "policyengine",
                    "description": "GBP expense",
                    "items": [
                        {
                            "amount_cents": 10000,
                            "description": "Item 1",
                            "receipt_file": tmp.name,
                            "incurred_at": "2026-02-01",
                        },
                    ],
                    "currency": "GBP",
                },
            )
            text = result[0].text
            assert "50002" in text

            # Verify currency was sent in the createExpense request
            create_req = responses.calls[-1].request.body.decode()
            assert "GBP" in create_req
        finally:
            os.unlink(tmp.name)

    def test_submit_multi_item_reimbursement_missing_receipt_file(self):
        """Returns error when receipt file does not exist."""
        from opencollective.mcp_server import create_server

        server = create_server()
        result = _call_tool(
            server,
            "submit_multi_item_reimbursement",
            {
                "collective_slug": "policyengine",
                "description": "Bad file",
                "items": [
                    {
                        "amount_cents": 1000,
                        "description": "Missing receipt",
                        "receipt_file": "/nonexistent/path/receipt.pdf",
                        "incurred_at": "2026-01-01",
                    },
                ],
            },
        )
        text = result[0].text
        assert "Error" in text


class TestGetExpenseItems:
    """Tests for the get_expense_items tool."""

    @responses.activate
    def test_get_expense_items_success(self):
        """Can retrieve expense items by legacy ID."""
        from opencollective.mcp_server import create_server

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expense": {
                        "id": "exp-abc",
                        "legacyId": 12345,
                        "description": "Travel expenses",
                        "status": "PENDING",
                        "items": [
                            {
                                "id": "item-1",
                                "description": "Hotel",
                                "amount": 10000,
                                "incurredAt": "2026-01-15T00:00:00Z",
                                "url": "https://example.com/hotel-receipt.pdf",
                            },
                            {
                                "id": "item-2",
                                "description": "Taxi",
                                "amount": 5000,
                                "incurredAt": "2026-01-16T00:00:00Z",
                                "url": "https://example.com/taxi-receipt.pdf",
                            },
                        ],
                    }
                }
            },
            status=200,
        )

        server = create_server()
        result = _call_tool(server, "get_expense_items", {"expense_id": 12345})
        text = result[0].text

        assert "Hotel" in text
        assert "Taxi" in text
        assert "$100.00" in text
        assert "$50.00" in text
        assert "hotel-receipt.pdf" in text
        assert "taxi-receipt.pdf" in text

    @responses.activate
    def test_get_expense_items_no_items(self):
        """Returns message when expense has no items."""
        from opencollective.mcp_server import create_server

        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expense": {
                        "id": "exp-empty",
                        "legacyId": 99999,
                        "description": "Empty expense",
                        "status": "DRAFT",
                        "items": [],
                    }
                }
            },
            status=200,
        )

        server = create_server()
        result = _call_tool(server, "get_expense_items", {"expense_id": 99999})
        text = result[0].text

        assert "No items" in text or "0 item" in text

    @responses.activate
    def test_get_expense_items_api_error(self):
        """Returns error message on API failure."""
        from opencollective.mcp_server import create_server

        responses.add(
            responses.POST,
            API_URL,
            json={"errors": [{"message": "Expense not found"}]},
            status=200,
        )

        server = create_server()
        result = _call_tool(server, "get_expense_items", {"expense_id": 0})
        text = result[0].text

        assert "Error" in text
