"""OpenCollective API client."""

from typing import Any

import requests

API_URL = "https://api.opencollective.com/graphql/v2"


class OpenCollectiveClient:
    """Client for interacting with the OpenCollective GraphQL API."""

    def __init__(self, access_token: str | None = None):
        """Initialize the client.

        Args:
            access_token: OAuth2 access token for authentication.

        Raises:
            ValueError: If no access token is provided.
        """
        if not access_token:
            raise ValueError("access_token is required")
        self.access_token = access_token
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }
        )

    def _request(self, query: str, variables: dict[str, Any] = None) -> dict:
        """Make a GraphQL request.

        Args:
            query: GraphQL query or mutation.
            variables: Variables for the query.

        Returns:
            The data from the response.

        Raises:
            Exception: If the API returns an error.
        """
        response = self._session.post(
            API_URL,
            json={"query": query, "variables": variables or {}},
        )
        response.raise_for_status()

        result = response.json()
        if "errors" in result:
            errors = result["errors"]
            msg = errors[0].get("message", "Unknown error")
            raise Exception(f"API error: {msg}")

        return result.get("data", {})

    def get_collective(self, slug: str) -> dict:
        """Get information about a collective.

        Args:
            slug: The collective's slug (e.g., "policyengine").

        Returns:
            Collective information including id, slug, name, description, currency.
        """
        query = """
        query GetCollective($slug: String!) {
            collective(slug: $slug) {
                id
                slug
                name
                description
                currency
            }
        }
        """
        data = self._request(query, {"slug": slug})
        return data.get("collective", {})

    def get_expenses(
        self,
        collective_slug: str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        date_from: str | None = None,
    ) -> dict:
        """Get expenses for a collective.

        Args:
            collective_slug: The collective's slug.
            limit: Maximum number of expenses to return.
            offset: Offset for pagination.
            status: Filter by status (PENDING, APPROVED, PAID, etc.).
            date_from: Filter expenses from this date (ISO format).

        Returns:
            Dict with totalCount and nodes (list of expenses).
        """
        query = """
        query GetExpenses(
            $account: AccountReferenceInput!,
            $limit: Int!,
            $offset: Int!,
            $status: ExpenseStatusFilter,
            $dateFrom: DateTime
        ) {
            expenses(
                account: $account,
                limit: $limit,
                offset: $offset,
                status: $status,
                dateFrom: $dateFrom,
                orderBy: { field: CREATED_AT, direction: DESC }
            ) {
                totalCount
                nodes {
                    id
                    legacyId
                    description
                    amount
                    currency
                    type
                    status
                    createdAt
                    payee { name slug }
                    tags
                }
            }
        }
        """
        variables = {
            "account": {"slug": collective_slug},
            "limit": limit,
            "offset": offset,
        }
        if status:
            variables["status"] = status
        if date_from:
            variables["dateFrom"] = date_from

        data = self._request(query, variables)
        return data.get("expenses", {"totalCount": 0, "nodes": []})

    def approve_expense(self, expense_id: str) -> dict:
        """Approve a pending expense.

        Args:
            expense_id: The expense ID (not legacy ID).

        Returns:
            Updated expense data.
        """
        return self._process_expense(expense_id, "APPROVE")

    def reject_expense(
        self, expense_id: str, message: str | None = None
    ) -> dict:
        """Reject a pending expense.

        Args:
            expense_id: The expense ID.
            message: Optional rejection message.

        Returns:
            Updated expense data.
        """
        return self._process_expense(expense_id, "REJECT", message)

    def _process_expense(
        self, expense_id: str, action: str, message: str | None = None
    ) -> dict:
        """Process an expense (approve, reject, etc.).

        Args:
            expense_id: The expense ID.
            action: Action to take (APPROVE, REJECT, etc.).
            message: Optional message for the action.

        Returns:
            Updated expense data.
        """
        mutation = """
        mutation ProcessExpense(
            $expense: ExpenseReferenceInput!,
            $action: ExpenseProcessAction!,
            $message: String
        ) {
            processExpense(expense: $expense, action: $action, message: $message) {
                id
                legacyId
                description
                status
            }
        }
        """
        variables = {
            "expense": {"id": expense_id},
            "action": action,
        }
        if message:
            variables["message"] = message

        data = self._request(mutation, variables)
        return data.get("processExpense", {})

    def get_payout_methods(self, account_slug: str) -> list[dict]:
        """Get payout methods for an account.

        Args:
            account_slug: The account's slug (e.g., your user slug).

        Returns:
            List of payout method objects with id, type, name, data.
        """
        query = """
        query GetPayoutMethods($slug: String!) {
            account(slug: $slug) {
                id
                slug
                payoutMethods {
                    id
                    type
                    name
                    data
                    isSaved
                }
            }
        }
        """
        data = self._request(query, {"slug": account_slug})
        account = data.get("account", {})
        return account.get("payoutMethods", [])

    def create_expense(
        self,
        collective_slug: str,
        payee_slug: str,
        description: str,
        amount_cents: int,
        payout_method_id: str | None = None,
        expense_type: str = "RECEIPT",
        tags: list[str] | None = None,
        attachment_urls: list[str] | None = None,
        invoice_url: str | None = None,
    ) -> dict:
        """Create a new expense (as a draft).

        Args:
            collective_slug: The collective's slug.
            payee_slug: The payee's slug.
            description: Description of the expense.
            amount_cents: Amount in cents (e.g., 1000 for $10.00).
            payout_method_id: ID of the payout method to use (required).
                Use get_payout_methods() to find available methods.
            expense_type: Type of expense (RECEIPT, INVOICE, etc.).
            tags: Optional list of tags.
            attachment_urls: Optional list of URLs for receipt/attachment files.
            invoice_url: Optional URL for invoice file (for INVOICE type).

        Returns:
            Created expense data.
        """
        mutation = """
        mutation CreateExpense(
            $expense: ExpenseCreateInput!,
            $account: AccountReferenceInput!
        ) {
            createExpense(expense: $expense, account: $account) {
                id
                legacyId
                description
                amount
                status
            }
        }
        """
        expense_input = {
            "description": description,
            "type": expense_type,
            "payee": {"slug": payee_slug},
            "items": [
                {
                    "description": description,
                    "amount": amount_cents,
                }
            ],
        }
        if payout_method_id:
            expense_input["payoutMethod"] = {"id": payout_method_id}
        if tags:
            expense_input["tags"] = tags
        if attachment_urls:
            expense_input["attachedFiles"] = [
                {"url": url} for url in attachment_urls
            ]
        if invoice_url:
            expense_input["invoiceFile"] = {"url": invoice_url}

        variables = {
            "account": {"slug": collective_slug},
            "expense": expense_input,
        }

        data = self._request(mutation, variables)
        return data.get("createExpense", {})

    def get_pending_expenses(self, collective_slug: str) -> list[dict]:
        """Get all pending expenses for a collective.

        Args:
            collective_slug: The collective's slug.

        Returns:
            List of pending expenses.
        """
        result = self.get_expenses(
            collective_slug, status="PENDING", limit=100
        )
        return result.get("nodes", [])

    def get_my_expenses(
        self, collective_slug: str, payee_slug: str, limit: int = 50
    ) -> list[dict]:
        """Get expenses submitted by a specific payee.

        Args:
            collective_slug: The collective's slug.
            payee_slug: The payee's slug.
            limit: Maximum number of expenses.

        Returns:
            List of expenses from the payee.
        """
        result = self.get_expenses(collective_slug, limit=limit)
        return [
            e
            for e in result.get("nodes", [])
            if e.get("payee", {}).get("slug") == payee_slug
        ]
