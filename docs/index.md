# opencollective-py

A Python client for the [OpenCollective](https://opencollective.com) GraphQL API.

## Features

- **OAuth2 Authentication**: Full OAuth2 flow with token refresh support
- **Expense Management**: Create, approve, reject, and list expenses
- **Collective Information**: Fetch collective details
- **Type Hints**: Full type annotations for better IDE support

## Installation

```bash
# From GitHub
pip install git+https://github.com/MaxGhenis/opencollective-py.git
```

## Quick Example

```python
from opencollective import OpenCollectiveClient

# Initialize with access token
client = OpenCollectiveClient(access_token="your_token")

# Get recent expenses
expenses = client.get_expenses("policyengine", limit=10)
for exp in expenses["nodes"]:
    print(f"{exp['description']}: ${exp['amount']/100:.2f}")

# Approve a pending expense
client.approve_expense("expense_id_here")
```

## Documentation

- [Quick Start Guide](quickstart.md) - Get up and running
- [API Reference](api-reference.md) - Detailed API documentation

## License

MIT License - see [LICENSE](https://github.com/MaxGhenis/opencollective-py/blob/main/LICENSE) for details.
