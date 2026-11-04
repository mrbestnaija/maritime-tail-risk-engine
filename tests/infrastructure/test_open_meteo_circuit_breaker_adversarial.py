"""Adversarial Stress Test Suite for Open-Meteo Circuit Breaker & Fallback Architecture.

Challenger T3_2 (Circuit Breaker & Fallback Challenger):
Exhaustively challenges:
1. Network Fault Injection:
   - Socket timeout (> 5.0s and real SLA window < 1.0s via local mock server).
   - HTTP errors (400, 401, 403, 404, 429 rate limit, 500, 502, 503, 504).
   - DNS resolution failure (URLError errno 11001 getaddrinfo failed).
   - Malformed/truncated JSON responses, HTML error pages, empty bytes, corrupt UTF-8.
   - Missing/corrupted payload keys ('hourly', 'wave_height', empty arrays, all None).
   - In all failure modes: verify is_estimated == True, metadata_tag == "[ESTIMATED_HYDRODYNAMICS]", valid wave_height_m.
2. SQLite Fallback Resilience:
   - Fallback when db_connection is None -> returns config default 2.15m.
   - Fallback when canonical table civilian_sensor_telemetry exists -> exact empirical 90th percentile.
   - Fallback when only legacy table civilian_telemetry exists -> exact empirical 90th percentile.
   - Fallback when table is empty (0 rows) -> returns config default 2.15m.
   - Fallback when table has all NULL values -> returns config default 2.15m.
   - Fallback when real SQLite table is locked on disk -> returns config default 2.15m without uncaught exception.
   - Fallback when SQLite database is closed or corrupted -> returns config default 2.15m without uncaught exception.
3. Zero-Hardcoding Stress Check:
   - Missing configs/external_feeds.json raises FileNotFoundError.
   - Missing api_endpoint in config raises KeyError.
   - Resolution of corridor_id with valid vs invalid entries under declarative configuration.
"""

from __future__ import annotations

import http.server
import json
import socket
import sqlite3
import tempfile
import threading
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from maritime_risk.infrastructure.open_meteo_adapter import (
    OpenMeteoHydroAdapter,
    OpenMeteoHydroResult,
    load_external_feeds_config,
)


# =====================================================================
# 1. NETWORK FAULT INJECTION TESTS
# =====================================================================

def test_circuit_breaker_on_socket_timeout_mocked():
    """Verify socket timeout triggers circuit breaker and returns estimated fallback."""
    with patch("urllib.request.urlopen", side_effect=socket.timeout("Socket timed out after 5.0s")):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")

        assert isinstance(res, OpenMeteoHydroResult)
        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15
        assert res.sample_size == 0


def test_circuit_breaker_on_urlerror_timeout():
    """Verify urllib.error.URLError wrapping timeout triggers circuit breaker cleanly."""
    timeout_err = urllib.error.URLError(socket.timeout("The read operation timed out"))
    with patch("urllib.request.urlopen", side_effect=timeout_err):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")

        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15


def test_circuit_breaker_real_socket_timeout_sla_window():
    """Verify real HTTP socket server timeout triggers circuit breaker within SLA window."""
    class StallingHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            # Sleep longer than the configured timeout
            time.sleep(1.5)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"hourly": {"wave_height": [1.0]}}')

        def log_message(self, format, *args):
            pass  # Suppress console log spam

    server = http.server.HTTPServer(("127.0.0.1", 0), StallingHandler)
    server_port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        cfg = load_external_feeds_config()
        # Override endpoint to point to local stalling server and set strict 0.3s timeout
        cfg["open_meteo"]["api_endpoint"] = f"http://127.0.0.1:{server_port}/marine"
        cfg["open_meteo"]["circuit_breaker"]["timeout_seconds"] = 0.3

        adapter = OpenMeteoHydroAdapter(config=cfg)
        t_start = time.perf_counter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")
        elapsed = time.perf_counter() - t_start

        # Must cleanly fail and return fallback well under 1.5 seconds
        assert elapsed < 1.0, f"Circuit breaker did not trip in SLA window; elapsed: {elapsed:.3f}s"
        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429, 500, 502, 503, 504])
def test_circuit_breaker_on_http_errors(status_code: int):
    """Verify HTTP error codes (client, rate limit, server errors) trigger circuit breaker fallback."""
    http_err = urllib.error.HTTPError(
        url="https://marine-api.open-meteo.com/v1/marine",
        code=status_code,
        msg=f"HTTP Error {status_code}",
        hdrs=None,
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=http_err):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_LAGOS_SAA_ANCHORAGE")

        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15
        assert res.sample_size == 0


def test_circuit_breaker_on_dns_resolution_failure():
    """Verify DNS resolution failure (errno 11001 getaddrinfo failed) triggers circuit breaker."""
    dns_err = urllib.error.URLError(OSError(11001, "getaddrinfo failed"))
    with patch("urllib.request.urlopen", side_effect=dns_err):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_ESCRAVOS_FORCADOS_APPROACH")

        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15


@pytest.mark.parametrize("bad_payload", [
    b"{",  # Truncated JSON
    b"<html><body><h1>502 Bad Gateway</h1></body></html>",  # HTML instead of JSON
    b"",  # Empty payload
    b"\x80\xff\xfe\x00corrupt",  # Non UTF-8 binary
    b"null",  # JSON null
    b"[1, 2, 3]",  # JSON array instead of dict
])
def test_circuit_breaker_on_malformed_json(bad_payload: bytes):
    """Verify corrupted, truncated, or invalid payloads trigger circuit breaker fallback."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = bad_payload
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")

        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15


@pytest.mark.parametrize("corrupt_dict", [
    {},  # Empty object
    {"hourly": {}},  # Missing wave_height
    {"hourly": {"wave_height": []}},  # Empty wave_height list
    {"hourly": {"wave_height": [None, None]}},  # All None values
    {"hourly": {"wave_height": ["nan", "corrupted"]}},  # Unparseable strings
    {"latitude": 4.25, "longitude": 7.0},  # Missing hourly entirely
])
def test_circuit_breaker_on_missing_payload_keys(corrupt_dict: dict):
    """Verify missing required keys in JSON trigger circuit breaker fallback."""
    raw_json = json.dumps(corrupt_dict).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = raw_json
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        adapter = OpenMeteoHydroAdapter()
        res = adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")

        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15


# =====================================================================
# 2. SQLITE FALLBACK RESILIENCE TESTS
# =====================================================================

def test_sqlite_fallback_when_db_conn_is_none():
    """Verify fallback returns default config p90 (2.15m) when db_connection is None."""
    adapter = OpenMeteoHydroAdapter(db_connection=None)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)

    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == 2.15


def test_sqlite_fallback_canonical_table_exact_90th_percentile():
    """Verify canonical table civilian_sensor_telemetry computes exact empirical 90th percentile."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE civilian_sensor_telemetry (
            telemetry_id TEXT PRIMARY KEY,
            significant_wave_height_m REAL
        )
    """)
    # 100 observations: 1.0 to 10.0 in increments of 0.090909...
    values = np.linspace(1.0, 10.0, 100).tolist()
    for i, val in enumerate(values):
        cursor.execute(
            "INSERT INTO civilian_sensor_telemetry (telemetry_id, significant_wave_height_m) VALUES (?, ?)",
            (f"REC-{i}", val),
        )
    conn.commit()

    expected_p90 = float(np.percentile(values, 90.0))

    adapter = OpenMeteoHydroAdapter(db_connection=conn)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)

    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == pytest.approx(expected_p90, abs=1e-6)


def test_sqlite_fallback_legacy_table_exact_90th_percentile():
    """Verify legacy table civilian_telemetry computes exact empirical 90th percentile when canonical table is absent."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE civilian_telemetry (
            id TEXT PRIMARY KEY,
            significant_wave_height_m REAL
        )
    """)
    values = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    for i, val in enumerate(values):
        cursor.execute(
            "INSERT INTO civilian_telemetry (id, significant_wave_height_m) VALUES (?, ?)",
            (f"LEGACY-{i}", val),
        )
    conn.commit()

    expected_p90 = float(np.percentile(values, 90.0))

    adapter = OpenMeteoHydroAdapter(db_connection=conn)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)

    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == pytest.approx(expected_p90, abs=1e-6)


def test_sqlite_fallback_empty_table_zero_rows():
    """Verify empty table civilian_sensor_telemetry safely falls back to config default 2.15m."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE civilian_sensor_telemetry (
            telemetry_id TEXT PRIMARY KEY,
            significant_wave_height_m REAL
        )
    """)
    conn.commit()

    adapter = OpenMeteoHydroAdapter(db_connection=conn)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)

    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == 2.15


def test_sqlite_fallback_all_null_values():
    """Verify table with all NULL wave heights safely falls back to config default 2.15m."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE civilian_sensor_telemetry (
            telemetry_id TEXT PRIMARY KEY,
            significant_wave_height_m REAL
        )
    """)
    for i in range(5):
        cursor.execute(
            "INSERT INTO civilian_sensor_telemetry (telemetry_id, significant_wave_height_m) VALUES (?, NULL)",
            (f"NULL-{i}",),
        )
    conn.commit()

    adapter = OpenMeteoHydroAdapter(db_connection=conn)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)

    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == 2.15


def test_sqlite_fallback_table_locked_on_disk():
    """Verify SQLite database locked by concurrent transaction safely falls back without raising OperationalError."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        # Create table with data
        conn_init = sqlite3.connect(db_path)
        conn_init.execute("CREATE TABLE civilian_sensor_telemetry (significant_wave_height_m REAL)")
        conn_init.execute("INSERT INTO civilian_sensor_telemetry VALUES (3.8)")
        conn_init.commit()
        conn_init.close()

        # Connection 1 locks the file exclusively
        locking_conn = sqlite3.connect(db_path, timeout=0.1)
        locking_conn.execute("BEGIN EXCLUSIVE")

        # Connection 2 (in adapter) attempts to query with tiny timeout -> triggers "database is locked"
        reader_conn = sqlite3.connect(db_path, timeout=0.01)

        adapter = OpenMeteoHydroAdapter(db_connection=reader_conn)
        res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)

        assert res.is_estimated is True
        assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
        assert res.wave_height_m == 2.15

        locking_conn.rollback()
        locking_conn.close()
        reader_conn.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_sqlite_fallback_closed_connection():
    """Verify closed SQLite connection safely falls back without raising ProgrammingError."""
    conn = sqlite3.connect(":memory:")
    conn.close()  # Deliberately close connection

    adapter = OpenMeteoHydroAdapter(db_connection=conn)
    res = adapter.fetch_live_hydrodynamics(force_circuit_breaker=True)

    assert res.is_estimated is True
    assert res.metadata_tag == "[ESTIMATED_HYDRODYNAMICS]"
    assert res.wave_height_m == 2.15


# =====================================================================
# 3. ZERO-HARDCODING STRESS CHECKS
# =====================================================================

def test_missing_config_file_raises_filenotfound():
    """Verify attempting to load configuration from nonexistent directory raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_external_feeds_config(config_dir="nonexistent_config_dir_path_98765")
    assert "not found in specified directory" in str(exc_info.value)


def test_missing_api_endpoint_in_config_raises_keyerror():
    """Verify missing api_endpoint in configuration raises KeyError instead of silent hardcoded URL fallback."""
    cfg = load_external_feeds_config()
    del cfg["open_meteo"]["api_endpoint"]

    adapter = OpenMeteoHydroAdapter(config=cfg)
    with pytest.raises(KeyError) as exc_info:
        adapter.fetch_live_hydrodynamics(corridor_id="GOG_BONNY_BRASS_FAIRWAY")
    assert "api_endpoint" in str(exc_info.value)


def test_invalid_corridor_id_without_default_raises_keyerror():
    """Verify requesting an invalid corridor ID when default_corridor_id is unset raises KeyError."""
    cfg = load_external_feeds_config()
    cfg["open_meteo"]["default_corridor_id"] = None

    adapter = OpenMeteoHydroAdapter(config=cfg)
    with pytest.raises(KeyError) as exc_info:
        adapter.fetch_live_hydrodynamics(corridor_id="INVALID_UNKNOWN_CORRIDOR")
    assert "INVALID_UNKNOWN_CORRIDOR" in str(exc_info.value)
