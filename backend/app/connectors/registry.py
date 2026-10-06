"""Connector registry: register, look up, and list connector classes.

The production registry starts EMPTY in this phase.  Connectors are
registered at import time via ``register_connector()``.
"""

from app.connectors.base import BaseConnector

_registry: dict[str, type[BaseConnector]] = {}


def register_connector(cls: type[BaseConnector]) -> type[BaseConnector]:
    """Register a connector class by its ``metadata.provider_key``.

    Raises ``ValueError`` if a connector with the same provider key
    is already registered.
    """
    key = cls.metadata.provider_key
    if key in _registry:
        raise ValueError(
            f"Duplicate connector provider key: '{key}' is already registered"
        )
    _registry[key] = cls
    return cls


def get_connector(provider: str) -> type[BaseConnector]:
    """Return the connector class for *provider*.

    Raises ``KeyError`` if no connector is registered for that key.
    """
    try:
        return _registry[provider]
    except KeyError:
        raise KeyError(f"Unknown connector provider: '{provider}'") from None


def list_connectors() -> dict[str, type[BaseConnector]]:
    """Return a shallow copy of the current registry."""
    return dict(_registry)


def _clear_registry() -> None:
    """Remove all registered connectors.  **Test-only helper.**"""
    _registry.clear()
