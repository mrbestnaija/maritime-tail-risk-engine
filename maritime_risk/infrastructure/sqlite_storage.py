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

from datetime import datetime, timezone
import sqlite3
from typing import Optional, Sequence
from ..core.models import CivilianSensorTelemetry, GeoCoordinates, MaritimeIncident, SeverityInterval

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

CREATE TABLE IF NOT EXISTS civilian_sensor_telemetry (
    telemetry_id TEXT PRIMARY KEY,
    corridor_id TEXT NOT NULL,
    observation_timestamp TEXT NOT NULL,
    publication_timestamp TEXT NOT NULL,
    sar_provider TEXT NOT NULL,
    metocean_provider TEXT NOT NULL,
    ais_provider TEXT NOT NULL,
    significant_wave_height_m REAL NOT NULL,
    sar_dark_vessel_ratio REAL NOT NULL,
    anchorage_waiting_hours REAL NOT NULL,
    viirs_flaring_continuity_idx REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_telemetry_temporal_monotonicity CHECK (publication_timestamp >= observation_timestamp),
    CONSTRAINT chk_significant_wave_height CHECK (significant_wave_height_m >= 0.0 AND significant_wave_height_m <= 25.0),
    CONSTRAINT chk_sar_dark_vessel_ratio CHECK (sar_dark_vessel_ratio >= 0.0 AND sar_dark_vessel_ratio <= 1.0),
    CONSTRAINT chk_anchorage_waiting CHECK (anchorage_waiting_hours >= 0.0),
    CONSTRAINT chk_viirs_continuity CHECK (viirs_flaring_continuity_idx >= 0.0 AND viirs_flaring_continuity_idx <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_corridor_obs ON civilian_sensor_telemetry (corridor_id, observation_timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_pub ON civilian_sensor_telemetry (publication_timestamp);
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

    def load_incidents_point_in_time(
        self, as_of_time: int | float | str | datetime
    ) -> list[MaritimeIncident]:
        """Fetch incidents published strictly on or before as_of_time (bi-temporal filtering)."""
        if isinstance(as_of_time, datetime):
            cutoff = int(as_of_time.timestamp())
        elif isinstance(as_of_time, (int, float)):
            cutoff = int(as_of_time)
        elif isinstance(as_of_time, str):
            cutoff = int(datetime.fromisoformat(as_of_time).timestamp())
        else:
            raise TypeError(f"Unsupported as_of_time type: {type(as_of_time)}")

        cursor = self.conn.execute(
            """
            SELECT incident_id, event_time, pub_time, min_severity, max_severity,
                   latitude, longitude, feed_source, vessel_name, raw_payload, lineage_hash
            FROM incidents
            WHERE pub_time <= ?
            ORDER BY event_time ASC
            """,
            (cutoff,),
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

    def insert_telemetry(self, telemetry: CivilianSensorTelemetry) -> None:
        """Persist a single civilian sensor telemetry record."""
        self.insert_telemetry_batch([telemetry])

    def insert_telemetry_batch(
        self, telemetry_records: Sequence[CivilianSensorTelemetry]
    ) -> int:
        """Insert a batch of civilian telemetry records in a single transaction."""
        sql = """
        INSERT INTO civilian_sensor_telemetry (
            telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
            sar_provider, metocean_provider, ais_provider,
            significant_wave_height_m, sar_dark_vessel_ratio,
            anchorage_waiting_hours, viirs_flaring_continuity_idx
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            (
                rec.telemetry_id,
                rec.corridor_id,
                rec.observation_timestamp.isoformat(),
                rec.publication_timestamp.isoformat(),
                rec.sar_provider,
                rec.metocean_provider,
                rec.ais_provider,
                rec.significant_wave_height_m,
                rec.sar_dark_vessel_ratio,
                rec.anchorage_waiting_hours,
                rec.viirs_flaring_continuity_idx,
            )
            for rec in telemetry_records
        ]
        self.conn.executemany(sql, params)
        self.conn.commit()
        return len(telemetry_records)

    def _parse_telemetry_row(self, row: tuple) -> CivilianSensorTelemetry:
        return CivilianSensorTelemetry(
            telemetry_id=row[0],
            corridor_id=row[1],
            observation_timestamp=datetime.fromisoformat(row[2]),
            publication_timestamp=datetime.fromisoformat(row[3]),
            sar_provider=row[4],
            metocean_provider=row[5],
            ais_provider=row[6],
            significant_wave_height_m=row[7],
            sar_dark_vessel_ratio=row[8],
            anchorage_waiting_hours=row[9],
            viirs_flaring_continuity_idx=row[10],
        )

    def load_all_telemetry(
        self, corridor_id: Optional[str] = None
    ) -> list[CivilianSensorTelemetry]:
        """Fetch all civilian telemetry records, optionally filtered by corridor."""
        if corridor_id:
            cursor = self.conn.execute(
                """
                SELECT telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
                       sar_provider, metocean_provider, ais_provider,
                       significant_wave_height_m, sar_dark_vessel_ratio,
                       anchorage_waiting_hours, viirs_flaring_continuity_idx
                FROM civilian_sensor_telemetry
                WHERE corridor_id = ?
                ORDER BY observation_timestamp ASC
                """,
                (corridor_id,),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
                       sar_provider, metocean_provider, ais_provider,
                       significant_wave_height_m, sar_dark_vessel_ratio,
                       anchorage_waiting_hours, viirs_flaring_continuity_idx
                FROM civilian_sensor_telemetry
                ORDER BY observation_timestamp ASC
                """
            )
        return [self._parse_telemetry_row(r) for r in cursor.fetchall()]

    def load_telemetry_point_in_time(
        self, as_of_time: int | float | str | datetime, corridor_id: Optional[str] = None
    ) -> list[CivilianSensorTelemetry]:
        """Fetch telemetry published strictly on or before as_of_time (bi-temporal lag guard)."""
        if isinstance(as_of_time, datetime):
            cutoff_iso = as_of_time.isoformat()
        elif isinstance(as_of_time, (int, float)):
            cutoff_iso = datetime.fromtimestamp(as_of_time, tz=timezone.utc).isoformat()
        elif isinstance(as_of_time, str):
            cutoff_iso = as_of_time
        else:
            raise TypeError(f"Unsupported as_of_time type: {type(as_of_time)}")

        if corridor_id:
            cursor = self.conn.execute(
                """
                SELECT telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
                       sar_provider, metocean_provider, ais_provider,
                       significant_wave_height_m, sar_dark_vessel_ratio,
                       anchorage_waiting_hours, viirs_flaring_continuity_idx
                FROM civilian_sensor_telemetry
                WHERE corridor_id = ? AND publication_timestamp <= ?
                ORDER BY observation_timestamp ASC
                """,
                (corridor_id, cutoff_iso),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT telemetry_id, corridor_id, observation_timestamp, publication_timestamp,
                       sar_provider, metocean_provider, ais_provider,
                       significant_wave_height_m, sar_dark_vessel_ratio,
                       anchorage_waiting_hours, viirs_flaring_continuity_idx
                FROM civilian_sensor_telemetry
                WHERE publication_timestamp <= ?
                ORDER BY observation_timestamp ASC
                """,
                (cutoff_iso,),
            )
        return [self._parse_telemetry_row(r) for r in cursor.fetchall()]


class SQLiteTelemetryRepository(SQLiteIncidentRepository):
    """Dedicated repository alias for civilian sensor telemetry operations."""

    pass
