# API Reference

## OpenCollectiveClient

The main client for interacting with the OpenCollective API.

### Initialization

```python
from opencollective import OpenCollectiveClient

client = OpenCollectiveClient(access_token="your_token")
```

**Parameters:**
- `access_token` (str, required): OAuth2 access token

### Methods

#### get_collective

Get information about a collective.

```python
collective = client.get_collective("policyengine")
```

**Parameters:**
- `slug` (str): The collective's slug

**Returns:** Dict with `id`, `slug`, `name`, `description`, `currency`

---

#### get_expenses

Get expenses for a collective.

```python
result = client.get_expenses(
    collective_slug="policyengine",
    limit=50,
    offset=0,
    status="PENDING",
    date_from="2025-01-01T00:00:00Z"
)
```

**Parameters:**
- `collective_slug` (str): The collective's slug
- `limit` (int, optional): Max expenses to return (default: 50)
- `offset` (int, optional): Pagination offset (default: 0)
- `status` (str, optional): Filter by status (`PENDING`, `APPROVED`, `PAID`, etc.)
- `date_from` (str, optional): Filter from date (ISO format)

**Returns:** Dict with `totalCount` and `nodes` (list of expense objects)

---

#### get_pending_expenses

Get all pending expenses for a collective.

```python
pending = client.get_pending_expenses("policyengine")
```

**Parameters:**
- `collective_slug` (str): The collective's slug

**Returns:** List of pending expense objects

---

#### approve_expense

Approve a pending expense.

```python
result = client.approve_expense("expense_id")
```

**Parameters:**
- `expense_id` (str): The expense ID (not legacy ID)

**Returns:** Updated expense object

---

#### reject_expense

Reject a pending expense.

```python
result = client.reject_expense("expense_id", message="Invalid receipt")
```

**Parameters:**
- `expense_id` (str): The expense ID
- `message` (str, optional): Rejection message

**Returns:** Updated expense object

---

#### create_expense

Create a new expense (as a draft).

```python
result = client.create_expense(
    collective_slug="policyengine",
    payee_slug="max-ghenis",
    description="Cloud services",
    amount_cents=10000,
    expense_type="RECEIPT",
    tags=["cloud"]
)
```

**Parameters:**
- `collective_slug` (str): The collective's slug
- `payee_slug` (str): The payee's slug
- `description` (str): Expense description
- `amount_cents` (int): Amount in cents
- `expense_type` (str, optional): Type (`RECEIPT`, `INVOICE`, etc.)
- `tags` (list[str], optional): List of tags

**Returns:** Created expense object

---

## OAuth2Handler

Handle OAuth2 authentication with OpenCollective.

### Initialization

```python
from opencollective import OAuth2Handler

auth = OAuth2Handler(
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="http://localhost:8080/callback",
    token_file="~/.config/opencollective/token.json"
)
```

**Parameters:**
- `client_id` (str, required): OAuth2 client ID
- `client_secret` (str, required): OAuth2 client secret
- `redirect_uri` (str, optional): Callback URL (default: `http://localhost:8080/callback`)
- `token_file` (str, optional): Path to store/load tokens

### Methods

#### get_authorization_url

Get the URL for user authorization.

```python
url = auth.get_authorization_url(scope="expenses")
```

**Parameters:**
- `scope` (str, optional): OAuth2 scope (default: `expenses`)

**Returns:** Authorization URL string

---

#### exchange_code

Exchange authorization code for access token.

```python
token_data = auth.exchange_code("authorization_code")
```

**Parameters:**
- `code` (str): Authorization code from callback

**Returns:** Token data dict with `access_token`, `refresh_token`, etc.

---

#### refresh_access_token

Refresh an expired access token.

```python
new_token = auth.refresh_access_token("refresh_token")
```

**Parameters:**
- `refresh_token` (str): The refresh token

**Returns:** New token data dict

---

#### save_token / load_token

Save and load tokens from file.

```python
auth.save_token(token_data)
token = auth.load_token()
```

---

## Expense Object

Expense objects returned by the API include:

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique expense ID |
| `legacyId` | int | Legacy numeric ID |
| `description` | str | Expense description |
| `amount` | int | Amount in cents |
| `currency` | str | Currency code (e.g., "USD") |
| `status` | str | Status (`DRAFT`, `PENDING`, `APPROVED`, `PAID`, `REJECTED`) |
| `type` | str | Type (`RECEIPT`, `INVOICE`, etc.) |
| `createdAt` | str | ISO timestamp |
| `payee` | dict | Payee info with `name` and `slug` |
| `tags` | list | List of tag strings |
