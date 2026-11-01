"""PyTest integration suite verifying multi-corridor configuration loading,
Empirical Bayes shape regularization, and JWC pricing across distinct fairways.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from maritime_risk.application.engine import MaritimeRiskEngine
from maritime_risk.infrastructure.osint_feed_loader import OSINTFeedLoader


@pytest.mark.parametrize(
    "corridor_id,expected_benchmark_bps",
    [
        ("GOG_BONNY_BRASS_FAIRWAY", 15.0),
        ("GOG_ESCRAVOS_FORCADOS_APPROACH", 12.5),
        ("GOG_LAGOS_SAA_ANCHORAGE", 10.0),
    ],
)
def test_multi_corridor_engine_initialization(corridor_id: str, expected_benchmark_bps: float):
    """Asserts that MaritimeRiskEngine initializes successfully for all configured fairways."""
    engine = MaritimeRiskEngine.from_config_files(
        corridor_id=corridor_id,
        vessel_profile_id="STANDARD_SUEZMAX_85M",
    )

    assert engine.corridor_spec.corridor_id == corridor_id
    assert engine.corridor_spec.jwc_market_benchmark_bps == expected_benchmark_bps
    assert engine.vessel_spec.insured_vessel_usd == 85_000_000.0


def test_multi_corridor_evaluation_isolation():
    """Asserts that different fairways yield distinct actuarial outputs due to spatial priors."""
    engine_bonny = MaritimeRiskEngine.from_config_files(
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        vessel_profile_id="STANDARD_SUEZMAX_85M",
    )
    engine_lagos = MaritimeRiskEngine.from_config_files(
        corridor_id="GOG_LAGOS_SAA_ANCHORAGE",
        vessel_profile_id="STANDARD_SUEZMAX_85M",
    )

    # Evaluate headless in-memory payloads
    audit_bonny = engine_bonny.evaluate(incidents=[], telemetry=[])
    audit_lagos = engine_lagos.evaluate(incidents=[], telemetry=[])

    # Verify each corridor applies its specific prior and benchmark
    assert audit_bonny.corridor_spec.prior_xi == 0.18
    assert audit_lagos.corridor_spec.prior_xi == 0.12
    assert audit_bonny.jwc_pricing.market_benchmark_bps == 15.0
    assert audit_lagos.jwc_pricing.market_benchmark_bps == 10.0


def test_multi_corridor_data_fixture_evaluation():
    """Asserts that evaluating with fairway-specific data fixtures produces valid audit outputs."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_root / "data"

    for corridor_id, inc_file, tel_file in [
        ("GOG_BONNY_BRASS_FAIRWAY", "gog_bonny_brass_vintage_osint.json", "gog_bonny_brass_civilian_telemetry.json"),
        ("GOG_ESCRAVOS_FORCADOS_APPROACH", "gog_escravos_forcados_osint.json", "gog_escravos_forcados_telemetry.json"),
        ("GOG_LAGOS_SAA_ANCHORAGE", "gog_lagos_saa_osint.json", "gog_lagos_saa_telemetry.json"),
    ]:
        inc_path = data_dir / inc_file
        tel_path = data_dir / tel_file

        assert inc_path.exists(), f"Incident fixture missing: {inc_path}"
        assert tel_path.exists(), f"Telemetry fixture missing: {tel_path}"

        incidents, inc_sha = OSINTFeedLoader.load_incidents_from_json(inc_path)
        telemetry, tel_sha = OSINTFeedLoader.load_civilian_telemetry_from_json(tel_path)

        engine = MaritimeRiskEngine.from_config_files(corridor_id=corridor_id)
        result = engine.evaluate(
            incidents=incidents,
            telemetry=telemetry,
            dataset_sha256=inc_sha,
            telemetry_sha256=tel_sha,
        )

        assert result.corridor_spec.corridor_id == corridor_id
        assert result.raw_incident_count == len(incidents)
        assert result.jwc_result.insured_vessel_usd == 85_000_000.0
        assert result.gpd_result.shape_xi > 0.0
        assert result.jwc_pricing.actuarial_7d_war_risk_ap_bps > 0.0
        assert result.jwc_pricing.market_benchmark_bps > 0.0


def test_multi_corridor_distinct_shrunk_xi():
    """Asserts that Bonny, Escravos, and Lagos yield distinctly different xi_shrunk values matching their priors."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_root / "data"

    corridors = [
        ("GOG_BONNY_BRASS_FAIRWAY", "gog_bonny_brass_vintage_osint.json", "gog_bonny_brass_civilian_telemetry.json", 0.0753),
        ("GOG_ESCRAVOS_FORCADOS_APPROACH", "gog_escravos_forcados_osint.json", "gog_escravos_forcados_telemetry.json", 0.3827),
        ("GOG_LAGOS_SAA_ANCHORAGE", "gog_lagos_saa_osint.json", "gog_lagos_saa_telemetry.json", 0.3320),
    ]

    results: dict[str, float] = {}
    for cid, inc_f, tel_f, expected_xi in corridors:
        inc_path = data_dir / inc_f
        tel_path = data_dir / tel_f
        incidents, inc_sha = OSINTFeedLoader.load_incidents_from_json(inc_path)
        telemetry, tel_sha = OSINTFeedLoader.load_civilian_telemetry_from_json(tel_path)
        engine = MaritimeRiskEngine.from_config_files(corridor_id=cid)
        res = engine.evaluate(incidents=incidents, telemetry=telemetry, dataset_sha256=inc_sha, telemetry_sha256=tel_sha)
        results[cid] = res.gpd_result.shape_xi
        assert res.gpd_result.shape_xi == pytest.approx(expected_xi, abs=0.01)
        assert res.gpd_result.shape_xi <= engine.hyperparams.gpd.xi_max

    # Assert distinct differentiation across corridors
    assert len(set(results.values())) == 3
    assert results["GOG_BONNY_BRASS_FAIRWAY"] != results["GOG_ESCRAVOS_FORCADOS_APPROACH"]
    assert results["GOG_ESCRAVOS_FORCADOS_APPROACH"] != results["GOG_LAGOS_SAA_ANCHORAGE"]
    assert results["GOG_BONNY_BRASS_FAIRWAY"] != results["GOG_LAGOS_SAA_ANCHORAGE"]


def test_lagos_saa_anchor_lower_hazard_and_ap_than_transit():
    """Asserts that Lagos SAA (Anchor) yields a lower AP than Escravos (Underway) holding other factors equal."""
    engine_escravos = MaritimeRiskEngine.from_config_files(corridor_id="GOG_ESCRAVOS_FORCADOS_APPROACH")
    engine_lagos = MaritimeRiskEngine.from_config_files(corridor_id="GOG_LAGOS_SAA_ANCHORAGE")

    assert engine_escravos.corridor_spec.operational_state == "UNDERWAY"
    assert engine_lagos.corridor_spec.operational_state == "AT_ANCHOR"

    from maritime_risk.core.jwc_pricer import price_cox_7day_war_risk_ap
    from maritime_risk.core.specs import CoxHazardSpec

    vessel = engine_escravos.vessel_spec
    cox_spec = CoxHazardSpec()

    ap_escravos = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=0.25,
        distance_pmsc_km=180.0,
        wave_height_m=1.2,
        composite_cvar_99=10.0,
        vessel_spec=vessel,
        corridor_spec=engine_escravos.corridor_spec,
        cox_spec=cox_spec,
    )
    ap_lagos = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=0.25,
        distance_pmsc_km=180.0,
        wave_height_m=1.2,
        composite_cvar_99=10.0,
        vessel_spec=vessel,
        corridor_spec=engine_lagos.corridor_spec,
        cox_spec=cox_spec,
    )

    assert ap_lagos.daily_hazard_rate < ap_escravos.daily_hazard_rate
    assert ap_lagos.calibrated_7d_breach_prob < ap_escravos.calibrated_7d_breach_prob
    assert ap_lagos.actuarial_7d_war_risk_ap_bps < ap_escravos.actuarial_7d_war_risk_ap_bps


def test_high_port_wait_hours_strictly_increases_regime_multiplier():
    """Asserts that high port wait hours strictly increase the regime multiplier in the pricer output."""
    from datetime import datetime, timezone
    from maritime_risk.core.models import CivilianSensorTelemetry
    from maritime_risk.core.regime_switch import compute_regime_multiplier
    from maritime_risk.core.specs import MacroRegimeSpec

    spec = MacroRegimeSpec(baseline_port_wait_hours=24.0, congestion_shock_alpha=0.50, max_regime_multiplier=2.0)

    wait_24 = compute_regime_multiplier(24.0, spec=spec)
    wait_36 = compute_regime_multiplier(36.0, spec=spec)
    wait_48 = compute_regime_multiplier(48.0, spec=spec)
    wait_96 = compute_regime_multiplier(96.0, spec=spec)

    assert wait_24 == 1.0
    assert wait_24 < wait_36 < wait_48
    assert wait_48 <= wait_96 <= spec.max_regime_multiplier
    assert wait_96 == pytest.approx(2.0, abs=1e-4)

    # In pricer: scaling strictly increases AP
    from maritime_risk.core.jwc_pricer import compute_jwc_7day_war_risk_ap, price_cox_7day_war_risk_ap
    from maritime_risk.core.specs import CorridorSpec, CoxHazardSpec, VesselProfileSpec

    vessel = VesselProfileSpec()
    corridor = CorridorSpec()
    p_low = compute_jwc_7day_war_risk_ap(
        calibrated_7d_breach_prob=0.10,
        composite_cvar_99=10.0,
        vessel_spec=vessel,
        corridor_spec=corridor,
        regime_multiplier=1.0,
    )
    p_high = compute_jwc_7day_war_risk_ap(
        calibrated_7d_breach_prob=0.10,
        composite_cvar_99=10.0,
        vessel_spec=vessel,
        corridor_spec=corridor,
        regime_multiplier=1.5,
    )
    assert p_high.actuarial_7d_war_risk_ap_bps == pytest.approx(p_low.actuarial_7d_war_risk_ap_bps * 1.5, abs=1e-4)
    assert p_high.actuarial_7d_war_risk_ap_bps > p_low.actuarial_7d_war_risk_ap_bps

    # In full engine evaluation with telemetry: higher port wait hours strictly increase regime multiplier and AP
    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_root / "data"
    incidents, inc_sha = OSINTFeedLoader.load_incidents_from_json(data_dir / "gog_lagos_saa_osint.json")
    telemetry, tel_sha = OSINTFeedLoader.load_civilian_telemetry_from_json(data_dir / "gog_lagos_saa_telemetry.json")

    engine = MaritimeRiskEngine.from_config_files(corridor_id="GOG_LAGOS_SAA_ANCHORAGE")
    res_baseline = engine.evaluate(incidents=incidents, telemetry=telemetry, dataset_sha256=inc_sha, telemetry_sha256=tel_sha)

    # Telemetry with wait hours boosted by 1.5x
    import copy
    congested_telemetry = [copy.deepcopy(t) for t in telemetry]
    for t in congested_telemetry:
        object.__setattr__(t, "anchorage_waiting_hours", float(t.anchorage_waiting_hours) * 1.5)

    res_congested = engine.evaluate(incidents=incidents, telemetry=congested_telemetry, dataset_sha256=inc_sha, telemetry_sha256=tel_sha)

    assert res_congested.jwc_result.regime_multiplier > res_baseline.jwc_result.regime_multiplier
    assert res_congested.jwc_result.actuarial_7d_war_risk_ap_bps > res_baseline.jwc_result.actuarial_7d_war_risk_ap_bps
