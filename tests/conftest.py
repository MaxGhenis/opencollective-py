"""Shared test fixtures and constants."""

import json

import pytest

from opencollective import OpenCollectiveClient

API_URL = "https://api.opencollective.com/graphql/v2"
# File uploads use frontend proxy due to infrastructure issues with direct API
# See: https://github.com/opencollective/opencollective-api/issues/11293
UPLOAD_URL = "https://opencollective.com/api/graphql/v2"


@pytest.fixture
def client():
    """Create a client with a test token."""
    return OpenCollectiveClient(access_token="test_token")


@pytest.fixture
def mock_token(tmp_path):
    """Create a mock token file and return its path."""
    token_dir = tmp_path / ".config" / "opencollective"
    token_dir.mkdir(parents=True)
    token_file = token_dir / "token.json"
    token_file.write_text(json.dumps({"access_token": "test_token"}))
    return str(token_file)
