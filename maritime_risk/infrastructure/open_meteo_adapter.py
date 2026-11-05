"""Open-Meteo Live Hydrodynamics REST Adapter with Cubic Delta Kernel Smoothing.

Clean Architecture Infrastructure Layer:
1. Ingests live metocean wave telemetry via Open-Meteo Marine REST API using standard urllib.request.
2. Applies Cubic Delta Kernel (psi_3) smoothing to discrete hourly wave observations,
   eliminating gradient discontinuities before exposure to the Cox Proportional Hazards scaler.
3. Implements an automatic circuit breaker falling back to historical 90th percentile wave height
   and tagging output metadata with [ESTIMATED_HYDRODYNAMICS] on timeout or upstream failure.
4. Fully declarative: zero hardcoded URLs, coordinates, or version parameters (loaded from configs/external_feeds.json).

Author: Maritime domain researcher with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence
import urllib.error
import urllib.parse
import urllib.request
import numpy as np


@dataclass(frozen=True)
class OpenMeteoHydroResult:
    """Hydrodynamic metocean state evaluated from live or circuit-breaker fallback data."""

    corridor_id: str
    wave_height_m: float
    raw_wave_height_m: float
    wave_period_s: float
    is_estimated: bool
    metadata_tag: str
    endpoint_url: str
    timestamp_utc: str
    sample_size: int
    smoothing_kernel: str = "cubic_delta_psi3"

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to dictionary representation."""
        return asdict(self)

    def __iter__(self):
        """Allow unpacking as (wave_height_m, metadata_tag)."""
        return iter((self.wave_height_m, self.metadata_tag))


def cubic_delta_kernel(u: float) -> float:
    """Evaluate compact Cubic Delta Kernel psi_3(u) = (1 - |u|^3)^3 for |u| < 1.

    Guarantees continuous first and second derivatives, ensuring smooth,
    spike-free gradients for the hydrodynamic boarding feasibility scaler.
    """
    abs_u = abs(float(u))
    if abs_u >= 1.0:
        return 0.0
    return float((1.0 - (abs_u**3)) ** 3)


def smooth_wave_heights_cubic_delta(
    timestamps_hours: Sequence[float],
    wave_heights: Sequence[float],
    target_time_hour: Optional[float] = None,
    bandwidth_hours: float = 3.0,
    delta: float = 1.0,
) -> float:
    """Apply Cubic Delta Kernel smoothing to a discrete wave height sequence.

    Parameters
    ----------
    timestamps_hours : Sequence[float]
        Relative or absolute time coordinates for the wave observations in hours.
    wave_heights : Sequence[float]
        Observed significant wave heights (Hs) in meters.
    target_time_hour : Optional[float]
        Time coordinate at which to compute the smoothed Hs. Defaults to the latest point.
    bandwidth_hours : float
        Kernel window bandwidth in hours.
    delta : float
        Kernel scale parameter delta.

    Returns
    -------
    float
        Smoothed significant wave height Hs*(t) in meters.
    """
    if not wave_heights:
        return 0.0
    if len(wave_heights) == 1:
        return float(wave_heights[0])

    t_eval = (
        float(timestamps_hours[-1])
        if target_time_hour is None
        else float(target_time_hour)
    )
    h_eff = max(float(bandwidth_hours) * max(float(delta), 1e-4), 0.1)

    weighted_sum = 0.0
    weight_total = 0.0

    for t_i, hs_i in zip(timestamps_hours, wave_heights):
        u = (t_eval - float(t_i)) / h_eff
        w = cubic_delta_kernel(u)
        weighted_sum += w * float(hs_i)
        weight_total += w

    if weight_total < 1e-12:
        return float(wave_heights[-1])

    return float(weighted_sum / weight_total)


def load_external_feeds_config(config_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Load declarative external feeds configuration from disk."""
    if config_dir is not None:
        explicit_file = Path(config_dir) / "external_feeds.json"
        if explicit_file.exists():
            return json.loads(explicit_file.read_text(encoding="utf-8"))
        raise FileNotFoundError(
            f"External feeds configuration 'external_feeds.json' not found in specified directory: {config_dir}"
        )

    curr_file = Path(__file__).resolve()
    search_dirs = [
        curr_file.parent.parent.parent / "configs",
        curr_file.parent.parent / "configs",
        Path.cwd() / "configs",
    ]

    for c_dir in search_dirs:
        cfg_file = c_dir / "external_feeds.json"
        if cfg_file.exists():
            return json.loads(cfg_file.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        f"External feeds configuration 'external_feeds.json' not found in search paths: {[str(d) for d in search_dirs]}"
    )


class OpenMeteoHydroAdapter:
    """REST adapter for live metocean telemetry via Open-Meteo Marine API."""

    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        config_dir: Optional[Path | str] = None,
        db_connection: Optional[Any] = None,
    ) -> None:
        self.full_config = config or load_external_feeds_config(config_dir)
        self.meteo_cfg = self.full_config.get("open_meteo", {})
        self.db_conn = db_connection

    def _resolve_coordinates(self, corridor_id: str) -> tuple[float, float]:
        """Resolve centroid latitude and longitude for a given corridor ID from configuration."""
        bboxes = self.meteo_cfg.get("bounding_boxes", {})
        if corridor_id in bboxes:
            c_info = bboxes[corridor_id]
            if "centroid_lat" in c_info and "centroid_lon" in c_info:
                return float(c_info["centroid_lat"]), float(c_info["centroid_lon"])
            lat = (float(c_info["latitude_min"]) + float(c_info["latitude_max"])) / 2.0
            lon = (float(c_info["longitude_min"]) + float(c_info["longitude_max"])) / 2.0
            return lat, lon

        default_cid = self.meteo_cfg.get("default_corridor_id")
        if default_cid and default_cid in bboxes:
            c_info = bboxes[default_cid]
            if "centroid_lat" in c_info and "centroid_lon" in c_info:
                return float(c_info["centroid_lat"]), float(c_info["centroid_lon"])
            lat = (float(c_info["latitude_min"]) + float(c_info["latitude_max"])) / 2.0
            lon = (float(c_info["longitude_min"]) + float(c_info["longitude_max"])) / 2.0
            return lat, lon

        raise KeyError(
            f"Coordinates for corridor '{corridor_id}' not found in external feeds configuration."
        )

    def _get_historical_fallback_wave_height(self) -> float:
        """Query SQLite database for 90th percentile historical wave height or return config default."""
        cb_cfg = self.meteo_cfg.get("circuit_breaker", {})
        fallback_default = float(cb_cfg.get("default_fallback_wave_height_m", 2.15))
        percentile = float(cb_cfg.get("fallback_historical_percentile", 90.0))

        if self.db_conn is not None:
            try:
                cursor = self.db_conn.cursor()
                try:
                    cursor.execute(
                        "SELECT significant_wave_height_m FROM civilian_sensor_telemetry "
                        "WHERE significant_wave_height_m IS NOT NULL"
                    )
                except sqlite3.OperationalError:
                    cursor.execute(
                        "SELECT significant_wave_height_m FROM civilian_telemetry "
                        "WHERE significant_wave_height_m IS NOT NULL"
                    )
                rows = cursor.fetchall()
                if rows:
                    vals = [float(r[0]) for r in rows if r[0] is not None]
                    if vals:
                        return float(np.percentile(vals, percentile))
            except Exception:
                pass

        return fallback_default

    def fetch_live_hydrodynamics(
        self,
        corridor_id: Optional[str] = None,
        target_timestamp: Optional[datetime] = None,
        force_circuit_breaker: bool = False,
    ) -> OpenMeteoHydroResult:
        """Fetch real-time wave heights via Open-Meteo REST API or activate circuit breaker fallback."""
        if corridor_id is None:
            corridor_id = self.meteo_cfg.get("default_corridor_id")
            if not corridor_id:
                raise KeyError("No corridor_id supplied and default_corridor_id missing in configuration")

        now_utc = datetime.now(timezone.utc).isoformat()
        cb_cfg = self.meteo_cfg.get("circuit_breaker", {})
        fallback_tag = str(cb_cfg.get("fallback_tag", "[ESTIMATED_HYDRODYNAMICS]"))
        timeout_sec = float(cb_cfg.get("timeout_seconds", 10.0))
        if "api_endpoint" not in self.meteo_cfg:
            raise KeyError("Missing required 'api_endpoint' in open_meteo configuration")
        endpoint = str(self.meteo_cfg["api_endpoint"])

        if force_circuit_breaker:
            fallback_hs = self._get_historical_fallback_wave_height()
            return OpenMeteoHydroResult(
                corridor_id=corridor_id,
                wave_height_m=fallback_hs,
                raw_wave_height_m=fallback_hs,
                wave_period_s=7.5,
                is_estimated=True,
                metadata_tag=fallback_tag,
                endpoint_url=endpoint,
                timestamp_utc=now_utc,
                sample_size=0,
            )

        lat, lon = self._resolve_coordinates(corridor_id)
        hourly_vars = self.meteo_cfg.get("hourly_variables", ["wave_height", "wave_period"])
        query_params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": ",".join(hourly_vars),
            "timezone": "UTC",
        }
        url = f"{endpoint}?{urllib.parse.urlencode(query_params)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "maritime-tail-risk-engine/1.0 (Civilian Metocean Ingestion)"},
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        url, response.status, f"HTTP Error {response.status}", response.headers, None
                    )
                raw_bytes = response.read()
                data = json.loads(raw_bytes.decode("utf-8"))

            hourly_data = data.get("hourly", {})
            times = hourly_data.get("time", [])
            wave_heights = [float(h) for h in hourly_data.get("wave_height", []) if h is not None]
            wave_periods = [float(p) for p in hourly_data.get("wave_period", []) if p is not None]

            if not wave_heights:
                raise ValueError("Open-Meteo payload contained zero valid wave_height entries.")

            raw_latest_hs = float(wave_heights[-1])
            raw_latest_period = float(wave_periods[-1]) if wave_periods else 7.5

            # Apply Cubic Delta Kernel (psi_3) smoothing over the recent 24h window
            window_size = min(len(wave_heights), 24)
            recent_hs = wave_heights[-window_size:]
            time_hours = list(range(len(recent_hs)))

            k_cfg = self.meteo_cfg.get("cubic_delta_kernel", {})
            bw = float(k_cfg.get("bandwidth_hours", 3.0))
            delta_val = float(k_cfg.get("smoothing_parameter_delta", 1.0))

            smoothed_hs = smooth_wave_heights_cubic_delta(
                timestamps_hours=time_hours,
                wave_heights=recent_hs,
                target_time_hour=float(time_hours[-1]),
                bandwidth_hours=bw,
                delta=delta_val,
            )

            return OpenMeteoHydroResult(
                corridor_id=corridor_id,
                wave_height_m=smoothed_hs,
                raw_wave_height_m=raw_latest_hs,
                wave_period_s=raw_latest_period,
                is_estimated=False,
                metadata_tag="[LIVE_METOCEAN]",
                endpoint_url=endpoint,
                timestamp_utc=now_utc,
                sample_size=len(wave_heights),
            )

        except Exception:
            # Circuit breaker trip: fall back to 90th percentile historical baseline
            fallback_hs = self._get_historical_fallback_wave_height()
            return OpenMeteoHydroResult(
                corridor_id=corridor_id,
                wave_height_m=fallback_hs,
                raw_wave_height_m=fallback_hs,
                wave_period_s=7.5,
                is_estimated=True,
                metadata_tag=fallback_tag,
                endpoint_url=endpoint,
                timestamp_utc=now_utc,
                sample_size=0,
            )

    def fetch_wave_heights(
        self,
        corridor_id: Optional[str] = None,
        force_circuit_breaker: bool = False,
    ) -> tuple[float, str]:
        """Fetch significant wave height and status tag tuple."""
        res = self.fetch_live_hydrodynamics(
            corridor_id=corridor_id,
            force_circuit_breaker=force_circuit_breaker,
        )
        return res.wave_height_m, res.metadata_tag


def smooth_cubic_delta(
    h_s: Sequence[float] | float,
    bandwidth_hours: float = 3.0,
    delta: float = 1.0,
) -> float:
    """Apply Cubic Delta Kernel psi_3(u) smoothing to discrete wave heights.

    Parameters
    ----------
    h_s : Sequence[float] | float
        Observed wave heights or single wave height.
    bandwidth_hours : float
        Smoothing window bandwidth.
    delta : float
        Scale parameter delta.

    Returns
    -------
    float
        Smoothed significant wave height.
    """
    if isinstance(h_s, (int, float)):
        return float(h_s)
    if not h_s:
        return 0.0
    time_hours = list(range(len(h_s)))
    return smooth_wave_heights_cubic_delta(
        timestamps_hours=time_hours,
        wave_heights=h_s,
        bandwidth_hours=bandwidth_hours,
        delta=delta,
    )


def fetch_wave_heights(
    corridor_id: Optional[str] = None,
    force_circuit_breaker: bool = False,
    config: Optional[dict[str, Any]] = None,
    config_dir: Optional[Path | str] = None,
    db_connection: Optional[Any] = None,
) -> tuple[float, str]:
    """Convenience function returning (wave_height_m, metadata_tag) tuple."""
    adapter = OpenMeteoHydroAdapter(
        config=config,
        config_dir=config_dir,
        db_connection=db_connection,
    )
    return adapter.fetch_wave_heights(
        corridor_id=corridor_id,
        force_circuit_breaker=force_circuit_breaker,
    )


__all__ = [
    "OpenMeteoHydroResult",
    "OpenMeteoHydroAdapter",
    "cubic_delta_kernel",
    "smooth_wave_heights_cubic_delta",
    "smooth_cubic_delta",
    "fetch_wave_heights",
    "load_external_feeds_config",
]
