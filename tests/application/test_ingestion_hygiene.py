"""Test Suite for Ingestion Hygiene & Deduplication Union Envelope.

MANDATORY AUDIT PROTOCOL:
Verify that cross-feed deduplication computes the UNION ENVELOPE
(min of mins, max of maxes) across severity intervals rather than keeping only
the first record. If worst-case severity is dropped, the underwriter underprices risk.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from core.models import GeoCoordinates, MaritimeIncident, SeverityInterval
from application.ingestion_hygiene import IngestionHygieneService
from infrastructure.osint_feed_loader import OSINTFeedLoader


def test_deduplication_takes_union_envelope_and_centroid():
    """Verify deduplication takes min of mins, max of maxes, and average coordinates."""
    # Two feeds reporting the same vessel attack in Bonny Fairway
    # Feed 1 (MDAT-GOG): reports severity [3.0, 5.0] at (4.20, 7.00)
    rep1 = MaritimeIncident(
        incident_id="REP-001",
        event_time=1700000000,
        pub_time=1700003600,
        coordinates=GeoCoordinates(latitude=4.20, longitude=7.00),
        severity=SeverityInterval(min_severity=3.0, max_severity=5.0),
        feed_source="MDAT-GOG",
        vessel_name="MT BONNY STAR",
        lineage_hash="hash_rep1",
    )

    # Feed 2 (IMB): reports severity [4.5, 8.0] at (4.22, 7.02) - confirmed weapons
    rep2 = MaritimeIncident(
        incident_id="REP-002",
        event_time=1700000300,  # 5 minutes later
        pub_time=1700007200,
        coordinates=GeoCoordinates(latitude=4.22, longitude=7.02),
        severity=SeverityInterval(min_severity=4.5, max_severity=8.0),
        feed_source="IMB",
        vessel_name="MT BONNY STAR",
        lineage_hash="hash_rep2",
    )

    hygiene = IngestionHygieneService(spatial_tolerance_nm=15.0, temporal_window_seconds=43200)
    deduped = hygiene.deduplicate_cross_feed([rep1, rep2])

    assert len(deduped) == 1, "Expected the two reports to be merged into 1 physical incident"
    merged = deduped[0]

    # --- MANDATORY AUDIT PROTOCOL 2: UNION ENVELOPE VERIFICATION ---
    # Min of mins: min(3.0, 4.5) = 3.0
    # Max of maxes: max(5.0, 8.0) = 8.0
    assert merged.severity.min_severity == pytest.approx(3.0)
    assert merged.severity.max_severity == pytest.approx(8.0)

    # Proves we did NOT just keep the first record's max_severity (which was 5.0)
    assert merged.severity.max_severity != rep1.severity.max_severity, (
        "Deduplication must NOT drop the worst-case severity from secondary feeds"
    )

    # --- MANDATORY AUDIT PROTOCOL 2: CENTROID IMPUTATION VERIFICATION ---
    # Centroid: (4.20 + 4.22) / 2 = 4.21, (7.00 + 7.02) / 2 = 7.01
    assert merged.coordinates.latitude == pytest.approx(4.21, abs=1e-4)
    assert merged.coordinates.longitude == pytest.approx(7.01, abs=1e-4)

    # Provenance preserved
    assert "MDAT-GOG" in merged.feed_source
    assert "IMB" in merged.feed_source


def test_independent_incidents_not_merged():
    """Verify distinct incidents (separated in time and space) remain unmerged."""
    rep1 = MaritimeIncident(
        incident_id="INC-A",
        event_time=1700000000,
        pub_time=1700001000,
        coordinates=GeoCoordinates(latitude=4.10, longitude=6.80),
        severity=SeverityInterval(min_severity=2.0, max_severity=3.0),
        feed_source="MDAT-GOG",
        vessel_name="VESSEL A",
        lineage_hash="hash_a",
    )
    rep2 = MaritimeIncident(
        incident_id="INC-B",
        event_time=1700200000,  # > 50 hours later
        pub_time=1700201000,
        coordinates=GeoCoordinates(latitude=4.40, longitude=7.30),  # > 30 nm away
        severity=SeverityInterval(min_severity=6.0, max_severity=7.0),
        feed_source="IMB",
        vessel_name="VESSEL B",
        lineage_hash="hash_b",
    )

    hygiene = IngestionHygieneService()
    deduped = hygiene.deduplicate_cross_feed([rep1, rep2])
    assert len(deduped) == 2


def test_40_row_sample_dataset_deduplication():
    """Verify 40-row realistic sample dataset loads and deduplicates with centroid imputation."""
    test_dir = Path(__file__).resolve().parent
    engine_root = test_dir.parent.parent
    csv_path = engine_root / "data" / "sample_gog_osint_vintage.csv"

    assert csv_path.exists(), f"Sample dataset not found at {csv_path}"

    raw_incidents, sha256 = OSINTFeedLoader.load_incidents_from_csv(csv_path)
    assert len(raw_incidents) == 40, f"Expected exactly 40 raw records, found {len(raw_incidents)}"

    hygiene = IngestionHygieneService()
    deduped = hygiene.deduplicate_cross_feed(raw_incidents)

    # Due to duplicates across MDAT-GOG, IMB, DRYAD, and revisions:
    assert len(deduped) < 40
    assert len(deduped) == 31

    # Verify that all deduplicated incidents have valid coordinates (centroid imputed)
    for inc in deduped:
        assert -90.0 <= inc.coordinates.latitude <= 90.0
        assert -180.0 <= inc.coordinates.longitude <= 180.0
        assert inc.severity.max_severity >= inc.severity.min_severity
        assert inc.pub_time >= inc.event_time
