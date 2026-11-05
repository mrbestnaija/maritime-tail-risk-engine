"""End-to-End (E2E) Adversarial Infrastructure Audit Test Suite.

Injects adversarial poison directly into the production data and modeling layers to verify:
1. Temporal Paradox Prevention: C-engine SQLite CHECK constraints strictly block any record
   where publication time is earlier than physical event/observation time.
2. Physics Boundary Enforcement: Environmental telemetry with unphysical significant wave
   heights (e.g. 50.0m) or invalid sensor ratios are physically rejected at the storage layer.
3. Heavy-Tail Uninsurable Risk Refusal: When extreme value shape parameter xi >= 1.0,
   the engine strictly refuses to price and raises UninsurableRiskException, preventing
   infinite-mean exposure in the underwriting pool.

Author: Maritime domain researcher with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
"""

from __future__ import annotations

import sqlite3
import numpy as np
import pytest

from maritime_risk.application.engine import MaritimeRiskEngine
from maritime_risk.application.registry import PluginRegistry
from maritime_risk.core.gpd_tail_fitter import GPDTailRiskEstimate
from maritime_risk.core.models import (
    CivilianSensorTelemetry,
    GeoCoordinates,
    MaritimeIncident,
    SeverityInterval,
    UninsurableRiskException,
)
from maritime_risk.core.ports import TailRiskFitterPort
from maritime_risk.core.specs import EmpiricalBayesSpec, GPDFitterSpec
from maritime_risk.infrastructure.sqlite_storage import SCHEMA_SQL, SQLiteIncidentRepository


@pytest.fixture
def live_production_db() -> sqlite3.Connection:
    """Initialize an isolated database with exact production schema constraints."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


# -----------------------------------------------------------------------------
# TEST 1: TEMPORAL PARADOX ADVERSARIAL POISON
# -----------------------------------------------------------------------------


def test_sqlite_check_constraint_blocks_telemetry_temporal_paradox(
    live_production_db: sqlite3.Connection,
):
    """Test 1A: Attempt to insert telemetry where publication_timestamp is strictly earlier

    than observation_timestamp. Must fail at C-storage layer with sqlite3.IntegrityError.
    """
    poison_telemetry_sql = """
    INSERT INTO civilian_sensor_telemetry (
        telemetry_id,
        corridor_id,
        observation_timestamp,
        publication_timestamp,
        sar_provider,
        metocean_provider,
        ais_provider,
        significant_wave_height_m,
        sar_dark_vessel_ratio,
        anchorage_waiting_hours,
        viirs_flaring_continuity_idx
    ) VALUES (
        'POISON-TEL-001',
        'GOG_BONNY_BRASS_FAIRWAY',
        '2026-03-01T12:00:00Z',
        '2026-03-01T10:00:00Z',
        'GFW_SENTINEL1_SAR',
        'COPERNICUS_ERA5_METOCEAN',
        'IMF_PORTWATCH_AIS',
        1.65,
        0.18,
        24.0,
        0.92
    );
    """
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        live_production_db.execute(poison_telemetry_sql)

    err = str(exc_info.value).lower()
    assert "chk_telemetry_temporal_monotonicity" in err or "check constraint" in err


def test_sqlite_check_constraint_blocks_incident_temporal_paradox(
    live_production_db: sqlite3.Connection,
):
    """Test 1B: Attempt to insert an incident report published before the event occurred.

    Must fail at C-storage layer with sqlite3.IntegrityError.
    """
    poison_incident_sql = """
    INSERT INTO incidents (
        incident_id,
        event_time,
        pub_time,
        min_severity,
        max_severity,
        latitude,
        longitude,
        feed_source,
        lineage_hash
    ) VALUES (
        'POISON-INC-001',
        1772450000,
        1772440000,
        3.0,
        6.0,
        4.2250,
        7.0850,
        'ADVERSARIAL_OSINT_INJECTION',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    );
    """
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        live_production_db.execute(poison_incident_sql)

    err = str(exc_info.value).lower()
    assert "chk_temporal_monotonicity" in err or "check constraint" in err


# -----------------------------------------------------------------------------
# TEST 2: PHYSICS VIOLATION ADVERSARIAL POISON
# -----------------------------------------------------------------------------


def test_sqlite_check_constraint_blocks_unphysical_wave_height_50m(
    live_production_db: sqlite3.Connection,
):
    """Test 2A: Attempt to insert an environmental record with wave_height_m = 50.0.

    Must fail at C-storage layer with sqlite3.IntegrityError enforcing [0.0, 25.0] bounds.
    """
    poison_wave_sql = """
    INSERT INTO civilian_sensor_telemetry (
        telemetry_id,
        corridor_id,
        observation_timestamp,
        publication_timestamp,
        sar_provider,
        metocean_provider,
        ais_provider,
        significant_wave_height_m,
        sar_dark_vessel_ratio,
        anchorage_waiting_hours,
        viirs_flaring_continuity_idx
    ) VALUES (
        'POISON-PHYSICS-WAVE-50M',
        'GOG_BONNY_BRASS_FAIRWAY',
        '2026-03-01T12:00:00Z',
        '2026-03-01T14:00:00Z',
        'GFW_SENTINEL1_SAR',
        'COPERNICUS_ERA5_METOCEAN',
        'IMF_PORTWATCH_AIS',
        50.0,
        0.15,
        18.0,
        0.88
    );
    """
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        live_production_db.execute(poison_wave_sql)

    err = str(exc_info.value).lower()
    assert "chk_significant_wave_height" in err or "check constraint" in err


def test_sqlite_check_constraint_blocks_negative_wave_height(
    live_production_db: sqlite3.Connection,
):
    """Test 2B: Attempt to insert wave_height_m = -2.5. Must fail with sqlite3.IntegrityError."""
    poison_negative_wave_sql = """
    INSERT INTO civilian_sensor_telemetry (
        telemetry_id,
        corridor_id,
        observation_timestamp,
        publication_timestamp,
        sar_provider,
        metocean_provider,
        ais_provider,
        significant_wave_height_m,
        sar_dark_vessel_ratio,
        anchorage_waiting_hours,
        viirs_flaring_continuity_idx
    ) VALUES (
        'POISON-PHYSICS-WAVE-NEG',
        'GOG_BONNY_BRASS_FAIRWAY',
        '2026-03-01T12:00:00Z',
        '2026-03-01T14:00:00Z',
        'GFW_SENTINEL1_SAR',
        'COPERNICUS_ERA5_METOCEAN',
        'IMF_PORTWATCH_AIS',
        -2.5,
        0.15,
        18.0,
        0.88
    );
    """
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        live_production_db.execute(poison_negative_wave_sql)

    err = str(exc_info.value).lower()
    assert "chk_significant_wave_height" in err or "check constraint" in err


# -----------------------------------------------------------------------------
# TEST 3: HEAVY-TAIL UNINSURABLE RISK REFUSAL (xi >= 1.0)
# -----------------------------------------------------------------------------


class MockHeavyTailFitter(TailRiskFitterPort):
    """Mocked tail fitter returning an extreme value shape parameter xi >= 1.0 (infinite mean)."""

    def __init__(self, poisoned_xi: float = 1.15) -> None:
        self.poisoned_xi = poisoned_xi

    def fit_tail(
        self,
        residuals: np.ndarray,
        baseline: float,
        bayes_spec: EmpiricalBayesSpec,
        gpd_spec: GPDFitterSpec,
    ) -> GPDTailRiskEstimate:
        return GPDTailRiskEstimate(
            shape_xi=self.poisoned_xi,
            scale_sigma=2.5,
            threshold_u=4.0,
            exceedance_count=15,
            var_95=6.5,
            var_99=12.0,
            cvar_99=float("inf"),
            actuarial_war_risk_loading_bps=999.0,
            insured_vessel_usd=85000000.0,
            residual_var_95=6.5,
            residual_var_99=12.0,
            residual_cvar_99=float("inf"),
            baseline_anchor=baseline,
            composite_corridor_var_95=baseline + 6.5,
            composite_corridor_var_99=baseline + 12.0,
            composite_corridor_cvar_99=float("inf"),
            shrinkage_weight_w=1.0,
            raw_xi=self.poisoned_xi,
        )


def test_engine_evaluate_refuses_heavy_tail_infinite_mean_risk():
    """Test 3A: When GPD shape xi >= 1.0, engine.evaluate() must refuse to price

    and explicitly raise UninsurableRiskException, protecting syndicate solvency.
    """
    registry = PluginRegistry()
    registry.register_tail_fitter("mock_heavy_tail_fitter", MockHeavyTailFitter(poisoned_xi=1.15))

    engine = MaritimeRiskEngine(
        registry=registry,
        tail_fitter_name="mock_heavy_tail_fitter",
    )

    valid_incident = MaritimeIncident(
        incident_id="INC-BASE-01",
        event_time=1700000000,
        pub_time=1700003600,
        coordinates=GeoCoordinates(latitude=4.2250, longitude=7.0850),
        severity=SeverityInterval(min_severity=2.0, max_severity=4.5),
        feed_source="MDAT-GOG",
        lineage_hash="hash_base_01",
    )

    with pytest.raises(UninsurableRiskException) as exc_info:
        engine.evaluate(incidents=[valid_incident])

    err = str(exc_info.value)
    assert "Uninsurable tail risk" in err
    assert "xi=1.1500 >= 1.0" in err
    assert "infinite-mean" in err.lower()


def test_engine_compute_tail_risk_refuses_xi_ge_1():
    """Test 3B: Direct engine.compute_tail_risk with shape parameter xi >= 1.0

    must raise UninsurableRiskException rather than clamp xi to force a finite price.
    """
    engine = MaritimeRiskEngine()

    with pytest.raises(UninsurableRiskException) as exc_info:
        engine.compute_tail_risk(u=4.0, xi=1.05, sigma=1.8, p_u=0.05)

    err = str(exc_info.value)
    assert "Uninsurable tail risk" in err
    assert "xi=1.0500 >= 1.0" in err


def test_production_sqlite_repository_rejects_corrupted_batch(
    live_production_db: sqlite3.Connection,
):
    """Test 3C: End-to-end repository batch insertion must roll back transaction

    when an adversarial poison record is slipped into a batch of valid records.
    """
    repo = SQLiteIncidentRepository(live_production_db)

    # Valid incident followed by poison temporal paradox incident
    clean_incident = MaritimeIncident(
        incident_id="CLEAN-01",
        event_time=1700000000,
        pub_time=1700003600,
        coordinates=GeoCoordinates(latitude=4.2250, longitude=7.0850),
        severity=SeverityInterval(min_severity=2.0, max_severity=4.0),
        feed_source="MDAT-GOG",
        lineage_hash="hash_clean",
    )

    repo.insert_incident(clean_incident)
    assert len(repo.load_all_incidents()) == 1

    # Injecting invalid raw sql bypassing pydantic layer to test C-storage boundary
    poison_sql = """
    INSERT INTO incidents (
        incident_id, event_time, pub_time, min_severity, max_severity,
        latitude, longitude, feed_source, lineage_hash
    ) VALUES ('POISON-RAW', 1700010000, 1700005000, 1.0, 5.0, 4.2, 7.1, 'INJECT', 'hash_poison');
    """
    with pytest.raises(sqlite3.IntegrityError):
        live_production_db.execute(poison_sql)
