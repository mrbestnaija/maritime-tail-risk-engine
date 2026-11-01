"""Public Facade API for Maritime Tail Risk SDK.

External libraries, FastAPI microservices, and Jupyter notebooks can import this module:
    from maritime_risk.sdk import MaritimeRiskEngine, CorridorAuditResult
"""

from __future__ import annotations

from .application.engine import (
    COMMERCIAL_DISCLAIMER,
    CorridorAuditResult,
    MaritimeRiskEngine,
    MaritimeTailRiskEngine,
)
from .application.registry import PluginRegistry, default_registry

__all__ = [
    "COMMERCIAL_DISCLAIMER",
    "CorridorAuditResult",
    "MaritimeRiskEngine",
    "MaritimeTailRiskEngine",
    "PluginRegistry",
    "default_registry",
]
