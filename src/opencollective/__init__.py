"""OpenCollective Python client."""

from opencollective.auth import OAuth2Handler
from opencollective.client import OpenCollectiveClient

__version__ = "0.1.0"
__all__ = ["OpenCollectiveClient", "OAuth2Handler"]
