# opencollective-py development instructions

## Project overview
Python client for OpenCollective GraphQL API with support for expense submission, file uploads, and MCP server integration.

## Dev setup
```bash
# Install with dev extras (required for tests)
uv sync --extra dev

# Authenticate with OpenCollective (creates ~/.config/opencollective/token.json)
oc auth
```

## Running tests
```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/test_client.py -v

# Run with coverage report
uv run pytest --cov=opencollective --cov-report=html
```

## Linting and formatting
```bash
# Check ruff violations
uv run ruff check src/ tests/

# Auto-fix ruff issues
uv run ruff check --fix src/ tests/

# Check black formatting
uv run black --check src/ tests/

# Auto-format with black
uv run black src/ tests/
```

## Key architectural patterns

### Authentication
- OAuth2 token stored at `~/.config/opencollective/token.json`
- Use `oc auth` command to set up (requires OAuth2 app credentials from https://opencollective.com/applications)
- Token auto-refreshes

### GraphQL API
- All API calls go through GraphQL at https://opencollective.com/api/graphql/v2
- Use schema introspection to discover available fields
- Mutation examples: `ExpenseCreateInput`, `FileUploadInput`

### File uploads
- Must use frontend proxy URL (`opencollective.com/api/graphql/v2`), NOT the regular API URL
- This is due to OpenCollective infrastructure issue #11293
- Supports: PNG, JPEG, GIF, WebP, PDF, CSV

### Expense creation
- **incurredAt**: Must be full ISO datetime string (e.g., "2026-02-11T15:30:00Z"), not date-only
- **currency**: Optional enum on ExpenseCreateInput (defaults to collective currency)
- **expenseType**: "RECEIPT" for reimbursements, "INVOICE" for service billing

### WeasyPrint (optional PDF conversion)
- Only needed if converting HTML receipts to PDF
- Requires system libraries: pango, glib
- Import catches both `ImportError` (missing package) and `OSError` (missing system libs)
- Core functionality works without it

## CI/CD
- GitHub Actions runs tests on Python 3.10–3.13
- Lint jobs: ruff check, black formatting
- Known issue: `docs` job may fail (Sphinx integration still in progress)

## Common workflows

### Submit a reimbursement
```python
from opencollective import OpenCollectiveClient

client = OpenCollectiveClient.from_token_file()
expense = client.submit_reimbursement(
    collective_slug="policyengine",
    description="NASI Membership Dues 2026",
    amount_cents=32500,  # $325.00
    receipt_file="/path/to/receipt.pdf",
    tags=["membership"]
)
```

### Submit an invoice
```python
expense = client.submit_invoice(
    collective_slug="policyengine",
    description="January 2026 Consulting",
    amount_cents=500000,  # $5,000.00
    tags=["consulting"]
)
```

### Get expenses
```python
# All expenses
expenses = client.get_expenses("policyengine", limit=50)

# Pending only
pending = client.get_pending_expenses("policyengine")
```
