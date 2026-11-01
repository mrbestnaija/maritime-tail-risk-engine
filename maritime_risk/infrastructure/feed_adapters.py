"""Standardized MetOcean and Satellite Telemetry Feed Adapters.

Provides pluggable adapters for raw Copernicus MetOcean and Global Fishing Watch (GFW) feeds.
"""

from __future__ import annotations

from ..application.registry import CopernicusGFWStandardizedAdapter

__all__ = [
    "CopernicusGFWStandardizedAdapter",
]
