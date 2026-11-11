"""OpenCollective Python client."""

from opencollective.auth import OAuth2Handler
from opencollective.client import OpenCollectiveClient, ReadOnlyError, read_only_enabled

__version__ = "0.2.1"
__all__ = [
    "OpenCollectiveClient",
    "OAuth2Handler",
    "ReadOnlyError",
    "read_only_enabled",
]
