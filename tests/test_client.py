"""Tests for OpenCollective client."""

import os
import tempfile
from io import BytesIO

import pytest
import responses

from opencollective import OpenCollectiveClient

from .conftest import API_URL, UPLOAD_URL


class TestOpenCollectiveClient:
    """Tests for the OpenCollective API client."""

    def test_client_init_with_token(self, client):
        """Client can be initialized with an access token."""
        assert client.access_token == "test_token"

    def test_client_init_without_token_raises(self):
        """Client raises error without token."""
        with pytest.raises(ValueError, match="access_token is required"):
            OpenCollectiveClient()

    @responses.activate
    def test_get_collective(self, client):
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

        collective = client.get_collective("policyengine")

        assert collective["slug"] == "policyengine"
        assert collective["name"] == "PolicyEngine"
        assert collective["currency"] == "USD"

    @responses.activate
    def test_get_expenses(self, client):
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

        result = client.get_expenses("policyengine", limit=10)

        assert result["totalCount"] == 2
        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["description"] == "Cloud services"
        assert result["nodes"][0]["amount"] == 10000

    @responses.activate
    def test_get_expenses_with_status_filter(self, client):
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

        result = client.get_expenses("policyengine", status="PENDING")

        assert result["totalCount"] == 1
        assert result["nodes"][0]["status"] == "PENDING"

    @responses.activate
    def test_approve_expense(self, client):
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

        result = client.approve_expense("exp2")

        assert result["status"] == "APPROVED"

    @responses.activate
    def test_reject_expense(self, client):
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

        result = client.reject_expense("exp2", message="Invalid receipt")

        assert result["status"] == "REJECTED"

    @responses.activate
    def test_create_expense(self, client):
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

        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Software subscription",
            amount_cents=2000,
        )

        assert result["description"] == "Software subscription"
        assert result["status"] == "DRAFT"

    @responses.activate
    def test_create_expense_with_attachments(self, client):
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

        request_body = responses.calls[0].request.body.decode()
        assert "attachedFiles" in request_body
        assert "https://example.com/receipt.pdf" in request_body

    @responses.activate
    def test_create_invoice_expense(self, client):
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

        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Consulting services",
            amount_cents=100000,
            expense_type="INVOICE",
            invoice_url="https://example.com/invoice.pdf",
        )

        assert result["description"] == "Consulting services"

        request_body = responses.calls[0].request.body.decode()
        assert "invoiceFile" in request_body
        assert "https://example.com/invoice.pdf" in request_body

    @responses.activate
    def test_get_payout_methods(self, client):
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

        methods = client.get_payout_methods("max-ghenis")

        assert len(methods) == 2
        assert methods[0]["id"] == "pm_abc123"
        assert methods[0]["type"] == "BANK_ACCOUNT"
        assert methods[1]["type"] == "PAYPAL"

    @responses.activate
    def test_create_expense_with_payout_method(self, client):
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

        result = client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Cloud services",
            amount_cents=10000,
            payout_method_id="pm_abc123",
        )

        assert result["description"] == "Cloud services"
        assert result["status"] == "DRAFT"

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
    def test_http_error_handling(self, client):
        """Client handles HTTP errors."""
        responses.add(
            responses.POST,
            API_URL,
            status=500,
        )

        with pytest.raises(Exception):
            client.get_collective("policyengine")


class TestUploadFile:
    """Tests for file upload functionality."""

    @responses.activate
    def test_upload_file_from_path(self, client):
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

            request = responses.calls[0].request
            assert b"operations" in request.body
            assert b"EXPENSE_ATTACHED_FILE" in request.body
        finally:
            os.unlink(temp_path)

    @responses.activate
    def test_upload_file_from_file_object(self, client):
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

        file_obj = BytesIO(b"test image content")
        result = client.upload_file(
            file_obj, filename="receipt.png", kind="EXPENSE_ITEM"
        )

        assert (
            result["url"]
            == "https://opencollective-production.s3.us-west-1.amazonaws.com/def456.png"
        )
        assert result["name"] == "receipt.png"

        request = responses.calls[0].request
        assert b"EXPENSE_ITEM" in request.body

    @responses.activate
    def test_upload_file_with_custom_kind(self, client):
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

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"test invoice content")
            temp_path = f.name

        try:
            result = client.upload_file(temp_path, kind="EXPENSE_INVOICE")
            assert (
                result["url"]
                == "https://opencollective-production.s3.us-west-1.amazonaws.com/ghi789.pdf"
            )

            request = responses.calls[0].request
            assert b"EXPENSE_INVOICE" in request.body
        finally:
            os.unlink(temp_path)

    def test_upload_file_not_found(self, client):
        """Raises FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            client.upload_file("/nonexistent/path/to/file.pdf")

    @responses.activate
    def test_upload_file_api_error(self, client):
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
            status=200,
        )

        file_obj = BytesIO(b"test content")

        with pytest.raises(Exception, match="Invalid file type"):
            client.upload_file(file_obj, filename="test.txt")

    @responses.activate
    def test_upload_file_mime_type_detection(self, client):
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

        file_obj = BytesIO(b"fake png content")
        result = client.upload_file(file_obj, filename="image.png")

        assert result["type"] == "image/png"
        assert result["name"] == "image.png"

        request = responses.calls[0].request
        assert b"image/png" in request.body


class TestGetMe:
    """Tests for get_me method."""

    @responses.activate
    def test_get_me(self, client):
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

        me = client.get_me()

        assert me["id"] == "user-abc123"
        assert me["slug"] == "max-ghenis"
        assert me["name"] == "Max Ghenis"


class TestDeleteExpense:
    """Tests for delete_expense method."""

    @responses.activate
    def test_delete_expense(self, client):
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

        result = client.delete_expense("exp-abc123")

        assert result["id"] == "exp-abc123"
        assert result["legacyId"] == 12345


class TestSubmitReimbursement:
    """Tests for submit_reimbursement high-level method."""

    @responses.activate
    def test_submit_reimbursement_with_pdf(self, client):
        """Can submit reimbursement with PDF receipt."""
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"id": "user-123", "slug": "max-ghenis"}}},
            status=200,
        )
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
    def test_submit_reimbursement_with_explicit_payee(self, client):
        """Can submit reimbursement with explicit payee slug."""
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
    def test_create_expense_with_currency(self, client):
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

        request_body = responses.calls[0].request.body.decode()
        assert '"currency":"GBP"' in request_body.replace(" ", "")

    @responses.activate
    def test_create_expense_without_currency_omits_field(self, client):
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

        client.create_expense(
            collective_slug="policyengine",
            payee_slug="max-ghenis",
            description="Test",
            amount_cents=1000,
        )

        request_body = responses.calls[0].request.body.decode()
        no_currency = '"currency"' not in request_body
        null_currency = '"currency":null' in request_body.replace(" ", "")
        assert no_currency or null_currency

    @responses.activate
    def test_submit_reimbursement_with_currency(self, client):
        """Can submit reimbursement with explicit currency."""
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"id": "user-123", "slug": "max-ghenis"}}},
            status=200,
        )
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

            create_request = responses.calls[3].request.body.decode()
            assert '"currency":"GBP"' in create_request.replace(" ", "")
        finally:
            os.unlink(temp_path)

    @responses.activate
    def test_submit_invoice_with_currency(self, client):
        """Can submit invoice with explicit currency."""
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"slug": "max-ghenis"}}},
            status=200,
        )
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"account": {"payoutMethods": [{"id": "pm-1"}]}}},
            status=200,
        )
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
    def test_create_expense_with_incurred_at(self, client):
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
    def test_submit_reimbursement_with_incurred_at(self, client):
        """Can submit reimbursement with incurredAt date."""
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"id": "user-123", "slug": "max-ghenis"}}},
            status=200,
        )
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
    def test_submit_invoice_without_file(self, client):
        """Can submit invoice without file attachment."""
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"slug": "max-ghenis"}}},
            status=200,
        )
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"account": {"payoutMethods": [{"id": "pm-1"}]}}},
            status=200,
        )
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

        result = client.submit_invoice(
            collective_slug="policyengine",
            description="January Consulting",
            amount_cents=500000,
            tags=["consulting"],
        )

        assert result["legacyId"] == 222
        assert result["status"] == "PENDING"

    @responses.activate
    def test_submit_invoice_with_file(self, client):
        """Can submit invoice with file attachment."""
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"me": {"slug": "test-user"}}},
            status=200,
        )
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"account": {"payoutMethods": [{"id": "pm-2"}]}}},
            status=200,
        )
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


class TestFromTokenFile:
    """Tests for from_token_file class method."""

    def test_from_token_file(self, mock_token, monkeypatch):
        """Can create client from token file."""
        monkeypatch.setattr("opencollective.client.TOKEN_FILE", mock_token)
        client = OpenCollectiveClient.from_token_file()
        assert client.access_token == "test_token"

    def test_from_token_file_custom_path(self, mock_token):
        """Can create client from custom token file path."""
        client = OpenCollectiveClient.from_token_file(mock_token)
        assert client.access_token == "test_token"

    def test_from_token_file_missing(self, tmp_path):
        """Raises FileNotFoundError when token file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            OpenCollectiveClient.from_token_file(str(tmp_path / "nonexistent.json"))


class TestApproveExpenseByLegacyId:
    """Tests for approve/reject by legacy ID."""

    @responses.activate
    def test_approve_by_legacy_id(self, client):
        """Can approve expense using legacy ID (integer)."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp-abc",
                        "legacyId": 285182,
                        "description": "Test",
                        "status": "APPROVED",
                    }
                }
            },
            status=200,
        )

        result = client.approve_expense(285182)
        assert result["status"] == "APPROVED"
        assert result["legacyId"] == 285182

    @responses.activate
    def test_approve_by_string_id(self, client):
        """Can still approve using string internal ID."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp-abc",
                        "legacyId": 123,
                        "status": "APPROVED",
                    }
                }
            },
            status=200,
        )

        result = client.approve_expense("exp-abc")
        assert result["status"] == "APPROVED"

    @responses.activate
    def test_reject_by_legacy_id(self, client):
        """Can reject expense using legacy ID."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "processExpense": {
                        "id": "exp-abc",
                        "legacyId": 999,
                        "status": "REJECTED",
                    }
                }
            },
            status=200,
        )

        result = client.reject_expense(999, message="Bad receipt")
        assert result["status"] == "REJECTED"


class TestGetExpense:
    """Tests for get_expense (single expense by legacy ID)."""

    @responses.activate
    def test_get_expense_by_legacy_id(self, client):
        """Can fetch a single expense by legacy ID."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expense": {
                        "id": "exp-abc",
                        "legacyId": 285182,
                        "description": "OpenAI expenses",
                        "amount": 247838,
                        "currency": "USD",
                        "status": "PENDING",
                        "createdAt": "2026-02-12T00:00:00Z",
                        "createdByAccount": {
                            "slug": "max-ghenis",
                            "name": "Max Ghenis",
                        },
                        "payee": {"slug": "max-ghenis", "name": "Max Ghenis"},
                        "items": [
                            {
                                "id": "item-1",
                                "description": "ChatGPT Plus",
                                "amount": 28000,
                                "url": "https://example.com/receipt.pdf",
                                "incurredAt": "2024-03-08T00:00:00Z",
                            }
                        ],
                    }
                }
            },
            status=200,
        )

        result = client.get_expense(285182)
        assert result["legacyId"] == 285182
        assert result["description"] == "OpenAI expenses"
        assert result["createdByAccount"]["slug"] == "max-ghenis"
        assert len(result["items"]) == 1

    @responses.activate
    def test_get_expense_not_found(self, client):
        """Raises on expense not found."""
        responses.add(
            responses.POST,
            API_URL,
            json={"data": {"expense": None}},
            status=200,
        )

        result = client.get_expense(999999)
        assert result is None


class TestGetExpensesCreatedBy:
    """Tests for get_expenses including createdByAccount."""

    @responses.activate
    def test_get_expenses_includes_created_by(self, client):
        """get_expenses query includes createdByAccount field."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 1,
                        "nodes": [
                            {
                                "id": "exp1",
                                "legacyId": 100,
                                "description": "Test",
                                "amount": 5000,
                                "currency": "USD",
                                "type": "RECEIPT",
                                "status": "PAID",
                                "createdAt": "2026-01-01T00:00:00Z",
                                "payee": {"name": "Max", "slug": "max-ghenis"},
                                "createdByAccount": {
                                    "slug": "max-ghenis",
                                    "name": "Max Ghenis",
                                },
                                "tags": [],
                                "items": [],
                            }
                        ],
                    }
                }
            },
            status=200,
        )

        result = client.get_expenses("policyengine")
        request_body = responses.calls[0].request.body.decode()
        assert "createdByAccount" in request_body
        assert result["nodes"][0]["createdByAccount"]["slug"] == "max-ghenis"


class TestGetExpensesStatusFix:
    """Tests for fix #1: get_expenses status type should be array."""

    @responses.activate
    def test_get_expenses_status_variable_type_is_array(self, client):
        """GraphQL query should use [ExpenseStatusFilter] array type."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 1,
                        "nodes": [
                            {
                                "id": "exp1",
                                "legacyId": 100,
                                "description": "Test",
                                "amount": 5000,
                                "currency": "USD",
                                "type": "RECEIPT",
                                "status": "PENDING",
                                "createdAt": "2026-01-01T00:00:00Z",
                                "payee": {"name": "Test User", "slug": "test-user"},
                                "tags": [],
                                "items": [],
                            }
                        ],
                    }
                }
            },
            status=200,
        )

        client.get_expenses("test-collective", status="PENDING")

        request_body = responses.calls[0].request.body.decode()
        # The variable type declaration must use array syntax
        assert "[ExpenseStatusFilter]" in request_body

    @responses.activate
    def test_get_expenses_status_sent_as_array(self, client):
        """When a status is provided, it should be sent as a single-element array."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 0,
                        "nodes": [],
                    }
                }
            },
            status=200,
        )

        client.get_expenses("test-collective", status="APPROVED")

        import json as json_mod

        request_body = json_mod.loads(responses.calls[0].request.body.decode())
        # The status variable must be a list
        assert isinstance(request_body["variables"]["status"], list)
        assert request_body["variables"]["status"] == ["APPROVED"]


class TestGetExpensesItems:
    """Tests for fix #3: get_expenses should include items in the response."""

    @responses.activate
    def test_get_expenses_includes_items_in_query(self, client):
        """Query should request items with standard fields."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 1,
                        "nodes": [
                            {
                                "id": "exp1",
                                "legacyId": 100,
                                "description": "Cloud hosting",
                                "amount": 15000,
                                "currency": "USD",
                                "type": "RECEIPT",
                                "status": "PAID",
                                "createdAt": "2026-01-15T00:00:00Z",
                                "payee": {"name": "Dev", "slug": "dev"},
                                "tags": ["hosting"],
                                "items": [
                                    {
                                        "id": "item1",
                                        "description": "January hosting",
                                        "amount": 15000,
                                        "url": "https://example.com/receipt.pdf",
                                        "incurredAt": "2026-01-15T00:00:00Z",
                                    }
                                ],
                            }
                        ],
                    }
                }
            },
            status=200,
        )

        result = client.get_expenses("test-collective")

        # The query must include items subfields
        request_body = responses.calls[0].request.body.decode()
        assert "items" in request_body

        # The response should contain items
        expense = result["nodes"][0]
        assert "items" in expense
        assert len(expense["items"]) == 1
        assert expense["items"][0]["id"] == "item1"
        assert expense["items"][0]["description"] == "January hosting"
        assert expense["items"][0]["amount"] == 15000

    @responses.activate
    def test_get_expenses_items_fields_in_query(self, client):
        """Items subquery includes all required fields."""
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "expenses": {
                        "totalCount": 0,
                        "nodes": [],
                    }
                }
            },
            status=200,
        )

        client.get_expenses("test-collective")

        request_body = responses.calls[0].request.body.decode()
        # Verify the query requests all required item fields
        assert "items" in request_body
        # Check that the query includes the expected subfields for items
        # These should appear in the query string after "items {"
        for field in ["id", "description", "amount", "url", "incurredAt"]:
            assert field in request_body


class TestSubmitMultiItemReimbursement:
    """Tests for feature #2: submit_multi_item_reimbursement method."""

    @responses.activate
    def test_submit_multi_item_reimbursement_basic(self, client):
        """Can submit a reimbursement with multiple items and receipts."""
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
        # Mock two file uploads (one per item)
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {
                            "file": {
                                "id": "file-1",
                                "url": "https://example.com/receipt1.pdf",
                            }
                        }
                    ]
                }
            },
            status=200,
        )
        responses.add(
            responses.POST,
            UPLOAD_URL,
            json={
                "data": {
                    "uploadFile": [
                        {
                            "file": {
                                "id": "file-2",
                                "url": "https://example.com/receipt2.pdf",
                            }
                        }
                    ]
                }
            },
            status=200,
        )
        # Mock createExpense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-multi",
                        "legacyId": 50000,
                        "description": "Conference travel",
                        "amount": 75000,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f1:
            f1.write(b"receipt 1 pdf")
            path1 = f1.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f2:
            f2.write(b"receipt 2 pdf")
            path2 = f2.name

        try:
            result = client.submit_multi_item_reimbursement(
                collective_slug="policyengine",
                description="Conference travel",
                items=[
                    {
                        "amount_cents": 50000,
                        "description": "Flight ticket",
                        "receipt_file": path1,
                        "incurred_at": "2026-03-01",
                    },
                    {
                        "amount_cents": 25000,
                        "description": "Hotel stay",
                        "receipt_file": path2,
                        "incurred_at": "2026-03-02",
                    },
                ],
                tags=["travel", "conference"],
            )

            assert result["legacyId"] == 50000
            assert result["status"] == "PENDING"

            # Verify the createExpense request has two items
            import json as json_mod

            create_request = json_mod.loads(responses.calls[4].request.body.decode())
            expense_input = create_request["variables"]["expense"]
            assert len(expense_input["items"]) == 2
            assert expense_input["items"][0]["description"] == "Flight ticket"
            assert expense_input["items"][0]["amount"] == 50000
            assert expense_input["items"][1]["description"] == "Hotel stay"
            assert expense_input["items"][1]["amount"] == 25000
            assert expense_input["type"] == "RECEIPT"
        finally:
            os.unlink(path1)
            os.unlink(path2)

    @responses.activate
    def test_submit_multi_item_with_explicit_payee(self, client):
        """Can submit multi-item reimbursement with explicit payee and payout method."""
        # No get_me or get_payout_methods needed when both are provided
        # Mock file upload
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
        # Mock createExpense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-explicit",
                        "legacyId": 50001,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"receipt pdf")
            path = f.name

        try:
            result = client.submit_multi_item_reimbursement(
                collective_slug="policyengine",
                description="Single item multi method",
                items=[
                    {
                        "amount_cents": 10000,
                        "description": "Software license",
                        "receipt_file": path,
                        "incurred_at": "2026-02-01",
                    },
                ],
                payee_slug="explicit-user",
                payout_method_id="pm-456",
            )
            assert result["legacyId"] == 50001
        finally:
            os.unlink(path)

    @responses.activate
    def test_submit_multi_item_with_currency(self, client):
        """Can submit multi-item reimbursement with explicit currency."""
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
        # Mock file upload
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
        # Mock createExpense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-gbp-multi",
                        "legacyId": 50002,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"pdf")
            path = f.name

        try:
            result = client.submit_multi_item_reimbursement(
                collective_slug="policyengine",
                description="GBP expense",
                items=[
                    {
                        "amount_cents": 5000,
                        "description": "UK purchase",
                        "receipt_file": path,
                        "incurred_at": "2026-01-15",
                    },
                ],
                currency="GBP",
            )
            assert result["legacyId"] == 50002

            import json as json_mod

            create_request = json_mod.loads(responses.calls[3].request.body.decode())
            assert create_request["variables"]["expense"].get("currency") == "GBP"
        finally:
            os.unlink(path)

    @responses.activate
    def test_submit_multi_item_uploads_each_receipt(self, client):
        """Each item's receipt_file should be uploaded separately."""
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
            json={"data": {"account": {"payoutMethods": [{"id": "pm-1"}]}}},
            status=200,
        )
        # Mock 3 file uploads
        for i in range(3):
            responses.add(
                responses.POST,
                UPLOAD_URL,
                json={
                    "data": {
                        "uploadFile": [
                            {
                                "file": {
                                    "id": f"file-{i}",
                                    "url": f"https://example.com/receipt{i}.pdf",
                                }
                            }
                        ]
                    }
                },
                status=200,
            )
        # Mock createExpense
        responses.add(
            responses.POST,
            API_URL,
            json={
                "data": {
                    "createExpense": {
                        "id": "exp-3items",
                        "legacyId": 50003,
                        "status": "PENDING",
                    }
                }
            },
            status=200,
        )

        temp_paths = []
        try:
            items = []
            for i in range(3):
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(f"receipt {i}".encode())
                    temp_paths.append(f.name)
                    items.append(
                        {
                            "amount_cents": 1000 * (i + 1),
                            "description": f"Item {i + 1}",
                            "receipt_file": f.name,
                            "incurred_at": f"2026-01-0{i + 1}",
                        }
                    )

            result = client.submit_multi_item_reimbursement(
                collective_slug="policyengine",
                description="Three items",
                items=items,
            )

            assert result["legacyId"] == 50003
            # 2 API calls (get_me, get_payout) + 3 uploads + 1 create = 6
            assert len(responses.calls) == 6
            # Verify 3 upload calls went to UPLOAD_URL
            upload_calls = [c for c in responses.calls if c.request.url == UPLOAD_URL]
            assert len(upload_calls) == 3
        finally:
            for p in temp_paths:
                os.unlink(p)
