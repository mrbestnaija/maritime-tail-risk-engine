"""Deterministic Verification Suite for Tactical Hardening Arbitrage.

Phase 2 Actuarial & Naval Operational Invariants:
1. Kinetic Suppression Ordering:
   UNDERWAY_LONE > AT_ANCHOR_UNPROTECTED > UNDERWAY_ESCORTED > AT_ANCHOR_SECURED.
2. Positive Arbitrage:
   In elevated threat regimes (high MLI, high port wait), dividend_net_usd > 0
   (naval escort pays for itself via gross AP savings > escort OPEX).
3. Monsoonal Swamping (Avoided Security Waste):
   When H_s > 1.85m (Sea State 6), small-skiff boarding feasibility decays exponentially,
   yielding dividend_net_usd < 0 (hiring escorts in heavy seas is wasted OPEX).
4. Underwriter Solvency II Capital Reserve Relief:
   delta_reserve_usd = (p_lone - p_escorted) * composite_cvar_99_usd > 0.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest

from maritime_risk.core.specs import (
    CorridorSpec,
    CoxHazardSpec,
    HydroEnvelopeSpec,
    VesselProfileSpec,
    VALID_OPERATIONAL_STATES,
)
from maritime_risk.core.jwc_pricer import (
    compute_cox_7day_breach_probability,
    compute_tactical_hardening_dividend,
    price_cox_7day_war_risk_ap,
    JWCPricingResult,
)
from maritime_risk.application.engine import MaritimeRiskEngine


def test_operational_state_taxonomy_declared():
    """Verify operational state taxonomy is exposed and contains all 4 standard postures."""
    required_states = {
        "UNDERWAY",
        "UNDERWAY_LONE",
        "UNDERWAY_ESCORTED",
        "AT_ANCHOR",
        "AT_ANCHOR_SECURED",
        "AT_ANCHOR_UNPROTECTED",
    }
    assert required_states.issubset(set(VALID_OPERATIONAL_STATES))


def test_cox_hazard_spec_declarative_baselines():
    """Verify CoxHazardSpec contains all required baselines without hardcoded math literals."""
    cox = CoxHazardSpec()
    assert cox.baseline_hazard_underway == 0.0005
    assert cox.baseline_hazard_escorted == 0.00015
    assert cox.baseline_hazard_anchor == 0.0002
    assert cox.baseline_hazard_anchor_secured == 0.00010
    assert cox.baseline_hazard_anchor_unprotected == 0.00045
    assert cox.escort_hazard_suppression_ratio == pytest.approx(0.30, abs=1e-6)

    # Mathematical ratio check
    ratio_escorted = cox.baseline_hazard_escorted / cox.baseline_hazard_underway
    assert ratio_escorted == pytest.approx(cox.escort_hazard_suppression_ratio, abs=1e-6)


def test_kinetic_suppression_ordering_across_threat_spectrum():
    """Requirement 3.1: Given identical threat vectors, AP must strictly order as:

    UNDERWAY_LONE > AT_ANCHOR_UNPROTECTED > UNDERWAY_ESCORTED > AT_ANCHOR_SECURED.
    """
    vessel = VesselProfileSpec()
    cox = CoxHazardSpec()

    corridor_lone = CorridorSpec(operational_state="UNDERWAY_LONE")
    corridor_unprotected = CorridorSpec(operational_state="AT_ANCHOR_UNPROTECTED")
    corridor_escorted = CorridorSpec(operational_state="UNDERWAY_ESCORTED")
    corridor_secured = CorridorSpec(operational_state="AT_ANCHOR_SECURED")

    # Evaluate across moderate and elevated threat spectrum where raw AP exceeds statutory floor
    threat_grid = [
        {"mli": 0.35, "dist": 60.0, "wave": 0.9, "cvar": 22.0, "reg_mult": 1.2},
        {"mli": 0.55, "dist": 40.0, "wave": 1.1, "cvar": 28.0, "reg_mult": 1.5},
        {"mli": 0.85, "dist": 20.0, "wave": 1.3, "cvar": 35.0, "reg_mult": 1.8},
    ]

    for tg in threat_grid:
        res_lone = price_cox_7day_war_risk_ap(
            mothership_loitering_idx=tg["mli"],
            distance_pmsc_km=tg["dist"],
            wave_height_m=tg["wave"],
            composite_cvar_99=tg["cvar"],
            vessel_spec=vessel,
            corridor_spec=corridor_lone,
            cox_spec=cox,
            regime_multiplier=tg["reg_mult"],
        )
        res_unprotected = price_cox_7day_war_risk_ap(
            mothership_loitering_idx=tg["mli"],
            distance_pmsc_km=tg["dist"],
            wave_height_m=tg["wave"],
            composite_cvar_99=tg["cvar"],
            vessel_spec=vessel,
            corridor_spec=corridor_unprotected,
            cox_spec=cox,
            regime_multiplier=tg["reg_mult"],
        )
        res_escorted = price_cox_7day_war_risk_ap(
            mothership_loitering_idx=tg["mli"],
            distance_pmsc_km=tg["dist"],
            wave_height_m=tg["wave"],
            composite_cvar_99=tg["cvar"],
            vessel_spec=vessel,
            corridor_spec=corridor_escorted,
            cox_spec=cox,
            regime_multiplier=tg["reg_mult"],
        )
        res_secured = price_cox_7day_war_risk_ap(
            mothership_loitering_idx=tg["mli"],
            distance_pmsc_km=tg["dist"],
            wave_height_m=tg["wave"],
            composite_cvar_99=tg["cvar"],
            vessel_spec=vessel,
            corridor_spec=corridor_secured,
            cox_spec=cox,
            regime_multiplier=tg["reg_mult"],
        )

        # 1. Daily hazard rate ordering
        assert (
            res_lone.daily_hazard_rate
            > res_unprotected.daily_hazard_rate
            > res_escorted.daily_hazard_rate
            > res_secured.daily_hazard_rate
        ), (
            f"Hazard ordering failed: lone={res_lone.daily_hazard_rate}, "
            f"unprotected={res_unprotected.daily_hazard_rate}, "
            f"escorted={res_escorted.daily_hazard_rate}, secured={res_secured.daily_hazard_rate}"
        )

        # 2. Cumulative 7-day breach probability ordering
        assert (
            res_lone.calibrated_7d_breach_prob
            > res_unprotected.calibrated_7d_breach_prob
            > res_escorted.calibrated_7d_breach_prob
            > res_secured.calibrated_7d_breach_prob
        )

        # 3. Expected tail loss ordering
        assert (
            res_lone.expected_7d_tail_loss_usd
            > res_unprotected.expected_7d_tail_loss_usd
            > res_escorted.expected_7d_tail_loss_usd
            > res_secured.expected_7d_tail_loss_usd
        )

        # 4. Fair Actuarial AP Rate ordering
        assert (
            res_lone.actuarial_7d_war_risk_ap_bps
            > res_unprotected.actuarial_7d_war_risk_ap_bps
            > res_escorted.actuarial_7d_war_risk_ap_bps
            > res_secured.actuarial_7d_war_risk_ap_bps
        ), (
            f"AP ordering failed: lone={res_lone.actuarial_7d_war_risk_ap_bps}, "
            f"unprotected={res_unprotected.actuarial_7d_war_risk_ap_bps}, "
            f"escorted={res_escorted.actuarial_7d_war_risk_ap_bps}, "
            f"secured={res_secured.actuarial_7d_war_risk_ap_bps}"
        )


def test_positive_arbitrage_in_high_threat_regime():
    """Requirement 3.2: In a high-threat regime (high MLI, high port wait),

    dividend_net_usd must be positive (the escort pays for itself in insurance savings).
    """
    vessel = VesselProfileSpec()
    cox = CoxHazardSpec()
    corridor = CorridorSpec(operational_state="UNDERWAY_LONE")

    # High-threat tactical shock: MLI = 0.85, close distance, calm water (high feasibility),
    # severe port congestion regime multiplier = 1.8x
    dividend = compute_tactical_hardening_dividend(
        mothership_loitering_idx=0.85,
        distance_pmsc_km=25.0,
        wave_height_m=0.8,
        composite_cvar_99=32.0,
        vessel_spec=vessel,
        corridor_spec=corridor,
        cox_spec=cox,
        regime_multiplier=1.80,
    )

    # 1. Gross AP savings must be substantial
    assert dividend["delta_ap_usd"] > 0.0
    assert dividend["ap_lone_usd"] > dividend["ap_escorted_usd"]

    # 2. Escort cost is 7 days * 18,500 = 129,500 USD
    assert dividend["escort_opex_cost_usd"] == pytest.approx(129_500.0, abs=1e-2)

    # 3. Positive Arbitrage: Net dividend must strictly exceed 0
    assert dividend["dividend_net_usd"] > 0.0, (
        f"Expected positive dividend in high threat, got {dividend['dividend_net_usd']}"
    )

    # 4. Underwriter Capital Relief must be positive
    assert dividend["delta_reserve_usd"] > 0.0
    assert dividend["p_breach_lone"] > dividend["p_breach_escorted"]

    # 5. Pricing result embeds identical metrics
    pricing_res = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=0.85,
        distance_pmsc_km=25.0,
        wave_height_m=0.8,
        composite_cvar_99=32.0,
        vessel_spec=vessel,
        corridor_spec=corridor,
        cox_spec=cox,
        regime_multiplier=1.80,
    )
    assert pricing_res.dividend_net_usd == pytest.approx(dividend["dividend_net_usd"], abs=1e-4)
    assert pricing_res.delta_ap_usd == pytest.approx(dividend["delta_ap_usd"], abs=1e-4)
    assert pricing_res.delta_reserve_usd == pytest.approx(dividend["delta_reserve_usd"], abs=1e-4)


def test_monsoonal_swamping_avoided_security_waste():
    """Requirement 3.3: When H_s > 1.85m (Sea State 6), kinetic threat drops exponentially.

    Hiring an escort in Sea State 6 yields a negative dividend (wasted security spend).
    """
    vessel = VesselProfileSpec()
    cox = CoxHazardSpec()
    corridor = CorridorSpec(operational_state="UNDERWAY_LONE")

    # Sea State 6 monsoonal swamping: wave height = 3.2m >> 1.85m h_0
    dividend_heavy_sea = compute_tactical_hardening_dividend(
        mothership_loitering_idx=0.30,
        distance_pmsc_km=150.0,
        wave_height_m=3.2,
        composite_cvar_99=8.0,
        vessel_spec=vessel,
        corridor_spec=corridor,
        cox_spec=cox,
        regime_multiplier=1.0,
    )

    # Under severe wave swamping, skiff boarding is hydrodynamically impossible.
    # AP is floored or tiny, so hiring an escort at $18,500/day produces negative net dividend!
    assert dividend_heavy_sea["dividend_net_usd"] < 0.0, (
        f"Expected negative dividend in Sea State 6, got {dividend_heavy_sea['dividend_net_usd']}"
    )
    # The negative dividend should approximately equal the full wasted escort cost
    assert dividend_heavy_sea["dividend_net_usd"] <= -50_000.0


def test_underwriter_capital_reserve_relief_scaling():
    """Verify underwriter Solvency II capital reserve relief scales monotonically with CVaR."""
    vessel = VesselProfileSpec()
    cox = CoxHazardSpec()
    corridor = CorridorSpec()

    cvar_levels = [10.0, 20.0, 30.0, 40.0]
    reserve_reliefs = []

    for cv in cvar_levels:
        div = compute_tactical_hardening_dividend(
            mothership_loitering_idx=0.60,
            distance_pmsc_km=50.0,
            wave_height_m=1.2,
            composite_cvar_99=cv,
            vessel_spec=vessel,
            corridor_spec=corridor,
            cox_spec=cox,
        )
        reserve_reliefs.append(div["delta_reserve_usd"])

    # Must scale monotonically with CVaR conditional severity
    for i in range(len(reserve_reliefs) - 1):
        assert reserve_reliefs[i] < reserve_reliefs[i + 1], (
            f"Relief at {cvar_levels[i]} ({reserve_reliefs[i]}) not lower than at {cvar_levels[i+1]} ({reserve_reliefs[i+1]})"
        )


def test_jwc_pricing_result_to_dict_contract():
    """Verify JWCPricingResult.to_dict() provides all tactical dividend fields."""
    res = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=0.50,
        distance_pmsc_km=80.0,
        wave_height_m=1.1,
        composite_cvar_99=18.0,
    )
    d = res.to_dict()
    assert isinstance(d, dict)
    assert "delta_ap_usd" in d
    assert "dividend_net_usd" in d
    assert "delta_reserve_usd" in d
    assert "escort_opex_cost_usd" in d
    assert "ap_lone_usd" in d
    assert "ap_escorted_usd" in d
    assert "ap_lone_bps" in d
    assert "ap_escorted_bps" in d
    assert "operational_state" in d


def test_engine_evaluates_operational_states_end_to_end():
    """Verify MaritimeRiskEngine evaluates custom operational states and includes dividend."""
    for state in ["UNDERWAY_LONE", "UNDERWAY_ESCORTED", "AT_ANCHOR_SECURED", "AT_ANCHOR_UNPROTECTED"]:
        engine = MaritimeRiskEngine(
            corridor_spec=CorridorSpec(operational_state=state),
        )
        audit_res = engine.evaluate()
        assert audit_res.corridor_spec.operational_state == state
        assert hasattr(audit_res.jwc_result, "dividend_net_usd")
        assert hasattr(audit_res.jwc_result, "delta_reserve_usd")
        # Check generated markdown includes the tactical dividend table
        md = audit_res.to_markdown()
        assert "Table 4D: Tactical Hardening Arbitrage" in md
        assert "Lone Underway AP Rate" in md
        assert "Escorted Underway AP Rate" in md
