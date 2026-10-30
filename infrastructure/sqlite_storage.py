"""SQLite Storage Repository with C-Engine CHECK Constraints.

Mandatory Invariants:
The database schema directly codifies mathematical and temporal invariants into
C-level SQLite CHECK constraints:
1. CHECK (pub_time >= event_time): Temporal paradox prevention at the byte/storage layer.
2. CHECK (max_severity >= min_severity): Severity interval consistency.
3. CHECK (min_severity >= 0.0 AND max_severity <= 10.0): Severity bounding.
4. CHECK (latitude >= -90.0 AND latitude <= 90.0): WGS-84 coordinate validity.
5. CHECK (longitude >= -180.0 AND longitude <= 180.0): WGS-84 coordinate validity.
"""

from __future__ import annotations

import sqlite3
from typing import Sequence
from core.models import GeoCoordinates, MaritimeIncident, SeverityInterval

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    event_time INTEGER NOT NULL,
    pub_time INTEGER NOT NULL,
    min_severity REAL NOT NULL,
    max_severity REAL NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    feed_source TEXT NOT NULL,
    vessel_name TEXT,
    raw_payload TEXT,
    lineage_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_temporal_monotonicity CHECK (pub_time >= event_time),
    CONSTRAINT chk_severity_interval CHECK (max_severity >= min_severity),
    CONSTRAINT chk_severity_bounds CHECK (min_severity >= 0.0 AND max_severity <= 10.0),
    CONSTRAINT chk_latitude_bounds CHECK (latitude >= -90.0 AND latitude <= 90.0),
    CONSTRAINT chk_longitude_bounds CHECK (longitude >= -180.0 AND longitude <= 180.0)
);

CREATE INDEX IF NOT EXISTS idx_incidents_event_time ON incidents (event_time);
CREATE INDEX IF NOT EXISTS idx_incidents_geo ON incidents (latitude, longitude);
"""


class SQLiteIncidentRepository:
    """Repository managing persistence with C-level invariant enforcement."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.conn = connection
        self.init_schema()

    def init_schema(self) -> None:
        """Initialize database schema with strict CHECK constraints."""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def insert_incident(self, incident: MaritimeIncident) -> None:
        """Persist incident into SQLite table."""
        sql = """
        INSERT INTO incidents (
            incident_id, event_time, pub_time, min_severity, max_severity,
            latitude, longitude, feed_source, vessel_name, raw_payload, lineage_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(
            sql,
            (
                incident.incident_id,
                incident.event_time,
                incident.pub_time,
                incident.severity.min_severity,
                incident.severity.max_severity,
                incident.coordinates.latitude,
                incident.coordinates.longitude,
                incident.feed_source,
                incident.vessel_name,
                incident.raw_payload,
                incident.lineage_hash,
            ),
        )
        self.conn.commit()

    def insert_batch(self, incidents: Sequence[MaritimeIncident]) -> int:
        """Insert a batch of incidents in a single transaction."""
        sql = """
        INSERT INTO incidents (
            incident_id, event_time, pub_time, min_severity, max_severity,
            latitude, longitude, feed_source, vessel_name, raw_payload, lineage_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            (
                inc.incident_id,
                inc.event_time,
                inc.pub_time,
                inc.severity.min_severity,
                inc.severity.max_severity,
                inc.coordinates.latitude,
                inc.coordinates.longitude,
                inc.feed_source,
                inc.vessel_name,
                inc.raw_payload,
                inc.lineage_hash,
            )
            for inc in incidents
        ]
        self.conn.executemany(sql, params)
        self.conn.commit()
        return len(incidents)

    def load_all_incidents(self) -> list[MaritimeIncident]:
        """Fetch all incidents as domain models."""
        cursor = self.conn.execute(
            """
            SELECT incident_id, event_time, pub_time, min_severity, max_severity,
                   latitude, longitude, feed_source, vessel_name, raw_payload, lineage_hash
            FROM incidents
            ORDER BY event_time ASC
            """
        )
        results = []
        for row in cursor.fetchall():
            results.append(
                MaritimeIncident(
                    incident_id=row[0],
                    event_time=row[1],
                    pub_time=row[2],
                    severity=SeverityInterval(min_severity=row[3], max_severity=row[4]),
                    coordinates=GeoCoordinates(latitude=row[5], longitude=row[6]),
                    feed_source=row[7],
                    vessel_name=row[8],
                    raw_payload=row[9],
                    lineage_hash=row[10],
                )
            )
        return results
