# Quick Start

This guide walks you through setting up and using opencollective-py.

## Installation

```bash
pip install git+https://github.com/MaxGhenis/opencollective-py.git
```

## Setting Up OAuth2

To use the API, you need to create an OAuth2 application on OpenCollective.

### 1. Create an OAuth App

1. Go to [OpenCollective Applications](https://opencollective.com/applications)
2. Click "Create Application"
3. Fill in the details:
   - Name: Your app name
   - Redirect URI: `http://localhost:8080/callback` (for local development)
4. Save your client ID and client secret

### 2. Authenticate

```python
from opencollective import OAuth2Handler

# Set up the handler
auth = OAuth2Handler(
    client_id="your_client_id",
    client_secret="your_client_secret",
    token_file="~/.config/opencollective/token.json"  # Optional: persist token
)

# Get authorization URL
auth_url = auth.get_authorization_url(scope="expenses")
print(f"Open this URL in your browser: {auth_url}")

# After user authorizes, you'll get a code in the callback
# Exchange it for a token
token_data = auth.exchange_code(authorization_code)
```

### 3. Use the Client

```python
from opencollective import OpenCollectiveClient

client = OpenCollectiveClient(access_token=token_data["access_token"])
```

## Common Operations

### Fetch Expenses

```python
# Get recent expenses
expenses = client.get_expenses("policyengine", limit=50)
print(f"Found {expenses['totalCount']} expenses")

# Get pending expenses only
pending = client.get_pending_expenses("policyengine")

# Get expenses from a specific date
from_2025 = client.get_expenses(
    "policyengine",
    date_from="2025-01-01T00:00:00Z"
)
```

### Manage Expenses

```python
# Approve an expense
result = client.approve_expense("expense_id")
print(f"New status: {result['status']}")

# Reject with a message
result = client.reject_expense("expense_id", message="Missing receipt")

# Create a new expense
result = client.create_expense(
    collective_slug="policyengine",
    payee_slug="max-ghenis",
    description="Cloud services - January 2025",
    amount_cents=10000,  # $100.00
    tags=["cloud", "infrastructure"]
)
```

### Get Collective Info

```python
collective = client.get_collective("policyengine")
print(f"Name: {collective['name']}")
print(f"Currency: {collective['currency']}")
```

## Token Persistence

To avoid re-authenticating every time, use the `token_file` parameter:

```python
import os

TOKEN_PATH = os.path.expanduser("~/.config/opencollective/token.json")

auth = OAuth2Handler(
    client_id="your_client_id",
    client_secret="your_client_secret",
    token_file=TOKEN_PATH
)

# Load existing token
token = auth.load_token()
if token:
    client = OpenCollectiveClient(access_token=token["access_token"])
else:
    # Run OAuth flow
    ...
```

## Refreshing Tokens

When your access token expires, use the refresh token:

```python
token = auth.load_token()
if token and "refresh_token" in token:
    new_token = auth.refresh_access_token(token["refresh_token"])
    client = OpenCollectiveClient(access_token=new_token["access_token"])
```
