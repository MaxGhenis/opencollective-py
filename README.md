# opencollective-py

A Python client for the [OpenCollective](https://opencollective.com) GraphQL API.

## Installation

```bash
# From GitHub (recommended for now)
pip install git+https://github.com/MaxGhenis/opencollective-py.git
```

## Quick Start

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

### Fetching Expenses

```python
# Get recent expenses
expenses = client.get_expenses("policyengine", limit=50)
print(f"Found {expenses['totalCount']} expenses")

for exp in expenses["nodes"]:
    print(f"{exp['description']}: ${exp['amount']/100:.2f}")

# Get pending expenses only
pending = client.get_pending_expenses("policyengine")
```

### Managing Expenses

```python
# Approve an expense
client.approve_expense(expense_id="abc123")

# Reject an expense with a message
client.reject_expense(expense_id="xyz789", message="Missing receipt")

# Create a new expense
client.create_expense(
    collective_slug="policyengine",
    payee_slug="max-ghenis",
    description="Cloud services - January 2025",
    amount_cents=10000,  # $100.00
)
```

### Get Collective Info

```python
collective = client.get_collective("policyengine")
print(f"Name: {collective['name']}")
print(f"Currency: {collective['currency']}")
```

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
