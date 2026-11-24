from contextvars import ContextVar
from typing import Optional, Any

_current_tenant: ContextVar[Optional[Any]] = ContextVar('current_tenant', default=None)

def get_current_tenant() -> Optional[Any]:
    """Retrieve the active tenant Organization instance from context."""
    return _current_tenant.get()

def set_current_tenant(tenant: Optional[Any]) -> None:
    """Set the active tenant Organization instance in context."""
    _current_tenant.set(tenant)

def clear_current_tenant() -> None:
    """Clear the active tenant Organization from context."""
    _current_tenant.set(None)
