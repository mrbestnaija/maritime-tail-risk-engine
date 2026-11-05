"""Test Suite for OSINT Incident Feed REST Adapter & SQLite Integrity.

Verifies:
1. Publication lag Delta_t = t_pub - t_event calculation.
2. SQLite C-engine CHECK constraint enforcement: rejecting pub_time < event_time at the storage layer.
3. Cubic Exponential parameter variance envelope bounds on GPD tail risk.
4. Automatic circuit breaker tripping on network failure/timeout returning ([], "[ESTIMATED_INCIDENTS]").
5. End-to-end IncidentFeedAdapter integration on real in-memory SQLite database.

Author: Maritime domain researcher with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
"""

from __future__ import annotations

import io
import json
import sqlite3
import urllib.error
from unittest.mock import patch
import pytest

from maritime_risk.core.models import GeoCoordinates, MaritimeIncident, SeverityInterval
from maritime_risk.core.specs import GPDFitterSpec
from maritime_risk.infrastructure.incident_feed_adapter import (
    INCIDENTS_SCHEMA_SQL,
    IncidentFeedAdapter,
    calculate_publication_lags,
    cubic_exponential_variance_bound,
    fetch_incidents,
    persist_incidents_to_sqlite,
    update_empirical_gpd,
)


@pytest.fixture
def memory_db() -> sqlite3.Connection:
    """Isolated, real in-memory SQLite database."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_calculate_publication_lags_seconds_and_hours():
    """Delta_t must accurately evaluate t_pub - t_obs in both seconds and hours."""
    incidents = [
        MaritimeIncident(
            incident_id="INC-01",
            event_time=1700000000,
            pub_time=1700003600,  # 3600 seconds = 1 hour lag
            coordinates=GeoCoordinates(latitude=4.2, longitude=7.1),
            severity=SeverityInterval(min_severity=2.0, max_severity=4.0),
            feed_source="MDAT-GOG",
            lineage_hash="hash01",
        ),
        MaritimeIncident(
            incident_id="INC-02",
            event_time=1700000000,
            pub_time=1700007200,  # 7200 seconds = 2 hours lag
            coordinates=GeoCoordinates(latitude=4.3, longitude=7.2),
            severity=SeverityInterval(min_severity=1.5, max_severity=3.5),
            feed_source="IMB-PRC",
            lineage_hash="hash02",
        ),
    ]

    lags_sec = calculate_publication_lags(incidents, in_hours=False)
    assert lags_sec == [3600.0, 7200.0]

    lags_hr = calculate_publication_lags(incidents, in_hours=True)
    assert lags_hr == [1.0, 2.0]


def test_calculate_publication_lags_from_raw_dicts():
    """Delta_t calculation must handle raw dictionary payloads seamlessly."""
    raw_dicts = [
        {"event_time": 1700000000, "pub_time": 1700018000},  # 5 hours
    ]
    lags = calculate_publication_lags(raw_dicts, in_hours=True)
    assert lags == [5.0]


def test_sqlite_check_constraint_rejects_temporal_paradox(memory_db: sqlite3.Connection):
    """Direct persist_incidents_to_sqlite must fail with sqlite3.IntegrityError if pub_time < event_time."""
    invalid_records = [
        {
            "incident_id": "PARADOX-01",
            "event_time": 1700010000,
            "pub_time": 1700005000,  # published before event!
            "min_severity": 2.0,
            "max_severity": 5.0,
            "latitude": 4.25,
            "longitude": 7.10,
            "feed_source": "OSINT_TEST",
            "lineage_hash": "hash_bad",
        }
    ]

    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        persist_incidents_to_sqlite(invalid_records, memory_db)

    err_msg = str(exc_info.value).lower()
    assert "chk_temporal_monotonicity" in err_msg or "check constraint" in err_msg


def test_sqlite_persists_valid_incidents(memory_db: sqlite3.Connection):
    """Valid incidents must persist to SQLite and be queryable."""
    incidents = [
        MaritimeIncident(
            incident_id="INC-VALID-01",
            event_time=1700000000,
            pub_time=1700003600,
            coordinates=GeoCoordinates(latitude=4.225, longitude=7.085),
            severity=SeverityInterval(min_severity=3.0, max_severity=6.0),
            feed_source="MDAT-GOG",
            vessel_name="MT BONNY_STAR",
            lineage_hash="lineage_valid_01",
        )
    ]

    count = persist_incidents_to_sqlite(incidents, memory_db)
    assert count == 1

    cur = memory_db.execute("SELECT incident_id, event_time, pub_time, vessel_name FROM incidents")
    row = cur.fetchone()
    assert row == ("INC-VALID-01", 1700000000, 1700003600, "MT BONNY_STAR")


def test_cubic_exponential_variance_bound_properties():
    """Verify mathematical properties of Cubic Exponential variance envelope."""
    # Zero sample
    assert cubic_exponential_variance_bound(1.5, sample_size=0) == 0.0

    # Small sample dampening
    v_small = cubic_exponential_variance_bound(5.0, sample_size=2, decay_rate=1.0, variance_cap=2.5)
    # Large sample convergence
    v_large = cubic_exponential_variance_bound(5.0, sample_size=100, decay_rate=1.0, variance_cap=2.5)

    assert 0.0 < v_small < v_large
    assert v_large <= 2.5  # Strictly capped at variance_cap


def test_update_empirical_gpd_bounds_and_monotonicity():
    """update_empirical_gpd must constrain parameters and maintain CVaR >= VaR monotonicity."""
    severities = [1.2, 1.5, 2.0, 3.5, 4.0, 6.2, 7.8, 8.5]
    res = update_empirical_gpd(severities)

    assert -0.5 <= res.shape_xi <= 0.95
    assert res.scale_sigma >= 0.01
    assert res.cvar_99 >= res.var_99 >= res.var_95


def test_update_empirical_gpd_with_empty_dataset():
    """Empty incident dataset must not raise but return bounded prior baseline."""
    res = update_empirical_gpd([])
    assert res.exceedance_count == 0
    assert res.var_99 >= 0.0


def test_fetch_incidents_force_circuit_breaker():
    """force_circuit_breaker=True must instantly return ([], '[ESTIMATED_INCIDENTS]')."""
    incidents, tag = fetch_incidents(force_circuit_breaker=True)
    assert incidents == []
    assert tag == "[ESTIMATED_INCIDENTS]"


def test_fetch_incidents_http_timeout_triggers_circuit_breaker():
    """Urllib timeout/URLError must trigger circuit breaker without crashing."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")):
        incidents, tag = fetch_incidents(feed_url="https://api.example.com/incidents")
        assert incidents == []
        assert tag == "[ESTIMATED_INCIDENTS]"


def test_fetch_incidents_success_and_filtering():
    """Valid payload must parse incidents and filter temporal paradoxes."""
    sample_payload = {
        "incidents": [
            {
                "id": "LIVE-01",
                "event_time": 1700000000,
                "pub_time": 1700003600,
                "lat": 4.25,
                "lon": 7.15,
                "severity": 3.5,
                "feed_source": "LIVE_FEED",
            },
            {
                "id": "PARADOX-DROP",
                "event_time": 1700010000,
                "pub_time": 1700005000,  # Violates pub_time >= event_time
                "lat": 4.25,
                "lon": 7.15,
                "severity": 5.0,
            },
        ]
    }

    mock_response = io.BytesIO(json.dumps(sample_payload).encode("utf-8"))
    mock_response.status = 200

    with patch("urllib.request.urlopen", return_value=mock_response):
        incidents, tag = fetch_incidents(feed_url="https://api.example.com/incidents")
        assert tag == "[LIVE_INCIDENTS]"
        assert len(incidents) == 1
        assert incidents[0].incident_id == "LIVE-01"


def test_incident_feed_adapter_full_integration(memory_db: sqlite3.Connection):
    """Verify IncidentFeedAdapter class integrating ingestion, lag, GPD updating, and SQLite."""
    adapter = IncidentFeedAdapter(db_connection=memory_db)

    # 1. Circuit breaker on unconfigured endpoint
    incidents, tag = adapter.fetch_incidents(force_circuit_breaker=True)
    assert incidents == []
    assert tag == "[ESTIMATED_INCIDENTS]"

    # 2. Ingest structured incidents
    test_incidents = [
        MaritimeIncident(
            incident_id="ADAPT-01",
            event_time=1700000000,
            pub_time=1700007200,
            coordinates=GeoCoordinates(latitude=4.2, longitude=7.0),
            severity=SeverityInterval(min_severity=2.0, max_severity=4.0),
            feed_source="UKMTO",
            lineage_hash="hash_adapt_01",
        ),
        MaritimeIncident(
            incident_id="ADAPT-02",
            event_time=1700000000,
            pub_time=1700010800,
            coordinates=GeoCoordinates(latitude=4.3, longitude=7.1),
            severity=SeverityInterval(min_severity=3.0, max_severity=5.5),
            feed_source="MDAT-GOG",
            lineage_hash="hash_adapt_02",
        ),
    ]

    # 3. Calculate lags
    lags = adapter.calculate_publication_lags(test_incidents, in_hours=True)
    assert lags == [2.0, 3.0]

    # 4. Update empirical GPD
    gpd_res = adapter.update_empirical_gpd(test_incidents)
    assert gpd_res.shape_xi <= 0.95
    assert gpd_res.var_99 >= gpd_res.var_95

    # 5. Persist to SQLite
    persisted = adapter.persist_incidents(test_incidents)
    assert persisted == 2

    cur = memory_db.execute("SELECT COUNT(*) FROM incidents")
    assert cur.fetchone()[0] == 2
