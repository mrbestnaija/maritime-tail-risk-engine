"""Ingestion Hygiene & Cross-Feed Deduplication Service.

Mandatory Invariants:
1. Union Envelope: Multi-feed deduplication MUST compute the union envelope of
   severity intervals:
       min_severity = min(reported_min_severities)
       max_severity = max(reported_max_severities)
   Dropping the worst-case severity causes underwriters to underprice tail risk.
2. Centroid Imputation: Geographically clusters reports and calculates the
   exact centroid (mean latitude, mean longitude) for merged incidents.
3. Provenance & Lineage: Combines reporting feed sources and hashes for audit trails.
"""

from __future__ import annotations

import hashlib
import json
from typing import Sequence
from ..core.models import GeoCoordinates, MaritimeIncident, SeverityInterval


class IngestionHygieneService:
    """Hygiene service for maritime OSINT data streams."""

    def __init__(
        self,
        spatial_tolerance_nm: float = 15.0,
        temporal_window_seconds: int = 43200,  # 12 hours
    ) -> None:
        self.spatial_tolerance_nm = spatial_tolerance_nm
        self.temporal_window_seconds = temporal_window_seconds

    def _are_reports_same_event(self, a: MaritimeIncident, b: MaritimeIncident) -> bool:
        """Evaluate if two reports describe the same physical event."""
        # 1. Exact vessel match if both present and non-empty
        if a.vessel_name and b.vessel_name:
            if a.vessel_name.strip().lower() == b.vessel_name.strip().lower():
                # Temporal proximity check within 24 hours
                if abs(a.event_time - b.event_time) <= 86400:
                    return True

        # 2. Spatio-temporal coincidence
        time_diff = abs(a.event_time - b.event_time)
        if time_diff <= self.temporal_window_seconds:
            dist_nm = a.coordinates.distance_to_nautical_miles(b.coordinates)
            if dist_nm <= self.spatial_tolerance_nm:
                return True

        return False

    def deduplicate_cross_feed(self, raw_incidents: Sequence[MaritimeIncident]) -> list[MaritimeIncident]:
        """Deduplicate reports across feeds using Union Envelope and Centroid Imputation."""
        if not raw_incidents:
            return []

        # Graph / cluster connected components
        clusters: list[list[MaritimeIncident]] = []
        for incident in raw_incidents:
            matched_cluster = None
            for cluster in clusters:
                if any(self._are_reports_same_event(incident, existing) for existing in cluster):
                    matched_cluster = cluster
                    break

            if matched_cluster is not None:
                matched_cluster.append(incident)
            else:
                clusters.append([incident])

        deduplicated: list[MaritimeIncident] = []

        for cluster in clusters:
            if len(cluster) == 1:
                deduplicated.append(cluster[0])
                continue

            # --- MANDATORY AUDIT INVARIANT 1: UNION ENVELOPE ---
            # Underwriters require the full uncertainty envelope.
            # We take min of mins and max of maxes across all cluster reports.
            union_min_sev = min(r.severity.min_severity for r in cluster)
            union_max_sev = max(r.severity.max_severity for r in cluster)
            envelope = SeverityInterval(
                min_severity=union_min_sev,
                max_severity=union_max_sev,
            )

            # --- MANDATORY AUDIT INVARIANT 2: CENTROID IMPUTATION ---
            mean_lat = sum(r.coordinates.latitude for r in cluster) / len(cluster)
            mean_lon = sum(r.coordinates.longitude for r in cluster) / len(cluster)
            centroid = GeoCoordinates(latitude=mean_lat, longitude=mean_lon)

            # Earliest event time and validated publication time
            min_event_time = min(r.event_time for r in cluster)
            min_pub_time = min(r.pub_time for r in cluster)
            # Ensure temporal monotonicity constraint holds
            effective_pub_time = max(min_pub_time, min_event_time)

            # Provenance aggregation
            sources = sorted(list(set(r.feed_source for r in cluster)))
            merged_source = " + ".join(sources)
            vessel_names = [r.vessel_name for r in cluster if r.vessel_name]
            vessel = vessel_names[0] if vessel_names else None

            # Combined cryptographic lineage hash
            combined_hash_input = "".join(sorted(r.lineage_hash for r in cluster))
            merged_lineage = hashlib.sha256(combined_hash_input.encode("utf-8")).hexdigest()

            primary_id = cluster[0].incident_id
            merged_incident = MaritimeIncident(
                incident_id=f"DEDUP-{primary_id}",
                event_time=min_event_time,
                pub_time=effective_pub_time,
                coordinates=centroid,
                severity=envelope,
                feed_source=merged_source,
                vessel_name=vessel,
                raw_payload=json.dumps({"cluster_size": len(cluster), "source_ids": [r.incident_id for r in cluster]}),
                lineage_hash=merged_lineage,
            )
            deduplicated.append(merged_incident)

        return deduplicated
