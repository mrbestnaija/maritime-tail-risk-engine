"""Core Domain Models & Temporal Invariants for Maritime Tail Risk.

Enforces:
1. Temporal paradox prevention (pub_time >= event_time).
2. Interval severity consistency (max_severity >= min_severity, bounds [0.0, 10.0]).
3. Spatial coordinate validation (lat in [-90, 90], lon in [-180, 180]).
4. Pure domain layer with ZERO dependencies on application or infrastructure.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, root_validator


class TemporalParadoxError(ValueError):
    """Raised when publication/reporting timestamp strictly precedes physical observation/event."""

    pass


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

    @root_validator(skip_on_failure=True)
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

    @root_validator(skip_on_failure=True)
    def validate_temporal_paradox(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Enforce strict temporal monotonicity: report cannot precede physical event."""
        event_time = values.get("event_time")
        pub_time = values.get("pub_time")
        if event_time is not None and pub_time is not None and pub_time < event_time:
            raise TemporalParadoxError(
                f"Temporal paradox detected: publication timestamp ({pub_time}) "
                f"is strictly earlier than event occurrence timestamp ({event_time})"
            )
        return values


from .specs import DEFAULT_CORRIDOR_ID


class CivilianSensorTelemetry(BaseModel):
    """Verifiable public civilian satellite and oceanographic telemetry."""

    telemetry_id: str = Field(..., min_length=1, description="Unique telemetry identifier")
    corridor_id: str = Field(
        default=DEFAULT_CORRIDOR_ID,
        description="Corridor identifier (e.g. fairway bounds)",
    )
    observation_timestamp: datetime = Field(
        ..., description="UTC when satellite/buoy observed the corridor"
    )
    publication_timestamp: datetime = Field(
        ..., description="UTC when public feed released the data"
    )
    sar_provider: Literal["GFW_SENTINEL1_SAR"] = "GFW_SENTINEL1_SAR"
    metocean_provider: Literal["COPERNICUS_ERA5_METOCEAN", "OPEN_METEO_MARINE"] = (
        "COPERNICUS_ERA5_METOCEAN"
    )
    ais_provider: Literal["IMF_PORTWATCH_AIS", "PUBLIC_AISHUB"] = "IMF_PORTWATCH_AIS"
    significant_wave_height_m: float = Field(
        ..., ge=0.0, le=25.0, description="Significant Wave Height Hs (meters)"
    )
    sar_dark_vessel_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of Sentinel-1 radar targets lacking public AIS"
    )
    anchorage_waiting_hours: float = Field(
        ..., ge=0.0, description="Median vessel loitering/queue duration in fairway approach"
    )
    viirs_flaring_continuity_idx: float = Field(
        default=1.0, ge=0.0, le=1.0, description="NOAA VIIRS Nightfire shortwave IR flaring continuity index"
    )
    mothership_loitering_index: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Sentinel-1 / AIS PAG mothership loitering proximity index"
    )
    distance_pmsc_km: float = Field(
        default=180.0, ge=0.0, le=2000.0, description="Distance to nearest private maritime security escort vessel in km"
    )

    class Config:
        frozen = True

    @root_validator(skip_on_failure=True)
    def validate_temporal_monotonicity(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Enforce publication_timestamp >= observation_timestamp."""
        obs = values.get("observation_timestamp")
        pub = values.get("publication_timestamp")
        if obs is not None and pub is not None:
            if isinstance(obs, datetime) and isinstance(pub, datetime):
                if obs.tzinfo is not None and pub.tzinfo is None:
                    pub = pub.replace(tzinfo=obs.tzinfo)
                elif obs.tzinfo is None and pub.tzinfo is not None:
                    obs = obs.replace(tzinfo=pub.tzinfo)
            if pub < obs:
                raise TemporalParadoxError(
                    f"Temporal paradox detected: publication timestamp ({pub}) "
                    f"is strictly earlier than observation timestamp ({obs})"
                )
        return values

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            super().__setattr__(name, value)
        except Exception as e:
            if "frozen" in str(e).lower():
                raise TypeError(str(e)) from e
            raise
