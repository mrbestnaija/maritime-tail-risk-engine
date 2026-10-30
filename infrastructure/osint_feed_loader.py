"""OSINT Maritime Security Feed Loader & Dataset Digest Calculator.

Ingests OSINT reporting (CSV and JSON formats from MDAT-GOG, IMB PRC, UKMTO, Dryad)
and computes cryptographic SHA-256 lineage digests for institutional auditability.
Performs default centroid imputation for records with missing coordinates.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Sequence
from core.models import GeoCoordinates, MaritimeIncident, SeverityInterval

DEFAULT_FAIRWAY_CENTROID_LAT = 4.2250
DEFAULT_FAIRWAY_CENTROID_LON = 7.0850


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute standard SHA-256 hex digest of file."""
    p = Path(file_path)
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class OSINTFeedLoader:
    """Loader for OSINT incident feeds with cryptographic lineage tracking."""

    @staticmethod
    def load_incidents_from_csv(file_path: Path | str) -> tuple[list[MaritimeIncident], str]:
        """Load incidents from CSV dataset and return (incidents, dataset_sha256).
        
        Handles missing coordinates via fairway centroid imputation.
        """
        p = Path(file_path)
        content_bytes = p.read_bytes()
        dataset_sha256 = hashlib.sha256(content_bytes).hexdigest()

        incidents = []
        text_content = content_bytes.decode("utf-8")
        reader = csv.DictReader(text_content.splitlines())

        for row in reader:
            raw_serialized = json.dumps(row, sort_keys=True)
            record_hash = hashlib.sha256(raw_serialized.encode("utf-8")).hexdigest()

            # Handle missing coordinates via centroid imputation
            lat_str = row.get("latitude", "").strip()
            lon_str = row.get("longitude", "").strip()

            lat = float(lat_str) if lat_str else DEFAULT_FAIRWAY_CENTROID_LAT
            lon = float(lon_str) if lon_str else DEFAULT_FAIRWAY_CENTROID_LON

            incident = MaritimeIncident(
                incident_id=row["incident_id"],
                event_time=int(row["event_time"]),
                pub_time=int(row["pub_time"]),
                coordinates=GeoCoordinates(latitude=lat, longitude=lon),
                severity=SeverityInterval(
                    min_severity=float(row["min_severity"]),
                    max_severity=float(row["max_severity"]),
                ),
                feed_source=row["feed_source"],
                vessel_name=row.get("vessel_name"),
                raw_payload=raw_serialized,
                lineage_hash=record_hash,
            )
            incidents.append(incident)

        return incidents, dataset_sha256

    @staticmethod
    def load_incidents_from_json(file_path: Path | str) -> tuple[list[MaritimeIncident], str]:
        """Load incidents from JSON file and return (incidents, dataset_sha256)."""
        p = Path(file_path)
        content_bytes = p.read_bytes()
        dataset_sha256 = hashlib.sha256(content_bytes).hexdigest()

        data = json.loads(content_bytes.decode("utf-8"))
        incidents = []

        for item in data:
            raw_serialized = json.dumps(item, sort_keys=True)
            record_hash = hashlib.sha256(raw_serialized.encode("utf-8")).hexdigest()

            lat = float(item["latitude"]) if item.get("latitude") is not None else DEFAULT_FAIRWAY_CENTROID_LAT
            lon = float(item["longitude"]) if item.get("longitude") is not None else DEFAULT_FAIRWAY_CENTROID_LON

            incident = MaritimeIncident(
                incident_id=item["incident_id"],
                event_time=item["event_time"],
                pub_time=item["pub_time"],
                coordinates=GeoCoordinates(latitude=lat, longitude=lon),
                severity=SeverityInterval(
                    min_severity=float(item["min_severity"]),
                    max_severity=float(item["max_severity"]),
                ),
                feed_source=item["feed_source"],
                vessel_name=item.get("vessel_name"),
                raw_payload=raw_serialized,
                lineage_hash=record_hash,
            )
            incidents.append(incident)

        return incidents, dataset_sha256
