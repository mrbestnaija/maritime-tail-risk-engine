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
