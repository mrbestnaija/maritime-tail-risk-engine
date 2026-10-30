"""Core Domain Models & Temporal Invariants for Maritime Tail Risk.

Enforces:
1. Temporal paradox prevention (pub_time >= event_time).
2. Interval severity consistency (max_severity >= min_severity, bounds [0.0, 10.0]).
3. Spatial coordinate validation (lat in [-90, 90], lon in [-180, 180]).
4. Pure domain layer with ZERO dependencies on application or infrastructure.
"""

from __future__ import annotations

import math
from typing import Any, Optional
from pydantic import BaseModel, Field, root_validator


class GeoCoordinates(BaseModel):
    """Geographic coordinates in WGS-84 decimal degrees."""

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")

    def distance_to_nautical_miles(self, other: GeoCoordinates) -> float:
        """Haversine distance in nautical miles."""
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
        c = 2.0 * math.asin(math.sqrt(a))
        # 1 radian ~ 3440.065 nautical miles (Earth mean radius 6371 km)
        return c * 3440.065


class SeverityInterval(BaseModel):
    """Uncertainty interval for maritime security incident severity [0.0, 10.0]."""

    min_severity: float = Field(..., ge=0.0, le=10.0, description="Lower bound of severity")
    max_severity: float = Field(..., ge=0.0, le=10.0, description="Upper bound of severity")

    @root_validator
    def validate_interval(cls, values: dict[str, Any]) -> dict[str, Any]:
        min_sev = values.get("min_severity")
        max_sev = values.get("max_severity")
        if min_sev is not None and max_sev is not None and max_sev < min_sev:
            raise ValueError(
                f"Invalid severity interval: max_severity ({max_sev}) "
                f"must be >= min_severity ({min_sev})"
            )
        return values

    def union_with(self, other: SeverityInterval) -> SeverityInterval:
        """Return the union envelope: min of mins, max of maxes."""
        return SeverityInterval(
            min_severity=min(self.min_severity, other.min_severity),
            max_severity=max(self.max_severity, other.max_severity),
        )


class MaritimeIncident(BaseModel):
    """Domain entity representing a verified maritime security incident."""

    incident_id: str = Field(..., min_length=1, description="Unique incident identifier")
    event_time: int = Field(..., description="Unix timestamp of when incident occurred")
    pub_time: int = Field(..., description="Unix timestamp of when incident was reported/published")
    coordinates: GeoCoordinates
    severity: SeverityInterval
    feed_source: str = Field(..., min_length=1, description="OSINT reporting source (e.g. MDAT-GOG, IMB)")
    vessel_name: Optional[str] = None
    raw_payload: Optional[str] = None
    lineage_hash: str = Field(..., description="SHA-256 lineage digest of original report")

    @root_validator
    def validate_temporal_paradox(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Enforce strict temporal monotonicity: report cannot precede physical event."""
        event_time = values.get("event_time")
        pub_time = values.get("pub_time")
        if event_time is not None and pub_time is not None and pub_time < event_time:
            raise ValueError(
                f"Temporal paradox detected: publication timestamp ({pub_time}) "
                f"is strictly earlier than event occurrence timestamp ({event_time})"
            )
        return values
