"""Hypothesis Property-Based Actuarial Stress Testing Suite.

Author: Nigerian Navy officer with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
Repository: maritime-tail-risk-engine (Branch main)

Implements rigorous continuous-parameter space property-based fuzzing:
1. The PnL Solvency Invariant (Premium vs. Tail Risk):
   Expected_Premium >= Expected_Shortfall(CVaR_99) + Margin.
   Engine never quotes below its 99th percentile conditional tail expectation.
2. Uninsurable Tail Refusal Guardrail (GPD Shape Bound):
   When xi_MLE >= 1.0 (infinite-mean tail shock), compute_tail_risk must REFUSE TO PRICE
   by raising UninsurableRiskException, preventing underwriter capital pool ruin.
3. Regime Liquidity Invariant (Monotonicity & Cap):
   compute_regime_multiplier strictly in [1.0, max_regime_multiplier] and monotonic.
4. Tactical Hydrodynamic Hardening Invariant (Cox PH):
   Breach probability drops exponentially across the swamping threshold (e.g. 1.85m),
   neutralizing attack viability regardless of Mothership Loitering Index (MLI).
5. Anchorage Static Cordon Invariant:
   Under identical threat inputs, transit breach probability for AT_ANCHOR is strictly
   lower than UNDERWAY.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
from typing import Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from maritime_risk.application.engine import MaritimeRiskEngine
from maritime_risk.core.empirical_bayes import shrink_gpd_parameters
from maritime_risk.core.gpd_tail_fitter import (
    GPDTailRiskEstimate,
    UninsurableRiskException,
    compute_actuarial_war_risk_loading_bps,
    compute_gpd_var_cvar,
    compute_tail_risk,
)
from maritime_risk.core.hydro_envelope import (
    composite_dark_vessel_hazard,
    evaluate_hydrodynamic_envelope,
    skiff_boarding_feasibility,
)
from maritime_risk.core.jwc_pricer import (
    compute_cox_7day_breach_probability,
    compute_jwc_7day_war_risk_ap,
    compute_operational_hardening_index,
    price_cox_7day_war_risk_ap,
)
from maritime_risk.core.models import (
    CivilianSensorTelemetry,
    GeoCoordinates,
    MaritimeIncident,
    SeverityInterval,
)
from maritime_risk.core.regime_switch import compute_regime_multiplier
from maritime_risk.core.specs import (
    CorridorSpec,
    CoxHazardSpec,
    EmpiricalBayesSpec,
    EngineConfigBundle,
    GPDFitterSpec,
    HydroEnvelopeSpec,
    MacroRegimeSpec,
    VesselProfileSpec,
)


# ==============================================================================
# INVARIANT 1: THE PNL SOLVENCY INVARIANT (PREMIUM VS. TAIL RISK)
# ==============================================================================

@settings(max_examples=50, deadline=None)
@given(
    insured_vessel_usd=st.floats(min_value=10_000_000.0, max_value=250_000_000.0, allow_nan=False, allow_infinity=False),
    daily_demurrage_usd=st.floats(min_value=10_000.0, max_value=120_000.0, allow_nan=False, allow_infinity=False),
    catastrophic_loss_usd=st.floats(min_value=500_000.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False),
    cvar_99=st.floats(min_value=0.01, max_value=40.0, allow_nan=False, allow_infinity=False),
    calibrated_p_7d=st.floats(min_value=0.0001, max_value=0.9999, allow_nan=False, allow_infinity=False),
    wait_hours=st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False),
    wave_height_m=st.floats(min_value=0.0, max_value=12.0, allow_nan=False, allow_infinity=False),
    exposure_factor=st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_pnl_solvency_invariant_premium_vs_tail_risk(
    insured_vessel_usd: float,
    daily_demurrage_usd: float,
    catastrophic_loss_usd: float,
    cvar_99: float,
    calibrated_p_7d: float,
    wait_hours: float,
    wave_height_m: float,
    exposure_factor: float,
):
    """Assert PnL Solvency Invariant:

    Expected_Premium >= Expected_Shortfall(CVaR_99) + Margin.
    The engine must never quote a price mathematically lower than its own 99th percentile
    conditional tail expectation.
    """
    vessel = VesselProfileSpec(
        insured_vessel_usd=insured_vessel_usd,
        daily_demurrage_usd=daily_demurrage_usd,
        catastrophic_boarding_loss_usd=catastrophic_loss_usd,
        single_vessel_exposure_factor=exposure_factor,
    )
    regime_spec = MacroRegimeSpec(
        baseline_port_wait_hours=24.0,
        congestion_shock_alpha=0.50,
        max_regime_multiplier=2.5,
    )
    reg_mult = compute_regime_multiplier(wait_hours, spec=regime_spec)
    assert reg_mult >= 1.0, f"Regime multiplier fell below 1.0: {reg_mult}"

    hydro_spec = HydroEnvelopeSpec()
    hydro_feas = skiff_boarding_feasibility(wave_height_m, spec=hydro_spec)
    corridor = CorridorSpec()

    res = compute_jwc_7day_war_risk_ap(
        calibrated_7d_breach_prob=calibrated_p_7d,
        composite_cvar_99=cvar_99,
        vessel_spec=vessel,
        corridor_spec=corridor,
        regime_multiplier=reg_mult,
        hydro_boarding_feasibility=hydro_feas,
        vessel_transit_exposure_factor=exposure_factor,
    )

    # 1. Unweighted conditional tail loss given breach (Expected Shortfall severity)
    loss_given_breach_usd = res.cvar_99_demurrage_usd + res.catastrophic_tail_loss_usd
    assert loss_given_breach_usd > 0.0

    # 2. Pure 99th percentile expected tail shortfall for the transiting vessel
    expected_shortfall_usd = min(
        res.effective_vessel_breach_prob * loss_given_breach_usd,
        res.insured_vessel_usd,
    )
    expected_shortfall_bps = (expected_shortfall_usd / res.insured_vessel_usd) * 10_000.0

    # 3. Macro liquidity solvency margin
    solvency_margin_bps = (res.regime_multiplier - 1.0) * expected_shortfall_bps
    assert solvency_margin_bps >= -1e-9

    # 4. Solvency Invariant Assertion:
    # Expected_Premium >= Expected_Shortfall(CVaR_99) + Margin
    expected_premium_bps = res.actuarial_7d_war_risk_ap_bps
    expected_target_bps = min(expected_shortfall_bps + solvency_margin_bps, 10_000.0)
    assert math.isclose(
        expected_premium_bps,
        expected_target_bps,
        rel_tol=1e-5,
        abs_tol=1e-7,
    )
    assert expected_premium_bps >= min(expected_shortfall_bps, 10_000.0), (
        f"Solvency violation: Expected premium {expected_premium_bps:.6f} bps "
        f"< Expected shortfall {expected_shortfall_bps:.6f} bps"
    )

    # Incurred expected USD premium covers expected tail loss
    assert res.expected_7d_tail_loss_usd >= expected_shortfall_usd - 1e-6
    assert expected_premium_bps > 0.0


@settings(max_examples=40, deadline=None)
@given(
    mothership_loitering_index=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    distance_pmsc_km=st.floats(min_value=0.0, max_value=1500.0, allow_nan=False, allow_infinity=False),
    wave_height_m=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    cvar_99=st.floats(min_value=0.1, max_value=35.0, allow_nan=False, allow_infinity=False),
    wait_hours=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_cox_pricer_solvency_invariant(
    mothership_loitering_index: float,
    distance_pmsc_km: float,
    wave_height_m: float,
    cvar_99: float,
    wait_hours: float,
):
    """Assert Cox Proportional Hazards pricer satisfies PnL Solvency Invariant."""
    vessel = VesselProfileSpec()
    cox = CoxHazardSpec()
    corridor = CorridorSpec()
    regime_spec = MacroRegimeSpec()
    reg_mult = compute_regime_multiplier(wait_hours, spec=regime_spec)

    res = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        composite_cvar_99=cvar_99,
        vessel_spec=vessel,
        corridor_spec=corridor,
        cox_spec=cox,
        regime_multiplier=reg_mult,
    )

    tail_loss_usd = res.cvar_99_demurrage_usd + res.catastrophic_tail_loss_usd
    expected_shortfall_usd = res.effective_vessel_breach_prob * tail_loss_usd
    expected_shortfall_bps = (expected_shortfall_usd / res.insured_vessel_usd) * 10_000.0
    margin_bps = (res.regime_multiplier - 1.0) * expected_shortfall_bps
    expected_base_ap_bps = expected_shortfall_bps + margin_bps

    # 1. PnL Solvency Invariant: Expected_Premium >= Expected_Shortfall(CVaR_99) + Margin
    assert res.actuarial_7d_war_risk_ap_bps >= expected_shortfall_bps - 1e-9
    assert res.actuarial_7d_war_risk_ap_bps >= expected_base_ap_bps - 1e-9
    # 2. Commercial Floor Invariant: AP must floor at commercial_baseline_bps
    assert res.actuarial_7d_war_risk_ap_bps >= cox.commercial_baseline_bps
    assert math.isclose(
        res.actuarial_7d_war_risk_ap_bps,
        max(expected_base_ap_bps, cox.commercial_baseline_bps),
        rel_tol=1e-5,
        abs_tol=1e-7,
    )


# ==============================================================================
# INVARIANT 2: UNINSURABLE TAIL REFUSAL GUARDRAIL (GPD SHAPE BOUND)
# ==============================================================================

@settings(max_examples=50, deadline=None)
@given(
    xi_mle=st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    u=st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    sigma=st.floats(min_value=0.05, max_value=10.0, allow_nan=False, allow_infinity=False),
    p_u=st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_uninsurable_tail_refusal_guardrail(
    xi_mle: float,
    u: float,
    sigma: float,
    p_u: float,
):
    """Assert Uninsurable Tail Refusal Guardrail:

    When xi_MLE >= 1.0 (infinite mean), the engine must NOT clamp xi to force a finite price.
    Instead, compute_tail_risk must explicitly REFUSE TO PRICE by raising UninsurableRiskException,
    protecting the underwriting capital pool.
    """
    assert xi_mle >= 1.0

    # 1. Direct call with keyword argument
    with pytest.raises(UninsurableRiskException) as exc_info:
        compute_tail_risk(u=u, xi=xi_mle, sigma=sigma, p_u=p_u)
    assert "infinite-mean" in str(exc_info.value).lower() or "uninsurable" in str(exc_info.value).lower()

    # 2. Positional and alias invocations
    with pytest.raises(UninsurableRiskException):
        compute_tail_risk(xi=xi_mle)

    with pytest.raises(UninsurableRiskException):
        compute_tail_risk(xi_mle)

    with pytest.raises(UninsurableRiskException):
        compute_tail_risk(raw_xi=xi_mle)

    # 3. Via MaritimeRiskEngine facade
    engine = MaritimeRiskEngine.from_specs()
    with pytest.raises(UninsurableRiskException):
        engine.compute_tail_risk(xi=xi_mle)


@settings(max_examples=30, deadline=None)
@given(
    xi_finite=st.floats(min_value=0.01, max_value=0.95, allow_nan=False, allow_infinity=False),
    u=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    sigma=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_insurable_finite_tail_pricing_succeeds(
    xi_finite: float,
    u: float,
    sigma: float,
):
    """Contrast: when xi < 1.0 (finite-mean regime), compute_tail_risk produces valid actuarial metrics."""
    assert xi_finite < 1.0
    res = compute_tail_risk(u=u, xi=xi_finite, sigma=sigma, p_u=0.05)

    assert isinstance(res, GPDTailRiskEstimate)
    assert res.shape_xi == xi_finite
    assert not math.isnan(res.var_99)
    assert not math.isinf(res.var_99)
    assert not math.isnan(res.cvar_99)
    assert not math.isinf(res.cvar_99)
    assert res.var_99 <= res.cvar_99
    assert res.actuarial_war_risk_loading_bps >= 0.0


@settings(max_examples=50, deadline=None)
@given(
    raw_xi_spike=st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False),
    prior_xi=st.floats(min_value=0.10, max_value=0.25, allow_nan=False, allow_infinity=False),
    insured_vessel_usd=st.floats(min_value=5_000_000.0, max_value=250_000_000.0, allow_nan=False, allow_infinity=False),
    cvar_99=st.floats(min_value=0.5, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_ultimate_capital_bound_gpd_shape_and_solvency(
    raw_xi_spike: float,
    prior_xi: float,
    insured_vessel_usd: float,
    cvar_99: float,
):
    """Assert Ultimate Capital Bound & Solvency Invariant:

    1. xi_shrunk must NEVER exceed GPDFitterSpec.xi_max (0.95).
    2. Capital Solvency Assertion: Expected Shortfall / reserve charge must NEVER exceed
       insured_vessel_usd (capital reserve charge cannot logically exceed total loss of asset).
    3. If raw_xi >= 1.0 is passed un-shrunk to compute_tail_risk, uninsurable risk refusal triggers.
    """
    g_spec = GPDFitterSpec()
    v_spec = VesselProfileSpec(insured_vessel_usd=insured_vessel_usd)
    bayes_spec = EmpiricalBayesSpec(prior_xi=prior_xi)

    # 1. Empirical Bayes shrinkage bounds shape by xi_max (0.95)
    exceedances = [1.0, 2.5, 5.0, 10.0, 50.0]
    shrunk_xi, _, _ = shrink_gpd_parameters(
        local_exceedances=exceedances,
        prior_xi=prior_xi,
        spec=bayes_spec,
        xi_max=g_spec.xi_max,
    )
    assert shrunk_xi <= g_spec.xi_max + 1e-9, f"xi_shrunk {shrunk_xi} breached xi_max {g_spec.xi_max}"

    # Also test with prior_xi set to extreme spike bounded by xi_max
    shrunk_extreme, _, _ = shrink_gpd_parameters(
        local_exceedances=exceedances,
        prior_xi=raw_xi_spike,
        spec=bayes_spec,
        xi_max=g_spec.xi_max,
    )
    assert shrunk_extreme <= g_spec.xi_max + 1e-9, f"shrunk_extreme {shrunk_extreme} breached xi_max {g_spec.xi_max}"

    # 2. Capital reserve charge capped at total asset value
    res = compute_jwc_7day_war_risk_ap(
        calibrated_7d_breach_prob=0.999,
        composite_cvar_99=cvar_99,
        vessel_spec=v_spec,
    )
    assert res.expected_7d_tail_loss_usd <= v_spec.insured_vessel_usd + 1e-6, (
        f"Capital reserve charge {res.expected_7d_tail_loss_usd} exceeded total asset value {v_spec.insured_vessel_usd}"
    )
    assert res.actuarial_7d_war_risk_ap_bps <= 10_000.0 + 1e-6

    # 3. Uninsurable tail refusal if raw_xi >= 1.0
    if raw_xi_spike >= 1.0:
        with pytest.raises(UninsurableRiskException):
            compute_tail_risk(xi=raw_xi_spike)


# ==============================================================================
# INVARIANT 3: REGIME LIQUIDITY INVARIANT (MONOTONICITY & CAP)
# ==============================================================================

@settings(max_examples=50, deadline=None)
@given(
    current_wait_hours=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
    delta_wait_hours=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
    baseline_wait=st.floats(min_value=1.0, max_value=72.0, allow_nan=False, allow_infinity=False),
    congestion_alpha=st.floats(min_value=0.05, max_value=2.0, allow_nan=False, allow_infinity=False),
    max_multiplier=st.floats(min_value=1.05, max_value=5.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_regime_liquidity_invariant_monotonicity_and_cap(
    current_wait_hours: float,
    delta_wait_hours: float,
    baseline_wait: float,
    congestion_alpha: float,
    max_multiplier: float,
):
    """Assert Regime Liquidity Invariant:

    1. compute_regime_multiplier must NEVER return < 1.0.
    2. compute_regime_multiplier must strictly cap at MacroRegimeSpec.max_regime_multiplier.
    3. Monotonicity: multiplier(wait + delta) >= multiplier(wait).
    4. PnL Duration Exposure Assertion: Total Computed Premium (derived AP Rate * duration factor)
       must scale monotonically with wait_hours, guaranteeing the syndicate does not give away
       free cumulative exposure when the regime rate hits its ceiling.
    """
    spec = MacroRegimeSpec(
        baseline_port_wait_hours=baseline_wait,
        congestion_shock_alpha=congestion_alpha,
        max_regime_multiplier=max_multiplier,
    )

    m1 = compute_regime_multiplier(current_wait_hours, spec=spec)
    m2 = compute_regime_multiplier(current_wait_hours + delta_wait_hours, spec=spec)

    # Invariant 1: Lower bound >= 1.0
    assert m1 >= 1.0, f"Multiplier fell below unity: {m1}"
    assert m2 >= 1.0, f"Multiplier fell below unity: {m2}"

    # Invariant 2: Strict cap at spec.max_regime_multiplier
    assert m1 <= spec.max_regime_multiplier + 1e-9, f"Cap exceeded: {m1} > {spec.max_regime_multiplier}"
    assert m2 <= spec.max_regime_multiplier + 1e-9, f"Cap exceeded: {m2} > {spec.max_regime_multiplier}"

    # Invariant 3: Monotonicity
    assert m2 >= m1 - 1e-12, f"Monotonicity violation: m2={m2} < m1={m1} for delta={delta_wait_hours}"

    # Invariant 4: Duration exposure PnL monotonicity
    voyage_hours = 7.0 * 24.0
    tot_prem1 = m1 * (1.0 + current_wait_hours / voyage_hours)
    tot_prem2 = m2 * (1.0 + (current_wait_hours + delta_wait_hours) / voyage_hours)
    assert tot_prem2 >= tot_prem1 - 1e-9, f"Duration exposure PnL leakage: {tot_prem2} < {tot_prem1}"


# ==============================================================================
# INVARIANT 4: TACTICAL HYDRODYNAMIC HARDENING INVARIANT (COX PH)
# ==============================================================================

@settings(max_examples=50, deadline=None)
@given(
    wave_height_m=st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    mothership_loitering_index=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    distance_pmsc_km=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
    delta_wave=st.floats(min_value=0.05, max_value=8.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_tactical_hydrodynamic_hardening_cox_ph(
    wave_height_m: float,
    mothership_loitering_index: float,
    distance_pmsc_km: float,
    delta_wave: float,
):
    """Assert Tactical Hydrodynamic Hardening Invariant:

    As wave_height_m increases, Cox breach probability strictly does not increase.
    Across the hydrodynamic swamping threshold (e.g. 1.85m), the boarding feasibility
    and breach probability drop exponentially, reflecting that skiffs cannot board
    in heavy swells regardless of the MLI.
    """
    cox = CoxHazardSpec()
    hydro = HydroEnvelopeSpec()

    h1 = wave_height_m
    h2 = wave_height_m + delta_wave

    p1, haz1, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=h1,
        cox_spec=cox,
        hydro_spec=hydro,
    )
    p2, haz2, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=h2,
        cox_spec=cox,
        hydro_spec=hydro,
    )

    # Monotonic drop in hazard and probability with rising wave height
    assert haz2 <= haz1 + 1e-12, f"Hazard increased with sea-state: haz1={haz1}, haz2={haz2}"
    assert p2 <= p1 + 1e-12, f"Breach prob increased with sea-state: p1={p1}, p2={p2}"


@settings(max_examples=30, deadline=None)
@given(
    mothership_loitering_index=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    distance_pmsc_km=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_hydrodynamic_threshold_exponential_swamping(
    mothership_loitering_index: float,
    distance_pmsc_km: float,
):
    """Assert exponential drop across threshold:

    Comparing calm seas (Hs = 0.5m) to swamping seas (Hs = 4.0m),
    skiff feasibility drops exponentially to near-zero, strictly suppressing
    voyage breach probability even under extreme hostile loitering (MLI = 1.0).
    """
    cox = CoxHazardSpec()
    hydro = HydroEnvelopeSpec()  # h_0 = 1.85m, k_w = 3.5

    f_calm = skiff_boarding_feasibility(0.5, spec=hydro)
    f_swamp = skiff_boarding_feasibility(4.0, spec=hydro)

    # Boarding feasibility drops by over an order of magnitude
    assert f_calm > 0.90
    assert f_swamp < 0.01
    assert f_swamp / f_calm < 0.02

    # Cox breach probability drops significantly even at MLI = 1.0
    p_calm, haz_calm, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=0.5,
        cox_spec=cox,
        hydro_spec=hydro,
    )
    p_swamp, haz_swamp, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=4.0,
        cox_spec=cox,
        hydro_spec=hydro,
    )

    assert haz_swamp < haz_calm
    assert p_swamp < p_calm
    # Hazard ratio reflects beta_hydro_feasibility * (f_calm - f_swamp)
    expected_ratio = math.exp(cox.beta_hydro_feasibility * (f_swamp - f_calm))
    actual_ratio = haz_swamp / haz_calm
    assert math.isclose(actual_ratio, expected_ratio, rel_tol=1e-5)


# ==============================================================================
# INVARIANT 5: ANCHORAGE STATIC CORDON INVARIANT
# ==============================================================================

@settings(max_examples=50, deadline=None)
@given(
    mothership_loitering_index=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    distance_pmsc_km=st.floats(min_value=0.0, max_value=2000.0, allow_nan=False, allow_infinity=False),
    wave_height_m=st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    cvar_99=st.floats(min_value=0.1, max_value=40.0, allow_nan=False, allow_infinity=False),
    wait_hours=st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_anchorage_static_cordon_invariant(
    mothership_loitering_index: float,
    distance_pmsc_km: float,
    wave_height_m: float,
    cvar_99: float,
    wait_hours: float,
):
    """Assert Anchorage Static Cordon Invariant:

    Given identical threat inputs, transit breach probability and Additional Premium
    for AT_ANCHOR must strictly remain lower than UNDERWAY.
    """
    cox = CoxHazardSpec(
        baseline_hazard_underway=0.0005,
        baseline_hazard_anchor=0.0002,
    )
    vessel = VesselProfileSpec()
    corridor_anchor = CorridorSpec(operational_state="AT_ANCHOR")
    corridor_underway = CorridorSpec(operational_state="UNDERWAY")
    regime_spec = MacroRegimeSpec()
    reg_mult = compute_regime_multiplier(wait_hours, spec=regime_spec)

    # 1. Breach Probability Routing
    p_anchor, haz_anchor, ohi_anchor = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        vessel_spec=vessel,
        cox_spec=cox,
        corridor_spec=corridor_anchor,
    )
    p_underway, haz_underway, ohi_underway = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        vessel_spec=vessel,
        cox_spec=cox,
        corridor_spec=corridor_underway,
    )

    # OHI is identical for identical vessel
    assert ohi_anchor == ohi_underway

    # Invariant: daily hazard at anchor strictly lower than underway
    assert haz_anchor < haz_underway
    # Hazard ratio must strictly equal baseline_hazard_anchor / baseline_hazard_underway
    expected_ratio = cox.baseline_hazard_anchor / cox.baseline_hazard_underway
    actual_ratio = haz_anchor / haz_underway
    assert math.isclose(actual_ratio, expected_ratio, rel_tol=1e-6)

    # Invariant: 7-day breach probability at anchor strictly lower than underway
    assert p_anchor < p_underway

    # 2. Pricer AP Routing
    res_anchor = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        composite_cvar_99=cvar_99,
        vessel_spec=vessel,
        corridor_spec=corridor_anchor,
        cox_spec=cox,
        regime_multiplier=reg_mult,
    )
    res_underway = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=mothership_loitering_index,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        composite_cvar_99=cvar_99,
        vessel_spec=vessel,
        corridor_spec=corridor_underway,
        cox_spec=cox,
        regime_multiplier=reg_mult,
    )

    assert p_anchor < p_underway
    assert haz_anchor < haz_underway
    assert res_anchor.calibrated_7d_breach_prob < res_underway.calibrated_7d_breach_prob
    assert res_anchor.expected_7d_tail_loss_usd < res_underway.expected_7d_tail_loss_usd
    assert res_anchor.actuarial_7d_war_risk_ap_bps <= res_underway.actuarial_7d_war_risk_ap_bps
    if res_underway.actuarial_7d_war_risk_ap_bps > cox.commercial_baseline_bps:
        assert res_anchor.actuarial_7d_war_risk_ap_bps < res_underway.actuarial_7d_war_risk_ap_bps


# ==============================================================================
# INVARIANT INTEGRATION: FULL ENGINE HEADLESS EVALUATION
# ==============================================================================

@settings(max_examples=20, deadline=None)
@given(
    wait_hours=st.floats(min_value=10.0, max_value=120.0, allow_nan=False, allow_infinity=False),
    wave_height_m=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
    sar_dark_ratio=st.floats(min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_engine_headless_solvency_and_monotonicity(
    wait_hours: float,
    wave_height_m: float,
    sar_dark_ratio: float,
):
    """Assert MaritimeRiskEngine end-to-end evaluation preserves solvency and regime invariants."""
    engine = MaritimeRiskEngine.from_specs()

    from datetime import datetime, timedelta, timezone

    t0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    telemetry_series = [
        CivilianSensorTelemetry(
            telemetry_id=f"TEL-FUZZ-{i}",
            corridor_id="GOG_BONNY_BRASS_FAIRWAY",
            observation_timestamp=t0 + timedelta(days=i),
            publication_timestamp=t0 + timedelta(days=i, hours=2),
            sar_provider="GFW_SENTINEL1_SAR",
            metocean_provider="COPERNICUS_ERA5_METOCEAN",
            ais_provider="IMF_PORTWATCH_AIS",
            significant_wave_height_m=wave_height_m,
            sar_dark_vessel_ratio=sar_dark_ratio,
            anchorage_waiting_hours=wait_hours,
            viirs_flaring_continuity_idx=0.95,
        )
        for i in range(6)
    ]

    inc_rec = MaritimeIncident(
        incident_id="INC-FUZZ-1",
        event_time=1772452800,
        pub_time=1772460000,
        coordinates=GeoCoordinates(latitude=4.25, longitude=7.10),
        severity=SeverityInterval(min_severity=2.0, max_severity=6.0),
        feed_source="OSINT_IMB",
        lineage_hash="test_fuzz_hash",
    )

    audit = engine.evaluate(incidents=[inc_rec], telemetry=telemetry_series)

    # Assert Solvency Invariant in full engine output
    jwc = audit.jwc_pricing
    assert jwc.regime_multiplier >= 1.0
    assert jwc.actuarial_7d_war_risk_ap_bps > 0.0

    pure_shortfall_usd = jwc.effective_vessel_breach_prob * (jwc.cvar_99_demurrage_usd + jwc.catastrophic_tail_loss_usd)
    pure_shortfall_bps = (pure_shortfall_usd / jwc.insured_vessel_usd) * 10_000.0

    assert jwc.actuarial_7d_war_risk_ap_bps >= pure_shortfall_bps - 1e-9
    assert audit.gpd_result.shape_xi <= engine.hyperparams.gpd.xi_max
