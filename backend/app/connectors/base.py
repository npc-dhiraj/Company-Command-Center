"""Base connector interface and metadata definitions.

Every connector must subclass ``BaseConnector`` and provide metadata,
a Pydantic credentials schema, and implementations of
``validate_credentials`` and ``test_connection``.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ConnectorCategory(str, Enum):
    """Supported connector categories."""

    COMMUNICATION = "communication"
    DEVELOPMENT = "development"
    PRODUCTIVITY = "productivity"
    MEETINGS = "meetings"
    CRM = "crm"
    SUPPORT = "support"
    MONITORING = "monitoring"
    OTHER = "other"


class ConnectorMetadata(BaseModel):
    """Descriptive metadata for a connector provider."""

    provider_key: str
    display_name: str
    description: str
    category: ConnectorCategory


class ConnectorError(Exception):
    """A safe, user-displayable error raised by connectors.

    The message MUST NOT contain credentials, ciphertext, or any
    sensitive material — it will be shown to the end user.
    """

    def __init__(self, message: str) -> None:
        self.safe_message = message
        super().__init__(message)


class BaseConnector(ABC):
    """Abstract base class for all connectors.

    Subclasses must define:
    - ``metadata``: a ``ConnectorMetadata`` class attribute
    - ``credentials_schema``: a Pydantic model class describing the
      required credential fields
    - ``validate_credentials``: parse and validate raw credential dicts
    - ``test_connection``: verify connectivity with the external service
    """

    metadata: ConnectorMetadata
    credentials_schema: type[BaseModel]

    @abstractmethod
    async def validate_credentials(self, raw: dict[str, Any]) -> BaseModel:
        """Validate and parse raw credential data.

        Returns an instance of ``credentials_schema`` on success.
        Raises ``ConnectorError`` with a safe message on validation failure.
        """

    @abstractmethod
    async def test_connection(self, credentials: BaseModel) -> None:
        """Test connectivity using validated credentials.

        Returns ``None`` on success.
        Raises ``ConnectorError`` with a safe, user-displayable message
        on failure. Must NEVER log or expose credential values.
        """
