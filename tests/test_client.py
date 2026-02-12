"""Tests for OpenCollective client."""

import os
import tempfile
from io import BytesIO

import pytest
import responses

from opencollective import OpenCollectiveClient

API_URL = "https://api.opencollective.com/graphql/v2"
# File uploads use frontend proxy due to infrastructure issues with direct API
# See: https://github.com/opencollective/opencollective-api/issues/11293
UPLOAD_URL = "https://opencollective.com/api/graphql/v2"


class TestOpenCollectiveClient:
    """Tests for the OpenCollective API client."""

    def test_client_init_with_token(self):
        """Client can be initialized with an access token."""
        client = OpenCollectiveClient(access_token="test_token")
        assert client.access_token == "test_token"

    def test_client_init_without_token_raises(self):
        """Client raises error without token."""
        with pytest.raises(ValueError, match="access_token is required"):
            OpenCollectiveClient()

    @responses.activate
    def test_get_collective(self):
        """Can fetch collective information."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "collective": {
                        "id": "abc123",
                        "slug": "policyengine",
                        "name": "PolicyEngine",
                        "description": "Computing public policy",
                        "currency": "USD",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        collective = client.get_collective("policyengine")

        assert collective["slug"] == "policyengine"
        assert collective["name"] == "PolicyEngine"
        assert collective["currency"] == "USD"

    @responses.activate
    def test_get_expenses(self):
        """Can fetch expenses for a collective."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 2,
                        "nodes": [
                            {
                                "id": "exp1",
                                "legacyId": 123,
                                "description": "Cloud services",
                                "amount": 10000,
                                "currency": "USD",
                                "status": "PAID",
                                "createdAt": "2025-01-01T00:00:00Z",
                                "payee": {
                                    "name": "Max Ghenis",
                                    "slug": "max-ghenis",
                                },
                            },
                            {
                                "id": "exp2",
                                "legacyId": 124,
                                "description": "Travel",
                                "amount": 50000,
                                "currency": "USD",
                                "status": "PENDING",
                                "createdAt": "2025-01-02T00:00:00Z",
                                "payee": {
                                    "name": "Jane Doe",
                                    "slug": "jane-doe",
                                },
                            },
                        ],
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.get_expenses("policyengine", limit=10)

        assert result["totalCount"] == 2
        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["description"] == "Cloud services"
        assert result["nodes"][0]["amount"] == 10000

    @responses.activate
    def test_get_expenses_with_status_filter(self):
        """Can filter expenses by status."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 1,
                        "nodes": [
                            {
                                "id": "exp2",
                                "legacyId": 124,
                                "description": "Travel",
                                "amount": 50000,
                                "currency": "USD",
                                "status": "PENDING",
                                "createdAt": "2025-01-02T00:00:00Z",
                                "payee": {
                                    "name": "Jane Doe",
                                    "slug": "jane-doe",
                                },
                            },
                        ],
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.get_expenses("policyengine", status="PENDING")

        assert result["totalCount"] == 1
        assert result["nodes"][0]["status"] == "PENDING"

    @responses.activate
    def test_approve_expense(self):
        """Can approve a pending expense."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp2",
                        "legacyId": 124,
                        "description": "Travel",
                        "status": "APPROVED",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.approve_expense("exp2")

        assert result["status"] == "APPROVED"

    @responses.activate
    def test_reject_expense(self):
        """Can reject a pending expense."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp2",
                        "legacyId": 124,
                        "description": "Travel",
                        "status": "REJECTED",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.reject_expense("exp2", message="Invalid receipt")

        assert result["status"] == "REJECTED"

    @responses.activate
    def test_create_expense(self):
        """Can create a new expense."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp3",
                        "legacyId": 125,
                        "description": "Software subscription",
                        "amount": 2000,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Software subscription",
            amount_cents=2000,
        )

        assert result["description"] == "Software subscription"
        assert result["status"] == "DRAFT"

    @responses.activate
    def test_create_expense_with_attachments(self):
        """Can create an expense with file attachments."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp4",
                        "legacyId": 126,
                        "description": "GCP Cloud Services",
                        "amount": 15000,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="GCP Cloud Services",
            amount_cents=15000,
            attachment_urls=["https://example.com/receipt.pdf"],
            tags=["cloud", "infrastructure"],
        )

        assert result["description"] == "GCP Cloud Services"
        assert result["status"] == "DRAFT"

        # Verify the request included attachedFiles
        request_body = responses.calls[0].request.body.decode()
        assert "attachedFiles" in request_body
        assert "https://example.com/receipt.pdf" in request_body

    @responses.activate
    def test_create_invoice_expense(self):
        """Can create an invoice expense with invoice file."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp5",
                        "legacyId": 127,
                        "description": "Consulting services",
                        "amount": 100000,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Consulting services",
            amount_cents=100000,
            expense_type="INVOICE",
            invoice_url="https://example.com/invoice.pdf",
        )

        assert result["description"] == "Consulting services"

        # Verify the request included invoiceFile
        request_body = responses.calls[0].request.body.decode()
        assert "invoiceFile" in request_body
        assert "https://example.com/invoice.pdf" in request_body

    @responses.activate
    def test_get_payout_methods(self):
        """Can fetch payout methods for an account."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "account": {
                        "id": "user123",
                        "slug": "max-ghenis",
                        "payoutMethods": [
                            {
                                "id": "pm_abc123",
                                "type": "BANK_ACCOUNT",
                                "name": "Chase ****1234",
                                "data": {"currency": "USD"},
                                "isSaved": True,
                            },
                            {
                                "id": "pm_def456",
                                "type": "PAYPAL",
                                "name": "PayPal",
                                "data": {"email": "max@example.com"},
                                "isSaved": True,
                            },
                        ],
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        methods = client.get_payout_methods("max-ghenis")

        assert len(methods) == 2
        assert methods[0]["id"] == "pm_abc123"
        assert methods[0]["type"] == "BANK_ACCOUNT"
        assert methods[1]["type"] == "PAYPAL"

    @responses.activate
    def test_create_expense_with_payout_method(self):
        """Can create expense with payout method."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp6",
                        "legacyId": 128,
                        "description": "Cloud services",
                        "amount": 10000,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Cloud services",
            amount_cents=10000,
            payout_method_id="pm_abc123",
        )

        assert result["description"] == "Cloud services"
        assert result["status"] == "DRAFT"

        # Verify the request included payoutMethod
        request_body = responses.calls[0].request.body.decode()
        assert "payoutMethod" in request_body
        assert "pm_abc123" in request_body

    @responses.activate
    def test_api_error_handling(self):
        """Client handles API errors gracefully."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "errors": [
                    {
                        "message": "Unauthorized",
                        "extensions": {"code": "UNAUTHORIZED"},
                    }
                ]
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="invalid_token")

        with pytest.raises(Exception, match="API error"):
            client.get_collective("policyengine")

    @responses.activate
    def test_http_error_handling(self):
        """Client handles HTTP errors."""
        responses.add(
            responses.POST,
            API_URL,
            status=500,
        )

        client = OpenCollectiveClient(access_token="test_token")

        with pytest.raises(Exception):
            client.get_collective("policyengine")


class TestUploadFile:
    """Tests for file upload functionality."""

    @responses.activate
    def test_upload_file_from_path(self):
        """Can upload a file from a file path."""
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": {
                        "file": {
                            "id": "file-abc123",
                            "url": "https://opencollective-production.s3.us-west-1.amazonaws.com/abc123.pdf",
                            "name": "test.pdf",
                            "type": "application/pdf",
                            "size": 16,
                        }
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"test pdf content")
            temp_path = f.name

        try:
            result = client.upload_file(temp_path)
            assert (
                result["url"]
                == "https://opencollective-production.s3.us-west-1.amazonaws.com/abc123.pdf"
            )
            assert result["id"] == "file-abc123"

            # Verify request follows GraphQL multipart spec
            request = responses.calls[0].request
            assert b"operations" in request.body
            assert b"EXPENSE_ATTACHED_FILE" in request.body
        finally:
            import os

            os.unlink(temp_path)

    @responses.activate
    def test_upload_file_from_file_object(self):
        """Can upload a file from a file-like object."""
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": {
                        "file": {
                            "id": "file-def456",
                            "url": "https://opencollective-production.s3.us-west-1.amazonaws.com/def456.png",
                            "name": "receipt.png",
                            "type": "image/png",
                            "size": 18,
                        }
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        file_obj = BytesIO(b"test image content")
        result = client.upload_file(
            file_obj, filename="receipt.png", kind="EXPENSE_ITEM"
        )

        assert (
            result["url"]
            == "https://opencollective-production.s3.us-west-1.amazonaws.com/def456.png"
        )
        assert result["name"] == "receipt.png"

        # Verify request included correct kind
        request = responses.calls[0].request
        assert b"EXPENSE_ITEM" in request.body

    @responses.activate
    def test_upload_file_with_custom_kind(self):
        """Can upload a file with custom file kind."""
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": {
                        "file": {
                            "id": "file-ghi789",
                            "url": "https://opencollective-production.s3.us-west-1.amazonaws.com/ghi789.pdf",
                            "name": "invoice.pdf",
                            "type": "application/pdf",
                            "size": 20,
                        }
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"test invoice content")
            temp_path = f.name

        try:
            result = client.upload_file(temp_path, kind="EXPENSE_INVOICE")
            assert (
                result["url"]
                == "https://opencollective-production.s3.us-west-1.amazonaws.com/ghi789.pdf"
            )

            # Verify request included correct kind
            request = responses.calls[0].request
            assert b"EXPENSE_INVOICE" in request.body
        finally:
            import os

            os.unlink(temp_path)

    def test_upload_file_not_found(self):
        """Raises FileNotFoundError for nonexistent file."""
        client = OpenCollectiveClient(access_token="test_token")

        with pytest.raises(FileNotFoundError, match="File not found"):
            client.upload_file("/nonexistent/path/to/file.pdf")

    @responses.activate
    def test_upload_file_api_error(self):
        """Handles API error responses."""
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "errors": [
                    {
                        "message": "Invalid file type",
                        "extensions": {"code": "BAD_REQUEST"},
                    }
                ]
            },
            status=200,  # GraphQL returns 200 with errors array
        )

        client = OpenCollectiveClient(access_token="test_token")

        file_obj = BytesIO(b"test content")

        with pytest.raises(Exception, match="Invalid file type"):
            client.upload_file(file_obj, filename="test.txt")

    @responses.activate
    def test_upload_file_mime_type_detection(self):
        """Correctly detects MIME type from filename."""
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": {
                        "file": {
                            "id": "file-mime123",
                            "url": "https://opencollective-production.s3.us-west-1.amazonaws.com/mime123.png",
                            "name": "image.png",
                            "type": "image/png",
                            "size": 16,
                        }
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        # Test PNG file
        file_obj = BytesIO(b"fake png content")
        result = client.upload_file(file_obj, filename="image.png")

        # Verify file info returned correctly
        assert result["type"] == "image/png"
        assert result["name"] == "image.png"

        # Check MIME type in request body
        request = responses.calls[0].request
        # The Content-Type header for multipart should contain image/png
        assert b"image/png" in request.body


class TestGetMe:
    """Tests for get_me method."""

    @responses.activate
    def test_get_me(self):
        """Can get current authenticated user."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "me": {
                        "id": "user-abc123",
                        "slug": "max-ghenis",
                        "name": "Max Ghenis",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        me = client.get_me()

        assert me["id"] == "user-abc123"
        assert me["slug"] == "max-ghenis"
        assert me["name"] == "Max Ghenis"


class TestDeleteExpense:
    """Tests for delete_expense method."""

    @responses.activate
    def test_delete_expense(self):
        """Can delete a draft/pending expense."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "deleteExpense": {
                        "id": "exp-abc123",
                        "legacyId": 12345,
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.delete_expense("exp-abc123")

        assert result["id"] == "exp-abc123"
        assert result["legacyId"] == 12345


class TestSubmitReimbursement:
    """Tests for submit_reimbursement high-level method."""

    @responses.activate
    def test_submit_reimbursement_with_pdf(self):
        """Can submit reimbursement with PDF receipt."""
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
        # Mock upload_file - returns list format
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {
                            "file": {
                                "id": "file-123",
                                "url": "https://example.com/receipt.pdf",
                            }
                        }
                    ]
                }
            },
            status=200,
        )
        # Mock create_expense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-123",
                        "legacyId": 99999,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        # Create a temp PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf content")
            temp_path = f.name

        try:
            result = client.submit_reimbursement(
                collective_slug="policyengine",
                description="Test expense",
                amount_cents=10000,
                receipt_file=temp_path,
                tags=["test"],
            )

            assert result["legacyId"] == 99999
            assert result["status"] == "PENDING"
        finally:
            os.unlink(temp_path)

    @responses.activate
    def test_submit_reimbursement_with_explicit_payee(self):
        """Can submit reimbursement with explicit payee slug."""
        # Mock get_payout_methods
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "account": {"payoutMethods": [{"id": "pm-456", "type": "PAYPAL"}]}
                }
            },
            status=200,
        )
        # Mock upload_file
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {"file": {"id": "f1", "url": "https://example.com/r.pdf"}}
                    ]
                }
            },
            status=200,
        )
        # Mock create_expense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {"id": "e1", "legacyId": 111, "status": "PENDING"}
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"pdf")
            temp_path = f.name

        try:
            result = client.submit_reimbursement(
                collective_slug="policyengine",
                description="Test",
                amount_cents=5000,
                receipt_file=temp_path,
                payee_slug="explicit-user",
            )
            assert result["legacyId"] == 111
        finally:
            os.unlink(temp_path)


class TestCurrencySupport:
    """Tests for multi-currency expense support."""

    @responses.activate
    def test_create_expense_with_currency(self):
        """Can create an expense with explicit currency."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-gbp",
                        "legacyId": 200,
                        "description": "GCP Cloud Services",
                        "amount": 205895,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="GCP Cloud Services",
            amount_cents=205895,
            currency="GBP",
            tags=["gcp", "infrastructure"],
        )

        assert result["description"] == "GCP Cloud Services"
        assert result["status"] == "DRAFT"

        # Verify the request included currency
        request_body = responses.calls[0].request.body.decode()
        assert '"currency":"GBP"' in request_body.replace(" ", "")

    @responses.activate
    def test_create_expense_without_currency_omits_field(self):
        """Currency field is omitted when not provided (uses collective default)."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-usd",
                        "legacyId": 201,
                        "description": "Test",
                        "amount": 1000,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Test",
            amount_cents=1000,
        )

        request_body = responses.calls[0].request.body.decode()
        # currency should NOT appear in expense input when not specified
        assert '"currency"' not in request_body or '"currency":null' in request_body.replace(" ", "")

    @responses.activate
    def test_submit_reimbursement_with_currency(self):
        """Can submit reimbursement with explicit currency."""
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
        # Mock upload_file
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {"file": {"id": "f1", "url": "https://example.com/r.pdf"}}
                    ]
                }
            },
            status=200,
        )
        # Mock create_expense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-gbp",
                        "legacyId": 202,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf")
            temp_path = f.name

        try:
            result = client.submit_reimbursement(
                collective_slug="policyengine",
                description="GCP Jan 2026",
                amount_cents=205895,
                receipt_file=temp_path,
                currency="GBP",
                tags=["gcp"],
            )
            assert result["legacyId"] == 202

            # Verify currency was passed in the create_expense call
            create_request = responses.calls[3].request.body.decode()
            assert '"currency":"GBP"' in create_request.replace(" ", "")
        finally:
            os.unlink(temp_path)

    @responses.activate
    def test_submit_invoice_with_currency(self):
        """Can submit invoice with explicit currency."""
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
            json={"data": {"account": {"payoutMethods": [{"id": "pm-1"}]}}},
            status=200,
        )
        # Mock create_expense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "inv-gbp",
                        "legacyId": 203,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.submit_invoice(
            collective_slug="policyengine",
            description="EUR Consulting",
            amount_cents=500000,
            currency="EUR",
        )

        assert result["legacyId"] == 203

        create_request = responses.calls[2].request.body.decode()
        assert '"currency":"EUR"' in create_request.replace(" ", "")

    @responses.activate
    def test_create_expense_with_incurred_at(self):
        """Can create an expense with incurredAt date on items."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-dated",
                        "legacyId": 204,
                        "description": "GCP Jan 2026",
                        "amount": 205895,
                        "status": "DRAFT",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="GCP Jan 2026",
            amount_cents=205895,
            currency="GBP",
            incurred_at="2026-01-31",
        )

        assert result["legacyId"] == 204

        request_body = responses.calls[0].request.body.decode()
        assert "2026-01-31" in request_body

    @responses.activate
    def test_submit_reimbursement_with_incurred_at(self):
        """Can submit reimbursement with incurredAt date."""
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
        # Mock upload_file
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {"file": {"id": "f1", "url": "https://example.com/r.pdf"}}
                    ]
                }
            },
            status=200,
        )
        # Mock create_expense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-dated",
                        "legacyId": 205,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf")
            temp_path = f.name

        try:
            result = client.submit_reimbursement(
                collective_slug="policyengine",
                description="GCP Jan 2026",
                amount_cents=205895,
                receipt_file=temp_path,
                currency="GBP",
                incurred_at="2026-01-31",
            )
            assert result["legacyId"] == 205

            create_request = responses.calls[3].request.body.decode()
            assert "2026-01-31" in create_request
        finally:
            os.unlink(temp_path)


class TestSubmitInvoice:
    """Tests for submit_invoice high-level method."""

    @responses.activate
    def test_submit_invoice_without_file(self):
        """Can submit invoice without file attachment."""
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
            json={"data": {"account": {"payoutMethods": [{"id": "pm-1"}]}}},
            status=200,
        )
        # Mock create_expense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "inv-1",
                        "legacyId": 222,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")
        result = client.submit_invoice(
            collective_slug="policyengine",
            description="January Consulting",
            amount_cents=500000,
            tags=["consulting"],
        )

        assert result["legacyId"] == 222
        assert result["status"] == "PENDING"

    @responses.activate
    def test_submit_invoice_with_file(self):
        """Can submit invoice with file attachment."""
        # Mock get_me
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"slug": "test-user"}}},
            status=200,
        )
        # Mock get_payout_methods
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"account": {"payoutMethods": [{"id": "pm-2"}]}}},
            status=200,
        )
        # Mock upload_file
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [{"file": {"url": "https://example.com/invoice.pdf"}}]
                }
            },
            status=200,
        )
        # Mock create_expense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {"id": "inv-2", "legacyId": 333, "status": "DRAFT"}
                }
            },
            status=200,
        )

        client = OpenCollectiveClient(access_token="test_token")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"invoice pdf")
            temp_path = f.name

        try:
            result = client.submit_invoice(
                collective_slug="policyengine",
                description="Invoice with file",
                amount_cents=100000,
                invoice_file=temp_path,
            )
            assert result["legacyId"] == 333
        finally:
            os.unlink(temp_path)
