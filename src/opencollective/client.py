"""OpenCollective API client."""

import json
import mimetypes
import os
import tempfile
from typing import Any, BinaryIO

import requests

# Optional PDF conversion
try:
    from weasyprint import HTML as WeasyHTML

    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False

API_URL = "https://api.opencollective.com/graphql/v2"
# File uploads must go through the frontend proxy due to infrastructure issues
# with multipart handling on the direct API endpoint.
# See: https://github.com/opencollective/opencollective-api/issues/11293
UPLOAD_API_URL = "https://opencollective.com/api/graphql/v2"


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

    def upload_file(
        self,
        file: str | BinaryIO,
        filename: str | None = None,
        kind: str = "EXPENSE_ATTACHED_FILE",
    ) -> dict:
        """Upload a file to OpenCollective.

        Uses GraphQL multipart upload via the frontend proxy endpoint.
        See: https://github.com/opencollective/opencollective-api/issues/11293

        Args:
            file: File path (str) or file-like object (BinaryIO).
            filename: Optional filename (inferred from path if not provided).
            kind: File kind - EXPENSE_ATTACHED_FILE, EXPENSE_ITEM,
                EXPENSE_INVOICE, ACCOUNT_AVATAR, etc.

        Returns:
            Dict with file info including 'url', 'id', 'name', 'size', 'type'.

        Example:
            >>> file_info = client.upload_file("/path/to/receipt.pdf")
            >>> print(file_info["url"])
            https://opencollective-production.s3.us-west-1.amazonaws.com/...
        """
        # Handle file path or file-like object
        if isinstance(file, str):
            if not os.path.exists(file):
                raise FileNotFoundError(f"File not found: {file}")
            filename = filename or os.path.basename(file)
            file_obj = open(file, "rb")
            should_close = True
        else:
            file_obj = file
            filename = filename or getattr(file, "name", "upload")
            should_close = False

        try:
            # Determine MIME type from filename
            mime_type, _ = mimetypes.guess_type(filename)
            if mime_type is None:
                mime_type = "application/octet-stream"

            # GraphQL multipart request spec:
            # https://github.com/jaydenseric/graphql-multipart-request-spec
            mutation = """
            mutation UploadFile($files: [UploadFileInput!]!) {
                uploadFile(files: $files) {
                    file {
                        id
                        url
                        name
                        type
                        size
                    }
                }
            }
            """

            operations = json.dumps(
                {
                    "query": mutation,
                    "variables": {"files": [{"kind": kind, "file": None}]},
                }
            )

            # Map tells server which variable path the file corresponds to
            file_map = json.dumps({"0": ["variables.files.0.file"]})

            # Build multipart form data
            files = {
                "operations": (None, operations, "application/json"),
                "map": (None, file_map, "application/json"),
                "0": (filename, file_obj, mime_type),
            }

            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(UPLOAD_API_URL, files=files, headers=headers)
            response.raise_for_status()

            result = response.json()
            if "errors" in result:
                errors = result["errors"]
                msg = errors[0].get("message", "Unknown error")
                raise Exception(f"Upload error: {msg}")

            data = result.get("data", {})
            upload_result = data.get("uploadFile", [])
            # uploadFile returns a list since mutation accepts multiple files
            if isinstance(upload_result, list) and len(upload_result) > 0:
                file_info = upload_result[0].get("file", {})
            else:
                file_info = upload_result.get("file", {}) if upload_result else {}

            return {
                "url": file_info.get("url"),
                "id": file_info.get("id"),
                "name": file_info.get("name"),
                "type": file_info.get("type"),
                "size": file_info.get("size"),
            }

        finally:
            if should_close:
                file_obj.close()

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

    def reject_expense(self, expense_id: str, message: str | None = None) -> dict:
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
        currency: str | None = None,
        incurred_at: str | None = None,
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
            currency: Optional currency code (e.g., "GBP", "EUR"). If not
                provided, defaults to the collective's currency.
            incurred_at: Optional date the expense was incurred (ISO format,
                e.g., "2026-01-31"). Set on the expense item.

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
        item = {
            "description": description,
            "amount": amount_cents,
        }
        if incurred_at:
            # Ensure full ISO datetime format (API rejects date-only strings)
            if "T" not in incurred_at:
                incurred_at = f"{incurred_at}T00:00:00Z"
            item["incurredAt"] = incurred_at

        expense_input = {
            "description": description,
            "type": expense_type,
            "payee": {"slug": payee_slug},
            "items": [item],
        }
        if currency:
            expense_input["currency"] = currency
        if payout_method_id:
            expense_input["payoutMethod"] = {"id": payout_method_id}
        if tags:
            expense_input["tags"] = tags
        if attachment_urls:
            expense_input["attachedFiles"] = [{"url": url} for url in attachment_urls]
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
        result = self.get_expenses(collective_slug, status="PENDING", limit=100)
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

    def get_me(self) -> dict:
        """Get the current authenticated user's account info.

        Returns:
            Dict with id, slug, name of the current user.
        """
        query = """
        query {
            me {
                id
                slug
                name
            }
        }
        """
        data = self._request(query)
        return data.get("me", {})

    def delete_expense(self, expense_id: str) -> dict:
        """Delete an expense (only works for DRAFT or PENDING expenses you created).

        Args:
            expense_id: The expense ID (not legacy ID).

        Returns:
            Dict with id and legacyId of deleted expense.
        """
        mutation = """
        mutation DeleteExpense($expense: ExpenseReferenceInput!) {
            deleteExpense(expense: $expense) {
                id
                legacyId
            }
        }
        """
        data = self._request(mutation, {"expense": {"id": expense_id}})
        return data.get("deleteExpense", {})

    def _convert_html_to_pdf(self, html_path: str) -> str:
        """Convert an HTML file to PDF.

        Args:
            html_path: Path to HTML file.

        Returns:
            Path to generated PDF file.

        Raises:
            ImportError: If weasyprint is not installed.
        """
        if not HAS_WEASYPRINT:
            raise ImportError(
                "weasyprint is required for HTML to PDF conversion. "
                "Install with: pip install opencollective[pdf]"
            )

        pdf_path = tempfile.mktemp(suffix=".pdf")
        WeasyHTML(filename=html_path).write_pdf(pdf_path)
        return pdf_path

    def submit_reimbursement(
        self,
        collective_slug: str,
        description: str,
        amount_cents: int,
        receipt_file: str,
        payee_slug: str | None = None,
        payout_method_id: str | None = None,
        tags: list[str] | None = None,
        currency: str | None = None,
        incurred_at: str | None = None,
    ) -> dict:
        """Submit a reimbursement expense with a receipt.

        This is a high-level method that handles:
        - Auto-detecting payee from authenticated user if not provided
        - Auto-selecting first payout method if not provided
        - Converting HTML receipts to PDF automatically
        - Uploading the receipt file
        - Creating the RECEIPT-type expense

        Use this for reimbursements where you paid out-of-pocket and need
        to be paid back. Requires a receipt file.

        Args:
            collective_slug: The collective's slug (e.g., "policyengine").
            description: Description of the expense.
            amount_cents: Amount in cents (e.g., 32500 for $325.00).
            receipt_file: Path to receipt file (PDF, PNG, JPG, or HTML).
                HTML files are automatically converted to PDF.
            payee_slug: Your account slug. Auto-detected if not provided.
            payout_method_id: Payout method ID. Uses first available if not provided.
            tags: Optional list of tags for categorization.
            currency: Optional currency code (e.g., "GBP", "EUR"). Defaults
                to the collective's currency if not provided.
            incurred_at: Optional date the expense was incurred (ISO format,
                e.g., "2026-01-31").

        Returns:
            Created expense data with id, legacyId, description, status.

        Example:
            >>> expense = client.submit_reimbursement(
            ...     collective_slug="policyengine",
            ...     description="NASI Membership Dues 2026",
            ...     amount_cents=32500,
            ...     receipt_file="/path/to/receipt.pdf",
            ...     tags=["membership", "professional development"]
            ... )
            >>> print(f"Created: https://opencollective.com/policyengine/expenses/{expense['legacyId']}")
        """
        # Auto-detect payee from authenticated user
        if not payee_slug:
            me = self.get_me()
            payee_slug = me.get("slug")
            if not payee_slug:
                raise ValueError(
                    "Could not determine payee. Please provide payee_slug."
                )

        # Auto-select first payout method if not provided
        if not payout_method_id:
            methods = self.get_payout_methods(payee_slug)
            if methods:
                payout_method_id = methods[0]["id"]

        # Handle file conversion and upload
        file_to_upload = receipt_file
        temp_pdf = None

        if receipt_file.lower().endswith(".html") or receipt_file.lower().endswith(
            ".htm"
        ):
            temp_pdf = self._convert_html_to_pdf(receipt_file)
            file_to_upload = temp_pdf

        try:
            # Upload the receipt
            file_info = self.upload_file(file_to_upload, kind="EXPENSE_ITEM")
            receipt_url = file_info.get("url")

            if not receipt_url:
                raise ValueError("Failed to upload receipt file")

            # Create the expense with the receipt attached to the item
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

            item = {
                "description": description,
                "amount": amount_cents,
                "url": receipt_url,
            }
            if incurred_at:
                if "T" not in incurred_at:
                    incurred_at = f"{incurred_at}T00:00:00Z"
                item["incurredAt"] = incurred_at

            expense_input = {
                "description": description,
                "type": "RECEIPT",
                "payee": {"slug": payee_slug},
                "items": [item],
            }
            if currency:
                expense_input["currency"] = currency
            if payout_method_id:
                expense_input["payoutMethod"] = {"id": payout_method_id}
            if tags:
                expense_input["tags"] = tags

            variables = {
                "account": {"slug": collective_slug},
                "expense": expense_input,
            }

            data = self._request(mutation, variables)
            return data.get("createExpense", {})

        finally:
            # Clean up temp PDF if created
            if temp_pdf and os.path.exists(temp_pdf):
                os.unlink(temp_pdf)

    def submit_invoice(
        self,
        collective_slug: str,
        description: str,
        amount_cents: int,
        payee_slug: str | None = None,
        payout_method_id: str | None = None,
        invoice_file: str | None = None,
        tags: list[str] | None = None,
        currency: str | None = None,
        incurred_at: str | None = None,
    ) -> dict:
        """Submit an invoice expense.

        This is a high-level method for invoices where you're billing
        for services rendered. Unlike reimbursements, invoices don't
        require a receipt - you're requesting payment for work done.

        Use this for:
        - Contractor payments
        - Service fees
        - Consulting work
        - Any expense where you're billing (not being reimbursed)

        Args:
            collective_slug: The collective's slug (e.g., "policyengine").
            description: Description of the invoice.
            amount_cents: Amount in cents (e.g., 100000 for $1,000.00).
            payee_slug: Your account slug. Auto-detected if not provided.
            payout_method_id: Payout method ID. Uses first available if not provided.
            invoice_file: Optional path to invoice PDF for documentation.
            tags: Optional list of tags for categorization.
            currency: Optional currency code (e.g., "GBP", "EUR"). Defaults
                to the collective's currency if not provided.
            incurred_at: Optional date the expense was incurred (ISO format,
                e.g., "2026-01-31").

        Returns:
            Created expense data with id, legacyId, description, status.

        Example:
            >>> expense = client.submit_invoice(
            ...     collective_slug="policyengine",
            ...     description="January 2026 Consulting",
            ...     amount_cents=500000,
            ...     tags=["consulting"]
            ... )
        """
        # Auto-detect payee from authenticated user
        if not payee_slug:
            me = self.get_me()
            payee_slug = me.get("slug")
            if not payee_slug:
                raise ValueError(
                    "Could not determine payee. Please provide payee_slug."
                )

        # Auto-select first payout method if not provided
        if not payout_method_id:
            methods = self.get_payout_methods(payee_slug)
            if methods:
                payout_method_id = methods[0]["id"]

        # Handle optional invoice file upload
        invoice_url = None
        if invoice_file:
            file_info = self.upload_file(invoice_file, kind="EXPENSE_INVOICE")
            invoice_url = file_info.get("url")

        # Create the invoice expense
        return self.create_expense(
            collective_slug=collective_slug,
            payee_slug=payee_slug,
            description=description,
            amount_cents=amount_cents,
            payout_method_id=payout_method_id,
            expense_type="INVOICE",
            tags=tags,
            invoice_url=invoice_url,
            currency=currency,
            incurred_at=incurred_at,
        )
