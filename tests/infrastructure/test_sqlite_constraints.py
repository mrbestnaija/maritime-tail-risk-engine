"""Test Suite for SQLite C-Engine CHECK Constraints.

Verifies:
1. CHECK (pub_time >= event_time) is physically enforced at the C-storage layer.
2. CHECK (max_severity >= min_severity) rejects inverted severity intervals.
3. CHECK bounds on coordinates and severities prevent corrupted data entry.
"""

from __future__ import annotations

import sqlite3
import pytest
from infrastructure.sqlite_storage import SCHEMA_SQL


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


def test_sqlite_rejects_temporal_paradox_at_c_storage_layer(db_conn: sqlite3.Connection):
    """Direct SQL insert violating pub_time >= event_time must trigger sqlite3.IntegrityError."""
    # Attempt to insert an event that was published BEFORE it happened
    # event_time = 1700005000, pub_time = 1700001000 (earlier!)
    sql = """
    INSERT INTO incidents (
        incident_id, event_time, pub_time, min_severity, max_severity,
        latitude, longitude, feed_source, lineage_hash
    ) VALUES ('ERR-001', 1700005000, 1700001000, 2.0, 5.0, 4.2, 7.1, 'OSINT', 'hash_test');
    """
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        db_conn.execute(sql)
    assert "chk_temporal_monotonicity" in str(exc_info.value).lower() or "check" in str(exc_info.value).lower()


def test_sqlite_rejects_inverted_severity_interval(db_conn: sqlite3.Connection):
    """Direct SQL insert with max_severity < min_severity must fail CHECK constraint."""
    # min_severity = 7.0, max_severity = 3.0 (inverted!)
    sql = """
    INSERT INTO incidents (
        incident_id, event_time, pub_time, min_severity, max_severity,
        latitude, longitude, feed_source, lineage_hash
    ) VALUES ('ERR-002', 1700001000, 1700002000, 7.0, 3.0, 4.2, 7.1, 'OSINT', 'hash_test');
    """
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(sql)


def test_sqlite_accepts_valid_incident(db_conn: sqlite3.Connection):
    """Valid record meeting all constraints inserts cleanly."""
    sql = """
    INSERT INTO incidents (
        incident_id, event_time, pub_time, min_severity, max_severity,
        latitude, longitude, feed_source, lineage_hash
    ) VALUES ('OK-001', 1700001000, 1700002000, 3.0, 6.0, 4.25, 7.12, 'MDAT', 'hash_valid');
    """
    db_conn.execute(sql)
    db_conn.commit()

    cursor = db_conn.execute("SELECT incident_id, min_severity, max_severity FROM incidents WHERE incident_id='OK-001'")
    row = cursor.fetchone()
    assert row == ("OK-001", 3.0, 6.0)


def test_sqlite_rejects_telemetry_temporal_paradox(db_conn: sqlite3.Connection):
    """Direct SQL insert violating publication_timestamp >= observation_timestamp fails CHECK constraint."""
    sql = """
    INSERT INTO civilian_sensor_telemetry (
        telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
        sar_provider, metocean_provider, ais_provider,
        significant_wave_height_m, sar_dark_vessel_ratio,
        anchorage_waiting_hours, viirs_flaring_continuity_idx
    ) VALUES (
        'TEL-ERR-001', 'GOG_BONNY_BRASS_FAIRWAY',
        '2023-01-15T12:00:00Z', '2023-01-15T10:00:00Z',
        'GFW_SENTINEL1_SAR', 'COPERNICUS_ERA5_METOCEAN', 'IMF_PORTWATCH_AIS',
        1.5, 0.2, 24.0, 0.95
    );
    """
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(sql)


def test_sqlite_rejects_wave_height_out_of_bounds(db_conn: sqlite3.Connection):
    """Significant wave height outside [0.0, 25.0] meters fails CHECK constraint."""
    sql = """
    INSERT INTO civilian_sensor_telemetry (
        telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
        sar_provider, metocean_provider, ais_provider,
        significant_wave_height_m, sar_dark_vessel_ratio,
        anchorage_waiting_hours, viirs_flaring_continuity_idx
    ) VALUES (
        'TEL-ERR-002', 'GOG_BONNY_BRASS_FAIRWAY',
        '2023-01-15T10:00:00Z', '2023-01-15T12:00:00Z',
        'GFW_SENTINEL1_SAR', 'COPERNICUS_ERA5_METOCEAN', 'IMF_PORTWATCH_AIS',
        28.5, 0.2, 24.0, 0.95
    );
    """
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(sql)


def test_sqlite_rejects_sar_ratio_out_of_bounds(db_conn: sqlite3.Connection):
    """SAR dark vessel ratio outside [0.0, 1.0] fails CHECK constraint."""
    sql = """
    INSERT INTO civilian_sensor_telemetry (
        telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
        sar_provider, metocean_provider, ais_provider,
        significant_wave_height_m, sar_dark_vessel_ratio,
        anchorage_waiting_hours, viirs_flaring_continuity_idx
    ) VALUES (
        'TEL-ERR-003', 'GOG_BONNY_BRASS_FAIRWAY',
        '2023-01-15T10:00:00Z', '2023-01-15T12:00:00Z',
        'GFW_SENTINEL1_SAR', 'COPERNICUS_ERA5_METOCEAN', 'IMF_PORTWATCH_AIS',
        1.5, 1.35, 24.0, 0.95
    );
    """
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(sql)


def test_sqlite_accepts_valid_telemetry(db_conn: sqlite3.Connection):
    """Valid telemetry meeting all CHECK constraints inserts cleanly."""
    sql = """
    INSERT INTO civilian_sensor_telemetry (
        telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
        sar_provider, metocean_provider, ais_provider,
        significant_wave_height_m, sar_dark_vessel_ratio,
        anchorage_waiting_hours, viirs_flaring_continuity_idx
    ) VALUES (
        'TEL-OK-001', 'GOG_BONNY_BRASS_FAIRWAY',
        '2023-01-15T10:00:00Z', '2023-01-15T12:00:00Z',
        'GFW_SENTINEL1_SAR', 'COPERNICUS_ERA5_METOCEAN', 'IMF_PORTWATCH_AIS',
        1.45, 0.22, 36.5, 0.94
    );
    """
    db_conn.execute(sql)
    db_conn.commit()

    cursor = db_conn.execute(
        "SELECT telemetry_id, significant_wave_height_m, sar_dark_vessel_ratio "
        "FROM civilian_sensor_telemetry WHERE telemetry_id='TEL-OK-001'"
    )
    row = cursor.fetchone()
    assert row == ("TEL-OK-001", 1.45, 0.22)
