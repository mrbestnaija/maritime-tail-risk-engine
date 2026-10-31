"""Test Suite for Phase 2B Remediation & High-Edge Domain Modules.

Covers:
1. Empirical Bayes GPD Parameter Shrinkage (anti-railing at xi = -0.5000)
2. Hydrodynamic Small-Skiff Swamping Physics (logistic curve & dark vessel hazard)
3. First-Principles Lloyd's JWC 7-Day Additional Premium & Demurrage Pricing
4. Wald's Sequential Probability Ratio Test (SPRT) Surveillance Gates
5. Audit Manifest Integrity & Cryptographic Lineage Verification
6. Hypothesis Fuzzing for Physical Boundaries and Parameter Invariants
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_engine_dir = str(Path(__file__).resolve().parent.parent.parent)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from core.empirical_bayes import shrink_gpd_parameters
from core.gpd_tail_fitter import fit_pot_gpd
from core.hydro_envelope import (
    composite_dark_vessel_hazard,
    evaluate_hydrodynamic_envelope,
    skiff_boarding_feasibility,
)
from core.jwc_pricer import compute_jwc_7day_war_risk_ap
from core.sprt_gates import evaluate_sprt_surveillance_gate
from infrastructure.audit_manifest import AuditManifestBuilder


# ==============================================================================
# 1. Empirical Bayes Shrinkage Tests
# ==============================================================================

def test_empirical_bayes_shrinkage_pulls_away_from_negative_half():
    """Verify Empirical Bayes regularizes small samples away from xi = -0.5000 railing."""
    # Small sample that historically railed at -0.5000 in pure MLE
    exceedances = [0.15, 0.45, 0.82, 1.10, 1.95]
    xi_shrunk, sigma_shrunk, w = shrink_gpd_parameters(
        exceedances, prior_xi=0.18, prior_sigma=1.5, kappa=12.0
    )

    assert not math.isnan(xi_shrunk)
    assert not math.isnan(sigma_shrunk)
    assert not math.isnan(w)
    # Must NOT rail at -0.5000
    assert xi_shrunk > -0.45, f"xi railed at lower bound: {xi_shrunk}"
    assert xi_shrunk <= 0.95
    assert sigma_shrunk > 0.0
    # For N_u = 5, w = 5 / (5 + 12) = 5 / 17 approx 0.294
    assert 0.28 < w < 0.31


def test_empirical_bayes_edge_cases():
    """Verify empty and single-element exceedance arrays return prior."""
    xi_0, sig_0, w_0 = shrink_gpd_parameters([], prior_xi=0.18, prior_sigma=1.5)
    assert xi_0 == 0.18
    assert sig_0 == 1.5
    assert w_0 == 0.0

    xi_1, sig_1, w_1 = shrink_gpd_parameters([2.5], prior_xi=0.18, prior_sigma=1.5)
    assert xi_1 == 0.18
    assert sig_1 == 1.5
    assert w_1 == 0.0


# ==============================================================================
# 2. Upgraded GPD Fitter & Composite Quantiles
# ==============================================================================

def test_gpd_composite_corridor_quantiles_ordered():
    """Verify strict quantile monotonicity: composite CVaR_99 > VaR_99 > VaR_95 and positive heavy tail."""
    data = [1.2, 1.5, 1.8, 2.1, 2.4, 2.8, 3.2, 3.8, 4.5, 5.2, 6.1, 7.5, 8.9]
    res = fit_pot_gpd(data, baseline_anchor=4.46, apply_shrinkage=True)

    # Monotonicity check: strict inequality
    assert res.composite_corridor_var_99 > res.composite_corridor_var_95
    assert res.composite_corridor_cvar_99 > res.composite_corridor_var_99
    # Positive heavy tail shape parameter from Empirical Bayes shrinkage
    assert 0.05 <= res.shape_xi <= 0.25
    # Baseline anchor preserved
    assert res.baseline_anchor == 4.46
    assert math.isclose(res.composite_corridor_var_95, res.baseline_anchor + res.residual_var_95, rel_tol=1e-6)


# ==============================================================================
# 3. Hydrodynamic Physics & Swamping Envelope Tests
# ==============================================================================

def test_skiff_boarding_feasibility_physics_curve():
    """Verify logistic swamping curve behavior at critical sea-state thresholds."""
    # Calm sea (0.8m): near 100% feasibility
    p_calm = skiff_boarding_feasibility(0.8, wind_knots=10.0)
    assert p_calm > 0.90, f"Calm sea should be highly feasible: {p_calm}"

    # Critical threshold (1.85m): approximately 50% feasibility
    p_crit = skiff_boarding_feasibility(1.85, wind_knots=15.0)
    assert 0.45 <= p_crit <= 0.55, f"Transition at H_0 should be ~50%: {p_crit}"

    # Rough sea (2.6m): small skiff swamping hazard, feasibility < 10%
    p_rough = skiff_boarding_feasibility(2.6, wind_knots=15.0)
    assert p_rough < 0.10, f"Rough sea should swamp small skiffs: {p_rough}"

    # Monotonicity: higher waves must decrease feasibility
    assert skiff_boarding_feasibility(1.0) > skiff_boarding_feasibility(1.5) > skiff_boarding_feasibility(2.0)


def test_composite_dark_vessel_hazard():
    """Verify composite dark vessel hazard scaling and limits."""
    # High dark vessel ratio (0.80) in calm sea (1.0m) -> High hazard
    hazard_high = composite_dark_vessel_hazard(1.0, sar_dark_ratio=0.80)
    assert hazard_high > 6.0

    # High dark vessel ratio (0.80) in stormy sea (3.0m) -> Low hazard (swamped)
    hazard_storm = composite_dark_vessel_hazard(3.0, sar_dark_ratio=0.80)
    assert hazard_storm < 0.5

    # Zero dark vessel ratio -> Zero hazard
    assert composite_dark_vessel_hazard(1.0, sar_dark_ratio=0.0) == 0.0

    env = evaluate_hydrodynamic_envelope(1.62, 0.259, wind_knots=12.0)
    assert 0.0 <= env.boarding_feasibility <= 1.0
    assert 0.0 <= env.composite_hazard_score <= 10.0


# ==============================================================================
# 4. First-Principles Lloyd's JWC Pricing Tests
# ==============================================================================

def test_jwc_7day_war_risk_pricer_first_principles():
    """Verify Lloyd's JWC pricing translates CVaR into expected loss and bps AP."""
    vessel_usd = 85_000_000.0
    res = compute_jwc_7day_war_risk_ap(
        calibrated_7d_breach_prob=0.25,
        composite_cvar_99=10.0,
        insured_vessel_usd=vessel_usd,
        daily_demurrage_usd=45_000.0,
        catastrophic_boarding_loss_usd=3_500_000.0,
        jwc_market_benchmark_bps=15.0,
    )

    # 10.0 severity -> 8.5 delay days -> 8.5 * $45,000 = $382,500 demurrage
    assert res.delay_days == 8.5
    assert res.cvar_99_demurrage_usd == 382_500.0

    # Catastrophic loss at 10.0 / 10.0 = $3,500,000
    assert res.catastrophic_tail_loss_usd == 3_500_000.0

    # Total loss = 0.25 * ($382,500 + $3,500,000) = 0.25 * $3,882,500 = $970,625
    expected_loss = 0.25 * (382_500.0 + 3_500_000.0)
    assert math.isclose(res.expected_7d_tail_loss_usd, expected_loss, rel_tol=1e-6)

    # Fair AP in bps: ($970,625 / $85,000,000) * 10,000 = 114.19 bps
    expected_ap = (expected_loss / vessel_usd) * 10_000.0
    assert math.isclose(res.actuarial_7d_war_risk_ap_bps, expected_ap, rel_tol=1e-6)

    # Spread vs 15.0 bps benchmark
    assert math.isclose(res.mispricing_spread_bps, expected_ap - 15.0, rel_tol=1e-6)


def test_jwc_zero_probability_zero_loading():
    """Zero breach probability must yield zero actuarial AP."""
    res = compute_jwc_7day_war_risk_ap(
        calibrated_7d_breach_prob=0.0,
        composite_cvar_99=8.0,
    )
    assert res.expected_7d_tail_loss_usd == 0.0
    assert res.actuarial_7d_war_risk_ap_bps == 0.0
    assert res.mispricing_spread_bps == -15.0


def test_jwc_7day_war_risk_pricer_calibrated_institutional_band():
    """Verify calibrated single-vessel transit exposure lands AP in [18.0, 35.0] bps band."""
    res = compute_jwc_7day_war_risk_ap(
        calibrated_7d_breach_prob=0.25,
        composite_cvar_99=10.0,
        insured_vessel_usd=85_000_000.0,
        daily_demurrage_usd=45_000.0,
        catastrophic_boarding_loss_usd=3_500_000.0,
        jwc_market_benchmark_bps=15.0,
        vessel_transit_exposure_factor=0.25,
        hydro_boarding_feasibility=0.463,
    )

    # Effective probability: 0.25 * 0.25 * (0.5 + 0.5 * 0.463) = 0.0457
    assert 0.04 <= res.effective_vessel_breach_prob <= 0.05
    # Fair AP in institutional underwriting band [18.0, 35.0] bps
    assert 18.0 <= res.actuarial_7d_war_risk_ap_bps <= 35.0
    # Mispricing spread over 15.0 bps commercial market quote
    assert res.mispricing_spread_bps > 0.0


# ==============================================================================
# 5. Wald's SPRT Surveillance Gates Tests
# ==============================================================================

def test_sprt_surveillance_gates_states():
    """Verify SPRT correctly discriminates baseline from escalation breach."""
    # Sustained baseline (zeros): must reach GREEN_BASELINE
    benign_series = [0] * 25
    res_green = evaluate_sprt_surveillance_gate(benign_series, p0=0.05, p1=0.20)
    assert res_green.state == "GREEN_BASELINE"
    assert res_green.cumulative_llr <= res_green.lower_bound_a

    # Active surge wave (consecutive ones): must trigger RED_ESCALATION_BREACH
    surge_series = [1] * 5
    res_red = evaluate_sprt_surveillance_gate(surge_series, p0=0.05, p1=0.20)
    assert res_red.state == "RED_ESCALATION_BREACH"
    assert res_red.cumulative_llr >= res_red.upper_bound_b

    # Ambiguous intermediate: AMBER_CORRIDOR_WATCH
    res_amber = evaluate_sprt_surveillance_gate([1, 0, 0, 1, 0], p0=0.05, p1=0.20)
    assert res_amber.state == "AMBER_CORRIDOR_WATCH"


# ==============================================================================
# 6. Audit Manifest Generation Tests
# ==============================================================================

def test_audit_manifest_builder(tmp_path: Path):
    """Verify AuditManifestBuilder generates valid schema and hashes."""
    builder = AuditManifestBuilder(tmp_path)

    # Create dummy dataset files
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    inc_file = data_dir / "sample_gog_osint_vintage.csv"
    inc_file.write_text("incident_id,event_time\nTEST-1,1000\n", encoding="utf-8")

    manifest = builder.generate_manifest(
        incident_dataset_rel_path="data/sample_gog_osint_vintage.csv",
        telemetry_dataset_rel_path="data/sample_gog_osint_vintage.csv",
    )

    assert manifest["schema_version"] == "2.0.0"
    assert manifest["corridor_id"] == "GOG_BONNY_BRASS_FAIRWAY"
    assert len(manifest["lineage_hashes"]["incident_dataset_sha256"]) == 64
    assert manifest["civilian_osint_hard_firewall"]["certified_civilian_only"] is True


# ==============================================================================
# 7. Hypothesis Fuzzing
# ==============================================================================

@settings(max_examples=50)
@given(
    hs=st.floats(min_value=0.0, max_value=15.0),
    wind=st.floats(min_value=0.0, max_value=60.0),
    sar_ratio=st.floats(min_value=0.0, max_value=1.0),
)
def test_hypothesis_fuzz_hydrodynamics(hs: float, wind: float, sar_ratio: float):
    """Fuzz hydrodynamic swamping and hazard calculations."""
    feasibility = skiff_boarding_feasibility(hs, wind_knots=wind)
    assert 0.0 <= feasibility <= 1.0

    hazard = composite_dark_vessel_hazard(hs, sar_ratio, wind_knots=wind)
    assert 0.0 <= hazard <= 10.0


@settings(max_examples=40)
@given(
    values=st.lists(st.floats(min_value=0.01, max_value=50.0), min_size=3, max_size=20),
)
def test_hypothesis_fuzz_shrink_gpd_parameters(values: list[float]):
    """Fuzz Empirical Bayes parameter shrinkage against arbitrary positive exceedances."""
    xi_shrunk, sigma_shrunk, w = shrink_gpd_parameters(values)
    assert not math.isnan(xi_shrunk)
    assert not math.isnan(sigma_shrunk)
    assert -0.5 <= xi_shrunk <= 0.95
    assert sigma_shrunk > 0.0
    assert 0.0 <= w <= 1.0
