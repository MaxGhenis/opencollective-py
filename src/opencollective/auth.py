"""OAuth2 authentication for OpenCollective."""

import json
import os
from urllib.parse import urlencode

import requests

AUTH_URL = "https://opencollective.com/oauth/authorize"
TOKEN_URL = "https://opencollective.com/oauth/token"
DEFAULT_REDIRECT_URI = "http://localhost:8080/callback"


class OAuth2Handler:
    """Handle OAuth2 authentication with OpenCollective."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str | None = None,
        token_file: str | None = None,
    ):
        """Initialize the OAuth2 handler.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            redirect_uri: Callback URL for OAuth flow.
            token_file: Path to store/load tokens.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri or DEFAULT_REDIRECT_URI
        self.token_file = token_file

    def get_authorization_url(self, scope: str = "expenses") -> str:
        """Get the URL for user authorization.

        Args:
            scope: OAuth2 scope (e.g., "expenses").

        Returns:
            URL to redirect user to for authorization.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def _token_request(self, data: dict, error_label: str) -> dict:
        """Make a token request to the OAuth2 token endpoint.

        Args:
            data: Form data for the token request.
            error_label: Label for error messages (e.g. "Token exchange").

        Returns:
            Token data from the response.

        Raises:
            Exception: If the request fails.
        """
        response = requests.post(TOKEN_URL, data=data)

        if response.status_code != 200:
            error = response.json().get("error_description", response.text)
            raise Exception(f"{error_label} failed: {error}")

        token_data = response.json()

        if self.token_file:
            self.save_token(token_data)

        return token_data

    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from callback.

        Returns:
            Token data including access_token, refresh_token, etc.

        Raises:
            Exception: If token exchange fails.
        """
        return self._token_request(
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            error_label="Token exchange",
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token.

        Args:
            refresh_token: The refresh token.

        Returns:
            New token data.

        Raises:
            Exception: If refresh fails.
        """
        return self._token_request(
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            },
            error_label="Token refresh",
        )

    def save_token(self, token_data: dict) -> None:
        """Save token data to file.

        Args:
            token_data: Token data to save.
        """
        if not self.token_file:
            return

        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
        with open(self.token_file, "w") as f:
            json.dump(token_data, f)

    def load_token(self) -> dict | None:
        """Load token data from file.

        Returns:
            Token data or None if file doesn't exist.
        """
        if not self.token_file or not os.path.exists(self.token_file):
            return None

        with open(self.token_file) as f:
            return json.load(f)

    def get_access_token(self) -> str | None:
        """Get the current access token.

        Returns:
            Access token or None if not available.
        """
        token_data = self.load_token()
        if token_data:
            return token_data.get("access_token")
        return None
