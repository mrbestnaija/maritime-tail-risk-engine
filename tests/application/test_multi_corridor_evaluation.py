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
