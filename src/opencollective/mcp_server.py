"""OpenCollective MCP Server.

Run with: python -m opencollective.mcp_server
Or add to Claude Code's MCP config.
"""

import json
import os
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

from .client import OpenCollectiveClient

TOKEN_FILE = os.path.expanduser("~/.config/opencollective/token.json")


def get_client() -> OpenCollectiveClient:
    """Get an authenticated client from saved token."""
    if not os.path.exists(TOKEN_FILE):
        raise ValueError(
            f"No token found at {TOKEN_FILE}. Run 'oc auth' to authenticate."
        )

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    return OpenCollectiveClient(access_token=token_data["access_token"])


def create_server() -> "Server":
    """Create and configure the MCP server."""
    if not HAS_MCP:
        raise ImportError("MCP not installed. Run: pip install opencollective[mcp]")

    server = Server("opencollective")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="submit_reimbursement",
                description=(
                    "Submit a reimbursement expense to OpenCollective. "
                    "Use when you paid out-of-pocket and need reimbursement. "
                    "Requires a receipt file (PDF, PNG, JPG, or HTML)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "collective": {
                            "type": "string",
                            "description": "Collective slug (e.g., 'policyengine')",
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the expense",
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount in dollars (e.g., 325.00)",
                        },
                        "receipt_file": {
                            "type": "string",
                            "description": "Path to receipt (PDF, PNG, JPG, HTML)",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags for categorization",
                        },
                    },
                    "required": ["collective", "description", "amount", "receipt_file"],
                },
            ),
            Tool(
                name="submit_invoice",
                description=(
                    "Submit an invoice expense to OpenCollective. "
                    "Use when billing for services (consulting, development). "
                    "No receipt required."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "collective": {
                            "type": "string",
                            "description": "Collective slug (e.g., 'policyengine')",
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the invoice",
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount in dollars (e.g., 5000.00)",
                        },
                        "invoice_file": {
                            "type": "string",
                            "description": "Optional path to invoice PDF",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags for categorization",
                        },
                    },
                    "required": ["collective", "description", "amount"],
                },
            ),
            Tool(
                name="list_expenses",
                description="List expenses for an OpenCollective collective.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "collective": {
                            "type": "string",
                            "description": "Collective slug (e.g., 'policyengine')",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["PENDING", "APPROVED", "PAID", "REJECTED"],
                            "description": "Filter by status",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max number of expenses to return",
                            "default": 20,
                        },
                    },
                    "required": ["collective"],
                },
            ),
            Tool(
                name="delete_expense",
                description="Delete a draft or pending expense you created.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "expense_id": {
                            "type": "string",
                            "description": "The expense ID to delete",
                        },
                    },
                    "required": ["expense_id"],
                },
            ),
            Tool(
                name="get_me",
                description="Get the current authenticated OpenCollective user.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_collective",
                description="Get information about an OpenCollective collective.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "slug": {
                            "type": "string",
                            "description": "Collective slug (e.g., 'policyengine')",
                        },
                    },
                    "required": ["slug"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            client = get_client()

            if name == "submit_reimbursement":
                amount_cents = int(arguments["amount"] * 100)
                expense = client.submit_reimbursement(
                    collective_slug=arguments["collective"],
                    description=arguments["description"],
                    amount_cents=amount_cents,
                    receipt_file=arguments["receipt_file"],
                    tags=arguments.get("tags"),
                )
                url = f"https://opencollective.com/{arguments['collective']}/expenses/{expense['legacyId']}"
                return [
                    TextContent(
                        type="text",
                        text=f"✓ Reimbursement submitted!\n"
                        f"  ID: {expense['legacyId']}\n"
                        f"  Amount: ${arguments['amount']:.2f}\n"
                        f"  Status: {expense['status']}\n"
                        f"  URL: {url}",
                    )
                ]

            elif name == "submit_invoice":
                amount_cents = int(arguments["amount"] * 100)
                expense = client.submit_invoice(
                    collective_slug=arguments["collective"],
                    description=arguments["description"],
                    amount_cents=amount_cents,
                    invoice_file=arguments.get("invoice_file"),
                    tags=arguments.get("tags"),
                )
                url = f"https://opencollective.com/{arguments['collective']}/expenses/{expense['legacyId']}"
                return [
                    TextContent(
                        type="text",
                        text=f"✓ Invoice submitted!\n"
                        f"  ID: {expense['legacyId']}\n"
                        f"  Amount: ${arguments['amount']:.2f}\n"
                        f"  Status: {expense['status']}\n"
                        f"  URL: {url}",
                    )
                ]

            elif name == "list_expenses":
                result = client.get_expenses(
                    arguments["collective"],
                    status=arguments.get("status"),
                    limit=arguments.get("limit", 20),
                )
                nodes = result.get("nodes", [])

                if not nodes:
                    return [TextContent(type="text", text="No expenses found.")]

                lines = [f"Found {len(nodes)} expense(s):\n"]
                for exp in nodes:
                    amount = exp.get("amount", 0) / 100
                    status = exp.get("status", "UNKNOWN")
                    desc = exp.get("description", "No description")
                    legacy_id = exp.get("legacyId", "?")
                    payee = exp.get("payee", {}).get("name", "Unknown")
                    lines.append(
                        f"  #{legacy_id} ${amount:.2f} - {desc}\n"
                        f"     Payee: {payee} | Status: {status}"
                    )

                return [TextContent(type="text", text="\n".join(lines))]

            elif name == "delete_expense":
                result = client.delete_expense(arguments["expense_id"])
                return [
                    TextContent(
                        type="text",
                        text=f"✓ Deleted expense #{result.get('legacyId')}",
                    )
                ]

            elif name == "get_me":
                me = client.get_me()
                methods = client.get_payout_methods(me["slug"])
                text = f"Logged in as: {me.get('name')} (@{me.get('slug')})"
                if methods:
                    text += "\n\nPayout methods:"
                    for m in methods:
                        text += f"\n  - {m['type']}: {m['id']}"
                return [TextContent(type="text", text=text)]

            elif name == "get_collective":
                collective = client.get_collective(arguments["slug"])
                return [
                    TextContent(
                        type="text",
                        text=f"Collective: {collective.get('name')}\n"
                        f"  Slug: {collective.get('slug')}\n"
                        f"  Currency: {collective.get('currency')}\n"
                        f"  Description: {collective.get('description', 'N/A')}",
                    )
                ]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


async def main():
    """Run the MCP server."""
    if not HAS_MCP:
        print("Error: MCP not installed. Run: pip install opencollective[mcp]")
        return

    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
