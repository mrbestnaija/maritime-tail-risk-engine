"""Adversarial stress-testing suite for Regime Multiplier & Operational State Hazard Routing.

Milestones M1-M4 Challenger 2 Empirical Test Harness.
Verifies mathematical invariants, boundary conditions, edge cases, and routing fidelity.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# Bootstrap sys.path for standalone execution
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pytest
from hypothesis import given, strategies as st

from maritime_risk.core.regime_switch import compute_regime_multiplier
from maritime_risk.core.specs import (
    CorridorSpec,
    CoxHazardSpec,
    MacroRegimeSpec,
    VesselProfileSpec,
    load_corridor_spec,
    load_engine_bundle,
)
from maritime_risk.core.jwc_pricer import (
    compute_cox_7day_breach_probability,
    compute_jwc_7day_war_risk_ap,
    price_cox_7day_war_risk_ap,
)


# ============================================================================
# PART 1: REGIME MULTIPLIER TESTS
# ============================================================================

def test_regime_multiplier_zero_wait():
    """Verify current wait = 0.0 yields exactly 1.0 (no negative discount)."""
    spec = MacroRegimeSpec(
        baseline_port_wait_hours=24.0,
        congestion_shock_alpha=0.50,
        max_regime_multiplier=2.0,
    )
    result = compute_regime_multiplier(0.0, spec=spec)
    assert result == 1.0, f"Expected 1.0, got {result}"
    assert type(result) is float


@pytest.mark.parametrize("wait_hours", [0.0001, 1.0, 12.0, 18.0, 23.999, 24.0])
def test_regime_multiplier_sub_and_equal_baseline(wait_hours: float):
    """Verify current wait <= baseline yields exactly 1.0 with no modification."""
    spec = MacroRegimeSpec(
        baseline_port_wait_hours=24.0,
        congestion_shock_alpha=0.50,
        max_regime_multiplier=2.0,
    )
    result = compute_regime_multiplier(wait_hours, spec=spec)
    assert result == 1.0, f"Wait {wait_hours}h yielded {result}, expected 1.0"


def test_regime_multiplier_double_baseline():
    """Verify current wait = 48h (2x baseline) yields 1.5.

    Formula: 1.0 + min(2.0 - 1.0, 0.50 * ((48 - 24) / 24)) = 1.0 + min(1.0, 0.50 * 1.0) = 1.5
    """
    spec = MacroRegimeSpec(
        baseline_port_wait_hours=24.0,
        congestion_shock_alpha=0.50,
        max_regime_multiplier=2.0,
    )
    result = compute_regime_multiplier(48.0, spec=spec)
    assert result == pytest.approx(1.5, abs=1e-9)


@pytest.mark.parametrize("wait_hours", [72.0, 100.0, 500.0, 1000.0, 10_000.0, 1_000_000.0])
def test_regime_multiplier_saturation_cap(wait_hours: float):
    """Verify multiplier strictly saturates at max_regime_multiplier = 2.0 under huge shocks."""
    spec = MacroRegimeSpec(
        baseline_port_wait_hours=24.0,
        congestion_shock_alpha=0.50,
        max_regime_multiplier=2.0,
    )
    result = compute_regime_multiplier(wait_hours, spec=spec)
    assert result == pytest.approx(2.0, abs=1e-9)
    assert result <= spec.max_regime_multiplier, f"Exceeded max multiplier: {result} > 2.0"


@pytest.mark.parametrize("neg_wait", [-0.0001, -1.0, -24.0, -100.0, -1e6])
def test_regime_multiplier_negative_wait_hours(neg_wait: float):
    """Verify negative wait hours never discount below 1.0."""
    result = compute_regime_multiplier(neg_wait)
    assert result == 1.0, f"Negative wait {neg_wait} yielded discount: {result}"


def test_regime_multiplier_nan_and_none():
    """Verify NaN and None inputs return safe 1.0 neutral multiplier without exception."""
    assert compute_regime_multiplier(float("nan")) == 1.0
    assert compute_regime_multiplier(None) == 1.0  # type: ignore


def test_regime_multiplier_infinities():
    """Verify positive infinity saturates at max_regime_multiplier, negative infinity returns 1.0."""
    spec = MacroRegimeSpec(
        baseline_port_wait_hours=24.0,
        congestion_shock_alpha=0.50,
        max_regime_multiplier=2.0,
    )
    pos_inf = compute_regime_multiplier(float("inf"), spec=spec)
    assert pos_inf == 2.0
    assert not math.isinf(pos_inf)

    neg_inf = compute_regime_multiplier(float("-inf"), spec=spec)
    assert neg_inf == 1.0


def test_regime_multiplier_invalid_and_degenerate_specs():
    """Verify invalid or boundary spec hyperparameters fail gracefully to 1.0."""
    # Zero baseline wait
    spec_zero_baseline = MacroRegimeSpec(baseline_port_wait_hours=0.0)
    assert compute_regime_multiplier(48.0, spec=spec_zero_baseline) == 1.0

    # Negative baseline wait
    spec_neg_baseline = MacroRegimeSpec(baseline_port_wait_hours=-10.0)
    assert compute_regime_multiplier(48.0, spec=spec_neg_baseline) == 1.0

    # Zero alpha (no sensitivity)
    spec_zero_alpha = MacroRegimeSpec(congestion_shock_alpha=0.0)
    assert compute_regime_multiplier(100.0, spec=spec_zero_alpha) == 1.0

    # Max multiplier equal to 1.0
    spec_flat_max = MacroRegimeSpec(max_regime_multiplier=1.0)
    assert compute_regime_multiplier(100.0, spec=spec_flat_max) == 1.0

    # Max multiplier < 1.0 (pathological)
    spec_sub_max = MacroRegimeSpec(max_regime_multiplier=0.5)
    assert compute_regime_multiplier(100.0, spec=spec_sub_max) == 1.0

    # Default spec when None provided
    assert compute_regime_multiplier(48.0, spec=None) == 1.5


@given(
    wait_hours=st.floats(min_value=-1000.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_fuzz_regime_multiplier_boundedness(wait_hours: float):
    """Property test proving multiplier is always bounded in [1.0, max_regime_multiplier]."""
    spec = MacroRegimeSpec(
        baseline_port_wait_hours=24.0,
        congestion_shock_alpha=0.50,
        max_regime_multiplier=2.0,
    )
    result = compute_regime_multiplier(wait_hours, spec=spec)
    assert 1.0 <= result <= 2.0, f"Boundedness violation: {result} for wait {wait_hours}"


def test_regime_multiplier_monotonic_growth():
    """Verify strictly non-decreasing monotonicity across entire domain."""
    spec = MacroRegimeSpec(baseline_port_wait_hours=24.0, congestion_shock_alpha=0.50, max_regime_multiplier=2.0)
    test_points = [-10.0, 0.0, 12.0, 24.0, 30.0, 36.0, 48.0, 60.0, 72.0, 80.0, 100.0, 1000.0]
    multipliers = [compute_regime_multiplier(p, spec=spec) for p in test_points]

    for i in range(len(multipliers) - 1):
        assert multipliers[i] <= multipliers[i + 1], (
            f"Monotonicity violated: {multipliers[i]} > {multipliers[i+1]} "
            f"at points {test_points[i]} -> {test_points[i+1]}"
        )

    # Strictly increasing in congestion zone (24h, 72h)
    assert multipliers[3] < multipliers[4] < multipliers[5] < multipliers[6] < multipliers[7] < multipliers[8]


# ============================================================================
# PART 2: OPERATIONAL STATE HAZARD ROUTING TESTS
# ============================================================================

def test_cox_hazard_spec_declared_baselines():
    """Verify CoxHazardSpec contains required separate baselines with exact values."""
    spec = CoxHazardSpec()
    assert spec.baseline_hazard_underway == 0.0005, f"Underway baseline mismatch: {spec.baseline_hazard_underway}"
    assert spec.baseline_hazard_anchor == 0.0002, f"Anchor baseline mismatch: {spec.baseline_hazard_anchor}"
    assert spec.baseline_daily_hazard == 0.0005, f"Legacy baseline mismatch: {spec.baseline_daily_hazard}"


def test_operational_state_routing_exact_baseline():
    """Verify compute_cox_7day_breach_probability routes baseline hazard according to operational_state."""
    cox_spec = CoxHazardSpec(
        baseline_hazard_underway=0.0005,
        baseline_hazard_anchor=0.0002,
    )
    corridor_anchor = CorridorSpec(operational_state="AT_ANCHOR")
    corridor_underway = CorridorSpec(operational_state="UNDERWAY")

    # When all risk factors are 0, exponent = 0.0 and daily hazard = baseline * exp(0) = baseline
    p_anchor, hazard_anchor, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=0.0,
        distance_pmsc_km=0.0,
        wave_height_m=0.0,
        cox_spec=cox_spec,
        corridor_spec=corridor_anchor,
    )
    p_underway, hazard_underway, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=0.0,
        distance_pmsc_km=0.0,
        wave_height_m=0.0,
        cox_spec=cox_spec,
        corridor_spec=corridor_underway,
    )

    # Note: wave_height_m=0 produces skiff feasibility > 0, so exponent != 0,
    # but the ratio of hazard_anchor / hazard_underway MUST be exactly 0.0002 / 0.0005 = 0.4000
    ratio = hazard_anchor / hazard_underway
    assert ratio == pytest.approx(0.40, abs=1e-9), f"Hazard ratio was {ratio}, expected 0.40"
    assert hazard_anchor < hazard_underway
    assert p_anchor < p_underway


def test_anchored_vessel_prices_lower_all_else_equal():
    """Verify that holding all risk, environmental, vessel, and CVaR factors equal,

    an anchored vessel strictly prices at a lower hazard rate and lower AP than an underway vessel.
    """
    vessel = VesselProfileSpec()
    cox = CoxHazardSpec()
    corridor_anchor = CorridorSpec(operational_state="AT_ANCHOR")
    corridor_underway = CorridorSpec(operational_state="UNDERWAY")

    # Run across a grid of risk levels (low, medium, high)
    test_scenarios = [
        {"mli": 0.10, "dist": 200.0, "wave": 0.8, "cvar": 5.0},
        {"mli": 0.35, "dist": 150.0, "wave": 1.2, "cvar": 15.0},
        {"mli": 0.70, "dist": 50.0, "wave": 2.0, "cvar": 30.0},
    ]

    for s in test_scenarios:
        res_anchor = price_cox_7day_war_risk_ap(
            mothership_loitering_idx=s["mli"],
            distance_pmsc_km=s["dist"],
            wave_height_m=s["wave"],
            composite_cvar_99=s["cvar"],
            vessel_spec=vessel,
            corridor_spec=corridor_anchor,
            cox_spec=cox,
            regime_multiplier=1.0,
        )
        res_underway = price_cox_7day_war_risk_ap(
            mothership_loitering_idx=s["mli"],
            distance_pmsc_km=s["dist"],
            wave_height_m=s["wave"],
            composite_cvar_99=s["cvar"],
            vessel_spec=vessel,
            corridor_spec=corridor_underway,
            cox_spec=cox,
            regime_multiplier=1.0,
        )

        assert res_anchor.daily_hazard_rate < res_underway.daily_hazard_rate, (
            f"Anchor hazard ({res_anchor.daily_hazard_rate}) not lower than underway ({res_underway.daily_hazard_rate})"
        )
        assert res_anchor.calibrated_7d_breach_prob < res_underway.calibrated_7d_breach_prob, (
            f"Anchor breach prob ({res_anchor.calibrated_7d_breach_prob}) not lower than underway"
        )
        assert res_anchor.expected_7d_tail_loss_usd < res_underway.expected_7d_tail_loss_usd, (
            f"Anchor expected loss ({res_anchor.expected_7d_tail_loss_usd}) not lower than underway"
        )
        if res_underway.actuarial_7d_war_risk_ap_bps > cox.commercial_baseline_bps:
            assert res_anchor.actuarial_7d_war_risk_ap_bps < res_underway.actuarial_7d_war_risk_ap_bps, (
                f"Anchor AP ({res_anchor.actuarial_7d_war_risk_ap_bps} bps) not lower than underway ({res_underway.actuarial_7d_war_risk_ap_bps} bps)"
            )
        else:
            assert res_anchor.actuarial_7d_war_risk_ap_bps <= res_underway.actuarial_7d_war_risk_ap_bps

        # Expected ratio check on daily hazard
        hazard_ratio = res_anchor.daily_hazard_rate / res_underway.daily_hazard_rate
        assert hazard_ratio == pytest.approx(0.40, abs=1e-9)


@pytest.mark.parametrize("casing", ["at_anchor", "AT_ANCHOR", "At_Anchor", "aT_aNcHoR"])
def test_operational_state_case_insensitivity(casing: str):
    """Verify operational_state matching is case-insensitive."""
    corridor = CorridorSpec(operational_state=casing)
    _, hazard, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=0.2,
        distance_pmsc_km=100.0,
        wave_height_m=1.0,
        corridor_spec=corridor,
    )
    corridor_canonical = CorridorSpec(operational_state="AT_ANCHOR")
    _, hazard_canon, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=0.2,
        distance_pmsc_km=100.0,
        wave_height_m=1.0,
        corridor_spec=corridor_canonical,
    )
    assert hazard == hazard_canon


@pytest.mark.parametrize("fallback_state", [None, "", "UNKNOWN", "DRIFTING", "MOORED"])
def test_operational_state_fallback_to_underway(fallback_state: str | None):
    """Verify unrecognised or empty operational_state safely defaults to UNDERWAY hazard."""
    corridor_fallback = CorridorSpec(operational_state=fallback_state or "UNDERWAY")
    _, hazard_fallback, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=0.2,
        distance_pmsc_km=100.0,
        wave_height_m=1.0,
        corridor_spec=corridor_fallback,
    )
    corridor_underway = CorridorSpec(operational_state="UNDERWAY")
    _, hazard_underway, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=0.2,
        distance_pmsc_km=100.0,
        wave_height_m=1.0,
        corridor_spec=corridor_underway,
    )
    assert hazard_fallback == hazard_underway


# ============================================================================
# PART 3: CONFIGURATION AND BUNDLE INTEGRITY
# ============================================================================

def test_declarative_config_operational_states():
    """Verify declarative corridors.json flags Lagos SAA as AT_ANCHOR and transit corridors as UNDERWAY."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    for cfg_dir in [repo_root / "configs", repo_root / "maritime_risk" / "configs"]:
        corridors_file = cfg_dir / "corridors.json"
        assert corridors_file.exists(), f"Missing config: {corridors_file}"
        data = json.loads(corridors_file.read_text(encoding="utf-8"))
        corridors = data.get("corridors", data)

        assert corridors["GOG_LAGOS_SAA_ANCHORAGE"]["operational_state"] == "AT_ANCHOR"
        assert corridors["GOG_BONNY_BRASS_FAIRWAY"]["operational_state"] == "UNDERWAY"
        assert corridors["GOG_ESCRAVOS_FORCADOS_APPROACH"]["operational_state"] == "UNDERWAY"


def test_declarative_hyperparams_macro_regime_and_cox():
    """Verify model_hyperparams.json contains macro_regime and cox_hazard baseline configurations."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    for cfg_dir in [repo_root / "configs", repo_root / "maritime_risk" / "configs"]:
        hyper_file = cfg_dir / "model_hyperparams.json"
        assert hyper_file.exists(), f"Missing config: {hyper_file}"
        data = json.loads(hyper_file.read_text(encoding="utf-8"))

        # Cox hazard baselines
        cox = data["cox_hazard"]
        assert cox["baseline_hazard_underway"] == 0.0005
        assert cox["baseline_hazard_anchor"] == 0.0002

        # Macro regime specs
        macro = data["macro_regime"]
        assert macro["baseline_port_wait_hours"] == 24.0
        assert macro["congestion_shock_alpha"] == 0.50
        assert macro["max_regime_multiplier"] == 2.0


# ============================================================================
# STANDALONE EXECUTION RUNNER
# ============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 80)
    print("CHALLENGER 2: EMPIRICAL REGIME MULTIPLIER & HAZARD ROUTING SUITE")
    print("=" * 80)

    # 1. Zero wait
    r_zero = compute_regime_multiplier(0.0)
    print(f"[TEST 1] Wait = 0.0h -> Multiplier = {r_zero:.4f} (Expected: 1.0000)")
    assert r_zero == 1.0

    # 2. Sub-baseline wait
    r_12 = compute_regime_multiplier(12.0)
    r_24 = compute_regime_multiplier(24.0)
    print(f"[TEST 2] Wait = 12.0h -> Multiplier = {r_12:.4f}; Wait = 24.0h -> Multiplier = {r_24:.4f}")
    assert r_12 == 1.0 and r_24 == 1.0

    # 3. Double baseline wait (48h)
    r_48 = compute_regime_multiplier(48.0)
    print(f"[TEST 3] Wait = 48.0h -> Multiplier = {r_48:.4f} (Expected: 1.5000)")
    assert r_48 == 1.5

    # 4. Saturation at 1000h
    r_1000 = compute_regime_multiplier(1000.0)
    print(f"[TEST 4] Wait = 1000.0h -> Multiplier = {r_1000:.4f} (Expected: 2.0000 saturation)")
    assert r_1000 == 2.0

    # 5. Negative wait
    r_neg = compute_regime_multiplier(-15.0)
    print(f"[TEST 5] Wait = -15.0h -> Multiplier = {r_neg:.4f} (Expected: 1.0000 no discount)")
    assert r_neg == 1.0

    # 6. NaN and Infinity
    r_nan = compute_regime_multiplier(float("nan"))
    r_inf = compute_regime_multiplier(float("inf"))
    print(f"[TEST 6] Wait = NaN -> Multiplier = {r_nan:.4f}; Wait = +inf -> Multiplier = {r_inf:.4f}")
    assert r_nan == 1.0 and r_inf == 2.0

    # 7. Operational state baselines
    cox_spec = CoxHazardSpec()
    print(f"[TEST 7] CoxHazardSpec: anchor = {cox_spec.baseline_hazard_anchor:.6f}, underway = {cox_spec.baseline_hazard_underway:.6f}")
    assert cox_spec.baseline_hazard_anchor == 0.0002
    assert cox_spec.baseline_hazard_underway == 0.0005

    # 8. Hazard routing
    corridor_anchor = CorridorSpec(operational_state="AT_ANCHOR")
    corridor_underway = CorridorSpec(operational_state="UNDERWAY")
    _, h_anchor, _ = compute_cox_7day_breach_probability(0.25, 180.0, 1.2, corridor_spec=corridor_anchor)
    _, h_underway, _ = compute_cox_7day_breach_probability(0.25, 180.0, 1.2, corridor_spec=corridor_underway)
    ratio = h_anchor / h_underway
    print(f"[TEST 8] Daily hazard: anchor = {h_anchor:.6f}, underway = {h_underway:.6f}, ratio = {ratio:.4f}")
    assert ratio == pytest.approx(0.40, abs=1e-6)

    # 9. All-else-equal JWC pricing
    ap_anchor = price_cox_7day_war_risk_ap(0.25, 180.0, 1.2, 10.0, corridor_spec=corridor_anchor)
    ap_underway = price_cox_7day_war_risk_ap(0.25, 180.0, 1.2, 10.0, corridor_spec=corridor_underway)
    print(f"[TEST 9] Pricing comparison (CVaR=10.0):")
    print(f"         Anchor:   P_breach = {ap_anchor.calibrated_7d_breach_prob:.6f}, AP = {ap_anchor.actuarial_7d_war_risk_ap_bps:.4f} bps")
    print(f"         Underway: P_breach = {ap_underway.calibrated_7d_breach_prob:.6f}, AP = {ap_underway.actuarial_7d_war_risk_ap_bps:.4f} bps")
    assert ap_anchor.actuarial_7d_war_risk_ap_bps < ap_underway.actuarial_7d_war_risk_ap_bps

    print("=" * 80)
    print("ALL EMPIRICAL CHALLENGER ASSERTIONS PASSED")
    print("=" * 80)
