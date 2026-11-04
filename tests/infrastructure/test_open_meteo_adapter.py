"""Deterministic Test Suite for Open-Meteo Live Hydrodynamics REST Adapter.

Verifies:
1. Mathematical invariants of Cubic Delta Kernel (psi_3) smoothing (continuity, vanishing boundaries, symmetry).
2. Declarative configuration loading with zero hardcoded URLs or coordinates.
3. Circuit breaker degradation on timeout/failure falling back to 90th percentile historical Hs with [ESTIMATED_HYDRODYNAMICS].
4. SQLite fallback querying canonical civilian_sensor_telemetry and fallback civilian_telemetry.
5. Successful response parsing with Cubic Delta smoothing and [LIVE_METOCEAN] metadata tag.
6. Root infrastructure shim compatibility.
"""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

# Test import from canonical package
from maritime_risk.infrastructure.open_meteo_adapter import (
    OpenMeteoHydroAdapter,
    OpenMeteoHydroResult,
    cubic_delta_kernel,
    load_external_feeds_config,
    smooth_wave_heights_cubic_delta,
)
# Test import from root forwarder shim
import infrastructure.open_meteo_adapter as shim_adapter


def test_root_shim_exports_match():
    """Verify infrastructure/open_meteo_adapter.py forwarder exports all symbols."""
    assert shim_adapter.OpenMeteoHydroAdapter is OpenMeteoHydroAdapter
    assert shim_adapter.OpenMeteoHydroResult is OpenMeteoHydroResult
    assert shim_adapter.cubic_delta_kernel is cubic_delta_kernel
    assert shim_adapter.smooth_wave_heights_cubic_delta is smooth_wave_heights_cubic_delta


def test_cubic_delta_kernel_mathematical_invariants():
    """Verify psi_3(u) = (1 - |u|^3)^3 satisfies compact kernel boundary conditions."""
    # Peak at origin
    assert cubic_delta_kernel(0.0) == 1.0

    # Compact support boundaries: psi_3(+-1) == 0.0
    assert cubic_delta_kernel(1.0) == 0.0
    assert cubic_delta_kernel(-1.0) == 0.0

    # Outside compact support
    assert cubic_delta_kernel(1.5) == 0.0
    assert cubic_delta_kernel(-2.0) == 0.0

    # Symmetry: psi_3(u) == psi_3(-u)
    for u in [0.1, 0.25, 0.5, 0.75, 0.99]:
        assert cubic_delta_kernel(u) == pytest.approx(cubic_delta_kernel(-u), abs=1e-12)
        assert 0.0 < cubic_delta_kernel(u) < 1.0


def test_cubic_delta_kernel_smoothing_continuity():
    """Verify wave height smoothing produces continuous, spike-free values across transitions."""
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    # Discrete jump: wave height spikes from 1.2m to 2.8m then drops
    raw_hs = [1.2, 1.3, 2.8, 1.5, 1.4, 1.3]

    smoothed_points = []
    # Evaluate at fine grid across time domain
    for t_step in [i * 0.25 for i in range(21)]:
        sm = smooth_wave_heights_cubic_delta(
            timestamps_hours=timestamps,
            wave_heights=raw_hs,
            target_time_hour=t_step,
            bandwidth_hours=2.0,
            delta=1.0,
        )
        smoothed_points.append(sm)

    # Check that adjacent points do not exhibit discontinuous jumps
    for i in range(len(smoothed_points) - 1):
        diff = abs(smoothed_points[i + 1] - smoothed_points[i])
        assert diff < 0.5, f"Gradient jump detected: {diff} at step {i}"


def test_external_feeds_config_loading_zero_hardcoding():
    """Verify declarative configuration file loads cleanly without hardcoded endpoints."""
    cfg = load_external_feeds_config()
    assert "open_meteo" in cfg
    meteo = cfg["open_meteo"]
    assert "api_endpoint" in meteo
    assert "bounding_boxes" in meteo
    assert "GOG_BONNY_BRASS_FAIRWAY" in meteo["bounding_boxes"]
    assert "GOG_ESCRAVOS_FORCADOS_APPROACH" in meteo["bounding_boxes"]
    assert "GOG_LAGOS_SAA_ANCHORAGE" in meteo["bounding_boxes"]
    assert meteo["bounding_boxes"]["GOG_LAGOS_SAA_ANCHORAGE"]["centroid_lat"] == 6.225
    assert meteo["bounding_boxes"]["GOG_LAGOS_SAA_ANCHORAGE"]["centroid_lon"] == 3.35
    assert "circuit_breaker" in meteo
    assert meteo["circuit_breaker"]["fallback_tag"] == "[ESTIMATED_HYDRODYNAMICS]"
    assert meteo["circuit_breaker"]["default_fallback_wave_height_m"] == 2.15


def test_external_feeds_config_missing_raises_filenotfound():
    """Verify attempting to load configuration from empty dir raises FileNotFoundError."""
    with tempfile.TemporaryDirectory() as empty_dir:
        with pytest.raises(FileNotFoundError):
            load_external_feeds_config(config_dir=empty_dir)


def test_corridor_coordinate_resolution_all_corridors():
    """Verify all 3 configured corridors resolve centroids correctly."""
    adapter = OpenMeteoHydroAdapter()
    lat1, lon1 = adapter._resolve_coordinates("GOG_BONNY_BRASS_FAIRWAY")
    assert (lat1, lon1) == (4.25, 7.0)

    lat2, lon2 = adapter._resolve_coordinates("GOG_ESCRAVOS_FORCADOS_APPROACH")
    assert (lat2, lon2) == (5.45, 5.15)

    lat3, lon3 = adapter._resolve_coordinates("GOG_LAGOS_SAA_ANCHORAGE")
    assert (lat3, lon3) == (6.225, 3.35)


def test_circuit_breaker_activates_on_forced_failure():
    """Verify circuit breaker returns fallback Hs and tags [ESTIMATED_HYDRODYNAMICS]."""
    adapter = OpenMeteoHydroAdapter()
    res = adapter.fetch_live_hydrodynamics(
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        force_circuit_breaker=True,
    )
    assert isinstance(res, OpenMeteoHydroResult)
    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == 2.15
    assert res.sample_size == 0


def test_circuit_breaker_pulls_90th_percentile_from_canonical_civilian_sensor_telemetry():
    """Verify circuit breaker queries civilian_sensor_telemetry table for 90th percentile historical wave height."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE civilian_sensor_telemetry (
            record_id TEXT PRIMARY KEY,
            significant_wave_height_m REAL
        )
    """)
    # Insert 10 observations with known 90th percentile: 1.0, 2.0, ..., 10.0 -> 90th percentile = 9.1
    for i in range(1, 11):
        cursor.execute(
            "INSERT INTO civilian_sensor_telemetry (record_id, significant_wave_height_m) VALUES (?, ?)",
            (f"R-{i}", float(i)),
        )
    conn.commit()

    adapter = OpenMeteoHydroAdapter(db_connection=conn)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)
    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == pytest.approx(9.1, abs=0.1)


def test_circuit_breaker_pulls_90th_percentile_from_legacy_civilian_telemetry():
    """Verify circuit breaker falls back to civilian_telemetry if civilian_sensor_telemetry does not exist."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE civilian_telemetry (
            telemetry_id TEXT PRIMARY KEY,
            significant_wave_height_m REAL
        )
    """)
    for i in range(1, 11):
        cursor.execute(
            "INSERT INTO civilian_telemetry (telemetry_id, significant_wave_height_m) VALUES (?, ?)",
            (f"T-{i}", float(i)),
        )
    conn.commit()

    adapter = OpenMeteoHydroAdapter(db_connection=conn)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)
    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == pytest.approx(9.1, abs=0.1)


def test_open_meteo_successful_payload_ingestion_and_smoothing():
    """Verify successful Open-Meteo REST response applies Cubic Delta Kernel smoothing."""
    mock_payload = {
        "latitude": 4.25,
        "longitude": 7.0,
        "hourly": {
            "time": ["2026-11-04T00:00", "2026-11-04T01:00", "2026-11-04T02:00", "2026-11-04T03:00"],
            "wave_height": [1.4, 1.5, 1.8, 1.7],
            "wave_period": [7.0, 7.2, 7.5, 7.4],
        },
    }
    raw_json = json.dumps(mock_payload).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = raw_json
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")

        assert isinstance(res, OpenMeteoHydroResult)
        assert res.is_estimated is False
        assert res.metadata_tag == "[LIVE_METOCEAN]"
        assert res.raw_wave_height_m == 1.7
        # Smoothed wave height should be weighted near recent readings
        assert 1.4 <= res.wave_height_m <= 1.8
        assert res.sample_size == 4
        assert res.smoothing_kernel == "cubic_delta_psi3"


def test_circuit_breaker_catches_timeout_and_network_error():
    """Verify urllib timeout triggers circuit breaker rather than propagating uncaught exception."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out after 5.0s")):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")

        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15
