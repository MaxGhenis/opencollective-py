"""Tests for OAuth2 authentication."""

import os
import tempfile

import pytest
import responses

from opencollective import OAuth2Handler

TOKEN_URL = "https://opencollective.com/oauth/token"


class TestOAuth2Handler:
    """Tests for OAuth2 authentication handler."""

    def test_handler_init(self):
        """Handler can be initialized with client credentials."""
        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        assert handler.client_id == "test_client_id"
        assert handler.client_secret == "test_client_secret"

    def test_handler_init_with_redirect_uri(self):
        """Handler accepts custom redirect URI."""
        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:9000/callback",
        )
        assert handler.redirect_uri == "http://localhost:9000/callback"

    def test_handler_default_redirect_uri(self):
        """Handler uses default redirect URI."""
        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        assert handler.redirect_uri == "http://localhost:8080/callback"

    def test_get_authorization_url(self):
        """Handler generates correct authorization URL."""
        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        url = handler.get_authorization_url(scope="expenses")

        assert "https://opencollective.com/oauth/authorize" in url
        assert "client_id=test_client_id" in url
        assert "scope=expenses" in url
        assert "response_type=code" in url

    @responses.activate
    def test_exchange_code_for_token(self):
        """Handler can exchange authorization code for token."""
        responses.add(
            responses.POST,
            TOKEN_URL,
            json={
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 7776000,
                "refresh_token": "test_refresh_token",
                "scope": "expenses",
            },
            status=200,
        )

        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        token_data = handler.exchange_code("auth_code_123")

        assert token_data["access_token"] == "test_access_token"
        assert token_data["refresh_token"] == "test_refresh_token"

    @responses.activate
    def test_refresh_token(self):
        """Handler can refresh an expired token."""
        responses.add(
            responses.POST,
            TOKEN_URL,
            json={
                "access_token": "new_access_token",
                "token_type": "Bearer",
                "expires_in": 7776000,
                "refresh_token": "new_refresh_token",
                "scope": "expenses",
            },
            status=200,
        )

        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        token_data = handler.refresh_access_token("old_refresh_token")

        assert token_data["access_token"] == "new_access_token"

    def test_save_and_load_token(self):
        """Handler can save and load tokens from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            token_file = f.name

        try:
            handler = OAuth2Handler(
                client_id="test_client_id",
                client_secret="test_client_secret",
                token_file=token_file,
            )

            token_data = {
                "access_token": "saved_token",
                "refresh_token": "saved_refresh",
            }
            handler.save_token(token_data)

            loaded = handler.load_token()
            assert loaded["access_token"] == "saved_token"
            assert loaded["refresh_token"] == "saved_refresh"
        finally:
            os.unlink(token_file)

    def test_load_token_missing_file(self):
        """Handler returns None for missing token file."""
        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
            token_file="/nonexistent/path/token.json",
        )

        result = handler.load_token()
        assert result is None

    @responses.activate
    def test_token_exchange_error(self):
        """Handler raises error on failed token exchange."""
        responses.add(
            responses.POST,
            TOKEN_URL,
            json={
                "error": "invalid_grant",
                "error_description": "Code expired",
            },
            status=400,
        )

        handler = OAuth2Handler(
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        with pytest.raises(Exception, match="Token exchange failed"):
            handler.exchange_code("expired_code")
