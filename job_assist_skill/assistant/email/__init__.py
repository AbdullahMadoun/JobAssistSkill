"""Email module for application email generation."""

from .mailto_client import MailtoClient, get_mailto_client

__all__ = [
    "MailtoClient",
    "get_mailto_client",
]
