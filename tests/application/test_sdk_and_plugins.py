"""Tests for institutional SDK facade, protocol ports, and plugin registry.

Validates:
1. Headless in-memory evaluation (zero file I/O, dict/dataclass ingestion, serializations).
2. Corridor and vessel profile switching (Lagos SAA vs Bonny/Brass, VLCC vs Suezmax).
3. Custom pricer and incident source plugin registration via PluginRegistry.
4. Parity test verifying exact baseline reproduction of Phase 1/2B Bonny-Brass audit.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any
import numpy as np
import pytest

import maritime_risk as mtr
from core.models import CivilianSensorTelemetry, GeoCoordinates, MaritimeIncident, SeverityInterval
from core.ports import ActuarialPricerPort, IncidentSourcePort
from core.specs import (
    CorridorSpec,
    EngineConfigBundle,
    VesselProfileSpec,
    load_corridor_spec,
    load_vessel_spec,
)
from application.engine import MaritimeRiskEngine, CorridorAuditResult
from application.registry import PluginRegistry, default_registry
from infrastructure.osint_feed_loader import OSINTFeedLoader


def test_sdk_headless_in_memory_evaluation() -> None:
    """Test 100% headless in-memory evaluation with zero file I/O."""
    # Instantiate engine with pure in-memory specs
    corridor_spec = CorridorSpec(
        corridor_id="SYNTHETIC_TEST_CORRIDOR",
        description="Synthetic Test Fairway",
        latitude_min=3.0,
        latitude_max=5.0,
        longitude_min=5.0,
        longitude_max=7.0,
    )
    vessel_spec = VesselProfileSpec(
        vessel_profile_id="SYNTHETIC_HANDYMAX",
        description="Synthetic Handymax Tanker",
        insured_vessel_usd=40_000_000.0,
        daily_demurrage_usd=25_000.0,
        daily_escort_cost_usd=12_000.0,
    )
    engine = mtr.MaritimeRiskEngine.from_specs(
        corridor_spec=corridor_spec,
        vessel_spec=vessel_spec,
    )

    # Ingest synthetic in-memory incidents (mix of Pydantic model and raw dict)
    base_time = 1673740800  # 2023-01-15T00:00:00Z
    incidents = []
    for i in range(15):
        inc_data = {
            "incident_id": f"SYNTH-{i:03d}",
            "event_time": base_time + i * 86400,
            "pub_time": base_time + i * 86400 + 3600,
            "severity": SeverityInterval(min_severity=2.0, max_severity=4.0 + (i % 3)),
            "coordinates": GeoCoordinates(latitude=4.2, longitude=6.8),
            "feed_source": "SYNTH_SRC",
            "lineage_hash": f"hash_{i}",
        }
        # Interleave dicts and model instances
        if i % 2 == 0:
            incidents.append(MaritimeIncident(**inc_data))
        else:
            incidents.append(inc_data)

    # Ingest synthetic telemetry (mix of model and raw dict)
    telemetry = []
    for i in range(20):
        t_dt = datetime.datetime.fromtimestamp(base_time + i * 86400, tz=datetime.timezone.utc)
        tel_data = {
            "telemetry_id": f"TEL-{i:03d}",
            "corridor_id": "SYNTHETIC_TEST_CORRIDOR",
            "observation_timestamp": t_dt,
            "publication_timestamp": t_dt + datetime.timedelta(hours=2),
            "sar_provider": "GFW_SENTINEL1_SAR",
            "metocean_provider": "COPERNICUS_ERA5_METOCEAN",
            "ais_provider": "IMF_PORTWATCH_AIS",
            "significant_wave_height_m": 1.5 + 0.1 * (i % 5),
            "sar_dark_vessel_ratio": 0.20 + 0.02 * (i % 4),
            "anchorage_waiting_hours": 14.0 + float(i),
            "viirs_flaring_continuity_idx": 0.85,
        }
        if i % 2 == 0:
            telemetry.append(CivilianSensorTelemetry(**tel_data))
        else:
            telemetry.append(tel_data)

    # Evaluate in memory
    result = engine.evaluate(incidents=incidents, telemetry=telemetry)
    assert isinstance(result, CorridorAuditResult)
    assert result.corridor_spec.corridor_id == "SYNTHETIC_TEST_CORRIDOR"
    assert result.vessel_spec.vessel_profile_id == "SYNTHETIC_HANDYMAX"
    assert result.raw_incident_count == 15
    assert result.dedup_incident_count <= 15

    # Check serialization methods
    payload_dict = result.to_dict()
    assert isinstance(payload_dict, dict)
    assert "corridor_id" in payload_dict
    assert "mssa_result" in payload_dict
    assert "gpd_result" in payload_dict
    assert "hydro_result" in payload_dict
    assert "sprt_result" in payload_dict
    assert "jwc_result" in payload_dict

    # Check JSON serialization
    payload_json = result.to_json()
    assert isinstance(payload_json, str)
    parsed_json = json.loads(payload_json)
    assert parsed_json["corridor_id"] == "SYNTHETIC_TEST_CORRIDOR"
    assert parsed_json["vessel_spec"]["insured_vessel_usd"] == 40_000_000.0

    # Check Markdown serialization
    md_text = result.to_markdown()
    assert isinstance(md_text, str)
    assert "### COMMERCIAL DISCLAIMER" in md_text
    assert "SYNTHETIC TEST FAIRWAY" in md_text
    assert "$40,000,000 USD" in md_text


    # Verify DataFrame ingestion directly
    class MockDataFrame:
        def __init__(self, records: list[dict[str, Any]]):
            self._records = records

        def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
            return self._records

    df_incidents = MockDataFrame([{"incident_id": f"DF-{i}", "event_time": base_time + i * 86400, "pub_time": base_time + i * 86400 + 10, "coordinates": GeoCoordinates(latitude=4.2, longitude=6.8), "severity": SeverityInterval(min_severity=2.0, max_severity=4.0), "feed_source": "DF_SRC", "lineage_hash": "df_hash"} for i in range(10)])
    df_telemetry = MockDataFrame([{"telemetry_id": f"DF-TEL-{i}", "corridor_id": "SYNTHETIC_TEST_CORRIDOR", "observation_timestamp": datetime.datetime.fromtimestamp(base_time + i * 86400, tz=datetime.timezone.utc), "publication_timestamp": datetime.datetime.fromtimestamp(base_time + i * 86400 + 3600, tz=datetime.timezone.utc), "significant_wave_height_m": 1.6, "sar_dark_vessel_ratio": 0.2, "anchorage_waiting_hours": 15.0} for i in range(10)])

    res_df = engine.evaluate(incidents=df_incidents, telemetry=df_telemetry)
    assert res_df.raw_incident_count == 10
    assert res_df.jwc_result.actuarial_7d_war_risk_ap_bps >= 0.0


def test_sdk_corridor_and_vessel_switching(tmp_path: Path) -> None:
    """Test switching corridors and vessel profiles changes risk metrics and pricing."""
    # Test loading configs with default config_dir from an external directory
    import os
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Should load seamlessly using packaged configs fallback
        engine_escravos = mtr.MaritimeRiskEngine.from_config_files(
            corridor_id="GOG_ESCRAVOS_FORCADOS_APPROACH",
            vessel_profile_id="VLCC_LNG_CARRIER_160M",
        )
        assert engine_escravos.corridor_spec.corridor_id == "GOG_ESCRAVOS_FORCADOS_APPROACH"
        assert engine_escravos.vessel_spec.insured_vessel_usd == 160_000_000.0
    finally:
        os.chdir(orig_cwd)

    configs_dir = Path(__file__).resolve().parent.parent.parent / "configs"

    # Profile 1: Suezmax in Bonny/Brass
    engine_suezmax = mtr.MaritimeRiskEngine.from_config_files(
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        vessel_profile_id="STANDARD_SUEZMAX_85M",
        config_dir=configs_dir,
    )

    # Profile 2: VLCC in Bonny/Brass
    engine_vlcc = mtr.MaritimeRiskEngine.from_config_files(
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        vessel_profile_id="VLCC_LNG_CARRIER_160M",
        config_dir=configs_dir,
    )

    # Profile 3: Suezmax in Lagos SAA Anchorage
    engine_lagos = mtr.MaritimeRiskEngine.from_config_files(
        corridor_id="GOG_LAGOS_SAA_ANCHORAGE",
        vessel_profile_id="STANDARD_SUEZMAX_85M",
        config_dir=configs_dir,
    )

    # Verify specs reflect the configuration files
    assert engine_suezmax.vessel_spec.insured_vessel_usd == 85_000_000.0
    assert engine_vlcc.vessel_spec.insured_vessel_usd == 160_000_000.0
    assert engine_lagos.corridor_spec.corridor_id == "GOG_LAGOS_SAA_ANCHORAGE"

    # Run evaluations with default fallback data
    res_suezmax = engine_suezmax.evaluate()
    res_vlcc = engine_vlcc.evaluate()
    res_lagos = engine_lagos.evaluate()

    # VLCC has higher insured value and higher demurrage loss
    assert res_vlcc.jwc_result.insured_vessel_usd == 160_000_000.0
    assert res_suezmax.jwc_result.insured_vessel_usd == 85_000_000.0
    assert res_vlcc.jwc_result.cvar_99_demurrage_usd > res_suezmax.jwc_result.cvar_99_demurrage_usd

    # Escort savings differ due to daily escort cost
    assert res_vlcc.vessel_spec.daily_escort_cost_usd == 22_000.0
    assert res_suezmax.vessel_spec.daily_escort_cost_usd == 18_500.0


def test_custom_pricer_and_source_plugin_registration() -> None:
    """Test custom ActuarialPricerPort and IncidentSourcePort registration via PluginRegistry and @decorator."""
    from core.jwc_pricer import JWCPricingResult

    # 1. Register custom pricer satisfying ActuarialPricerPort via @default_registry decorator
    @default_registry.register_pricer("custom_syndicate_pricer")
    class CustomSyndicatePricer:
        def price_transit(
            self,
            breach_prob_7d: float,
            composite_cvar_99: float,
            hydro_feasibility: float,
            vessel_spec: VesselProfileSpec,
            corridor_spec: CorridorSpec,
        ) -> JWCPricingResult:
            flat_rate_bps = 42.42
            expected_loss = vessel_spec.insured_vessel_usd * (flat_rate_bps / 10000.0)
            return JWCPricingResult(
                calibrated_7d_breach_prob=breach_prob_7d,
                effective_vessel_breach_prob=breach_prob_7d * hydro_feasibility,
                composite_cvar_99=composite_cvar_99,
                delay_days=5.0,
                cvar_99_demurrage_usd=100_000.0,
                catastrophic_tail_loss_usd=2_000_000.0,
                expected_7d_tail_loss_usd=expected_loss,
                actuarial_7d_war_risk_ap_bps=flat_rate_bps,
                jwc_market_benchmark_bps=15.0,
                mispricing_spread_bps=flat_rate_bps - 15.0,
                per_transit_mispricing_usd=expected_loss - (vessel_spec.insured_vessel_usd * 0.0015),
                insured_vessel_usd=vessel_spec.insured_vessel_usd,
            )

    # 2. Define custom incident source satisfying IncidentSourcePort
    class CustomMockIncidentSource:
        def fetch_incidents(
            self, corridor_id: str, as_of: datetime.datetime | None = None
        ) -> list[MaritimeIncident]:
            return []

    # Verify structural protocol conformance at runtime
    assert isinstance(CustomSyndicatePricer(), ActuarialPricerPort)
    assert isinstance(CustomMockIncidentSource(), IncidentSourcePort)

    # 3. Prove default_registry resolved the decorated pricer
    assert "custom_syndicate_pricer" in default_registry.list_pricers()
    engine_custom = mtr.MaritimeRiskEngine(pricer_name="custom_syndicate_pricer")
    res_custom = engine_custom.evaluate()
    assert res_custom.jwc_result.actuarial_7d_war_risk_ap_bps == 42.42

    # 4. Prove custom registry instantiation and evaluate_from_sources
    custom_registry = PluginRegistry(auto_discover=False)
    custom_registry.register_pricer("custom_syndicate_pricer", CustomSyndicatePricer())
    custom_registry.register_incident_source("mock_source", CustomMockIncidentSource())

    class CustomMockTelemetrySource:
        def fetch_telemetry(
            self, corridor_id: str, as_of: datetime.datetime | None = None
        ) -> list[CivilianSensorTelemetry]:
            return []

    engine_sources = mtr.MaritimeRiskEngine(registry=custom_registry, pricer_name="custom_syndicate_pricer")
    res_sources = engine_sources.evaluate_from_sources(
        incident_source=CustomMockIncidentSource(),
        telemetry_source=CustomMockTelemetrySource(),
    )
    assert res_sources.jwc_result.actuarial_7d_war_risk_ap_bps == 42.42


def test_bonny_brass_default_reproduces_exact_baseline() -> None:
    """Verify that default engine reproduces exact Phase 1 & 2B baseline metrics."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data"
    dataset_file = data_dir / "sample_gog_osint_vintage.csv"
    telemetry_file = data_dir / "gog_bonny_brass_civilian_telemetry.json"
    configs_dir = base_dir / "configs"

    assert dataset_file.exists(), f"Sample dataset missing at {dataset_file}"
    assert telemetry_file.exists(), f"Telemetry dataset missing at {telemetry_file}"

    raw_incidents, dataset_sha256 = OSINTFeedLoader.load_incidents_from_csv(dataset_file)
    telemetry_records, telemetry_sha256 = OSINTFeedLoader.load_civilian_telemetry_from_json(telemetry_file)

    engine = mtr.MaritimeRiskEngine.from_config_files(
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        vessel_profile_id="STANDARD_SUEZMAX_85M",
        config_dir=configs_dir,
    )

    res = engine.evaluate(
        incidents=raw_incidents,
        telemetry=telemetry_records,
        dataset_sha256=dataset_sha256,
        telemetry_sha256=telemetry_sha256,
    )

    # Exact baseline reproduction checks
    assert res.dataset_sha256 == "cac4ca9116cbb0f0038e4df511092f2a1025eabc840a0a5447f97849f88af39c"
    assert res.telemetry_sha256 == "c3685e086d228af1f3d0e44314f3c50e5af000406c0d55559d68d77c95157db7"
    assert res.raw_incident_count == 40
    assert res.dedup_incident_count == 31

    # Empirical Bayes Shrinkage
    assert res.gpd_result.raw_xi == pytest.approx(-0.5000, abs=1e-4)
    assert res.gpd_result.shape_xi == pytest.approx(0.3936, abs=1e-3)
    assert res.gpd_result.shrinkage_weight_w == pytest.approx(0.4545, abs=1e-4)
    assert res.gpd_result.scale_sigma == pytest.approx(2.4740, abs=1e-3)
    assert res.gpd_result.threshold_u == pytest.approx(1.9945, abs=1e-3)

    # Quantiles (Unclamped)
    assert res.gpd_result.composite_corridor_cvar_99 == pytest.approx(36.97, abs=0.1)
    assert res.jwc_result.composite_cvar_99 == pytest.approx(36.97, abs=0.1)

    # Pricing & Regime Scaling
    assert res.jwc_result.regime_multiplier == pytest.approx(1.4688, abs=1e-3)
    assert res.jwc_result.operational_state == "UNDERWAY"
    assert res.jwc_result.actuarial_7d_war_risk_ap_bps == pytest.approx(131.22, abs=0.1)
    assert res.jwc_result.jwc_market_benchmark_bps == pytest.approx(15.0, abs=1e-4)
    assert res.jwc_result.mispricing_spread_bps == pytest.approx(116.22, abs=0.1)

    # SPRT surveillance state
    assert res.sprt_result.state == "H1_ACCEPTED"
    assert res.sprt_result.breach_count == 10
    assert res.sprt_result.sample_size == 40
