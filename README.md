# opencollective-py

A Python client for the [OpenCollective](https://opencollective.com) GraphQL API.

## Installation

```bash
# Basic installation
pip install git+https://github.com/MaxGhenis/opencollective-py.git

# With PDF conversion support (for HTML receipts)
pip install "opencollective[pdf] @ git+https://github.com/MaxGhenis/opencollective-py.git"
```

## Quick start

### Authentication

First, create an OAuth2 application at https://opencollective.com/applications.

```python
from opencollective import OAuth2Handler, OpenCollectiveClient

# Set up OAuth2 handler
auth = OAuth2Handler(
    client_id="your_client_id",
    client_secret="your_client_secret",
    token_file="~/.config/opencollective/token.json"  # Optional: persist token
)

# Get authorization URL (redirect user here)
auth_url = auth.get_authorization_url(scope="expenses")

# After user authorizes, exchange code for token
token_data = auth.exchange_code(authorization_code)

# Create client with access token
client = OpenCollectiveClient(access_token=token_data["access_token"])
```

## Submitting expenses

### Reimbursement vs invoice: when to use which

| Type | Use when... | Receipt required? |
|------|-------------|-------------------|
| **Reimbursement** | You paid out-of-pocket and need to be paid back | Yes |
| **Invoice** | You're billing for services/work rendered | No (optional) |

**Examples:**
- Membership dues you paid → **Reimbursement** (you have a receipt)
- Conference registration → **Reimbursement** (you have a receipt)
- Monthly consulting fee → **Invoice** (you're billing for work)
- Software development work → **Invoice** (you're billing for work)

### Submit a reimbursement (recommended)

Use this when you paid for something and need to be reimbursed:

```python
expense = client.submit_reimbursement(
    collective_slug="policyengine",
    description="NASI Membership Dues 2026",
    amount_cents=32500,  # $325.00
    receipt_file="/path/to/receipt.pdf",  # or .png, .jpg, .html
    tags=["membership", "professional development"]
)
print(f"Created: https://opencollective.com/policyengine/expenses/{expense['legacyId']}")
```

Features:
- Auto-detects your account from the OAuth token
- Auto-selects your first payout method
- Converts HTML receipts to PDF automatically (requires `opencollective[pdf]`)
- Uploads receipt and attaches it to the expense

### Submit an invoice

Use this when billing for services (no receipt needed):

```python
expense = client.submit_invoice(
    collective_slug="policyengine",
    description="January 2026 Consulting",
    amount_cents=500000,  # $5,000.00
    tags=["consulting"]
)
```

### Low-level expense creation

For more control, use the lower-level `create_expense()` method:

```python
# First upload receipt if needed
file_info = client.upload_file("/path/to/receipt.pdf")

# Create expense with full control
expense = client.create_expense(
    collective_slug="policyengine",
    payee_slug="max-ghenis",
    description="Cloud services - January 2026",
    amount_cents=10000,
    expense_type="RECEIPT",  # or "INVOICE"
    payout_method_id="your-payout-method-id",
    attachment_urls=[file_info["url"]],
    tags=["cloud", "infrastructure"],
)
```

## Managing expenses

```python
# Get your account info
me = client.get_me()
print(f"Logged in as: {me['name']} (@{me['slug']})")

# Get your payout methods
methods = client.get_payout_methods(me['slug'])
for m in methods:
    print(f"  {m['type']}: {m['id']}")

# Get recent expenses
expenses = client.get_expenses("policyengine", limit=50)
print(f"Found {expenses['totalCount']} expenses")

# Get pending expenses only
pending = client.get_pending_expenses("policyengine")

# Approve an expense (requires admin permissions)
client.approve_expense(expense_id="abc123")

# Reject an expense with a message
client.reject_expense(expense_id="xyz789", message="Missing receipt")

# Delete your own draft/pending expense
client.delete_expense(expense_id="abc123")
```

## File uploads

Upload files for expense attachments:

```python
# Upload from file path
file_info = client.upload_file(
    "/path/to/receipt.pdf",
    kind="EXPENSE_ITEM"  # or EXPENSE_INVOICE, EXPENSE_ATTACHED_FILE
)
print(f"Uploaded to: {file_info['url']}")

# Upload from file-like object
from io import BytesIO
file_obj = BytesIO(pdf_bytes)
file_info = client.upload_file(file_obj, filename="receipt.pdf")
```

Supported formats: PNG, JPEG, GIF, WebP, PDF, CSV

## Get collective info

```python
collective = client.get_collective("policyengine")
print(f"Name: {collective['name']}")
print(f"Currency: {collective['currency']}")
```

## CLI

The package includes a command-line interface for common operations.

### Setup

```bash
# Authenticate (get credentials at https://opencollective.com/applications)
oc auth
```

### Commands

```bash
# Submit a reimbursement
oc reimbursement "NASI Dues 2026" 325.00 receipt.pdf -c policyengine -t membership

# Submit an invoice
oc invoice "January Consulting" 5000.00 -c policyengine

# List expenses
oc expenses -c policyengine --pending
oc expenses -c policyengine --mine

# Delete an expense
oc delete abc123-def456

# Show current user
oc me
```

## MCP server (for Claude Code)

The package includes an MCP server so Claude Code can submit expenses directly.

### Setup

Add to your Claude Code MCP config (`~/.claude/mcp.json`):

```json
{
  "mcpServers": {
    "opencollective": {
      "command": "python",
      "args": ["-m", "opencollective.mcp_server"]
    }
  }
}
```

Make sure you've authenticated first with `oc auth`.

### Available tools

- **submit_reimbursement** - Submit a reimbursement with receipt
- **submit_invoice** - Submit an invoice for services
- **list_expenses** - List expenses for a collective
- **delete_expense** - Delete a draft/pending expense
- **get_me** - Get current user info
- **get_collective** - Get collective info

### Example usage in Claude Code

> "Submit my NASI receipt at /tmp/nasi_receipt.html as a $325 reimbursement to policyengine with tags membership and professional-development"

## Development

```bash
# Clone the repository
git clone https://github.com/MaxGhenis/opencollective-py.git
cd opencollective-py

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check --fix .
```

## License

MIT
