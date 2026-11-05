"""First-Principles Lloyd's Joint War Committee (JWC) 7-Day AP & Demurrage Pricer.

Replaces naive 10x basis-point multipliers with actuarially sound loss expectation:
1. Translates CVaR_0.99 into expected tail operational delay days (delay_days = composite_cvar_99 * delay_factor).
2. Computes demurrage financial loss (delay_days * daily_demurrage_usd).
3. Evaluates catastrophic boarding exposure (composite_cvar_99 / 10.0 * catastrophic_boarding_loss_usd).
4. Models single-vessel 7-day transit risk via spatial-temporal exposure and hydrodynamic boarding physics:
     p_vessel = p_7d * vessel_transit_exposure_factor * (0.5 + 0.5 * hydro_boarding_feasibility)
5. Combines into unconditional expected loss:
     E[Loss_7d] = p_vessel * (Demurrage + Catastrophic_Loss)
6. Expresses fair actuarial AP in basis points (bps) of insured vessel value.
7. Compares against prevailing Lloyd's JWC market quote to identify
   over/under-pricing commercial arbitrage spreads.

Pure domain math: ZERO I/O, ZERO PRINT, pure Python/math.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Optional

from .hydro_envelope import skiff_boarding_feasibility
from .specs import CorridorSpec, CoxHazardSpec, HydroEnvelopeSpec, VesselProfileSpec


@dataclass(frozen=True)
class JWCPricingResult:
    """Immutable domain container for first-principles JWC actuarial pricing."""

    calibrated_7d_breach_prob: float
    composite_cvar_99: float
    delay_days: float
    cvar_99_demurrage_usd: float
    catastrophic_tail_loss_usd: float
    expected_7d_tail_loss_usd: float
    actuarial_7d_war_risk_ap_bps: float
    jwc_market_benchmark_bps: float
    mispricing_spread_bps: float
    per_transit_mispricing_usd: float
    insured_vessel_usd: float
    vessel_transit_exposure_factor: float = 1.0
    hydro_boarding_feasibility: float = 1.0
    effective_vessel_breach_prob: float = 0.0
    daily_hazard_rate: float = 0.0
    operational_hardening_index: float = 0.0
    pricing_model: str = "lloyds_first_principles"
    regime_multiplier: float = 1.0
    operational_state: str = "UNDERWAY"
    delta_ap_usd: float = 0.0
    dividend_net_usd: float = 0.0
    delta_reserve_usd: float = 0.0
    escort_opex_cost_usd: float = 0.0
    ap_lone_usd: float = 0.0
    ap_escorted_usd: float = 0.0
    ap_lone_bps: float = 0.0
    ap_escorted_bps: float = 0.0
    ap_unprotected_anchor_bps: float = 0.0
    ap_secured_anchor_bps: float = 0.0
    composite_cvar_99_usd: float = 0.0
    ap_credible_interval_lower_bps: Optional[float] = None
    ap_credible_interval_upper_bps: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert pricing result to dictionary for JSON serialization and audit manifests."""
        return asdict(self)

    @property
    def market_benchmark_bps(self) -> float:
        """Alias for jwc_market_benchmark_bps."""
        return self.jwc_market_benchmark_bps


# Alias for spec naming compatibility
JWCPriceResult = JWCPricingResult


def compute_jwc_7day_war_risk_ap(
    calibrated_7d_breach_prob: float,
    composite_cvar_99: float,
    insured_vessel_usd: Optional[float] = None,
    daily_demurrage_usd: Optional[float] = None,
    catastrophic_boarding_loss_usd: Optional[float] = None,
    jwc_market_benchmark_bps: Optional[float] = None,
    vessel_transit_exposure_factor: Optional[float] = None,
    hydro_boarding_feasibility: float = 1.0,
    vessel_spec: Optional[VesselProfileSpec] = None,
    corridor_spec: Optional[CorridorSpec] = None,
    regime_multiplier: float = 1.0,
    operational_state: Optional[str] = None,
    cox_spec: Optional[CoxHazardSpec] = None,
    commercial_baseline_bps: Optional[float] = None,
    mothership_loitering_idx: float = 0.25,
    distance_pmsc_km: float = 180.0,
    wave_height_m: float = 1.2,
    wind_knots: Optional[float] = None,
    hydro_spec: Optional[HydroEnvelopeSpec] = None,
    **kwargs: Any,
) -> JWCPricingResult:
    """Calculate first-principles Lloyd's JWC 7-Day Additional Premium and demurrage exposure.

    Parameters
    ----------
    calibrated_7d_breach_prob : float
        Calibrated probability p_7d that fairway risk breaches underwriter threshold.
    composite_cvar_99 : float
        Full composite fairway severity CVaR_0.99 on the [0.0, 10.0] scale.
    insured_vessel_usd : Optional[float]
        Agreed insured hull & machinery value in USD.
    daily_demurrage_usd : Optional[float]
        Vessel daily charterparty demurrage rate.
    catastrophic_boarding_loss_usd : Optional[float]
        Expected loss given successful boarding / hijacking.
    jwc_market_benchmark_bps : Optional[float]
        Commercial market quote in basis points.
    vessel_transit_exposure_factor : Optional[float]
        Single-voyage spatial-temporal corridor exposure factor.
    hydro_boarding_feasibility : float
        Small-craft boarding feasibility derived from wave height (default: 1.0).
    vessel_spec : Optional[VesselProfileSpec]
        Vessel profile specification. Defaults to VesselProfileSpec().
    corridor_spec : Optional[CorridorSpec]
        Corridor specification. Defaults to CorridorSpec().

    Returns
    -------
    JWCPricingResult
    """
    v_spec = vessel_spec or VesselProfileSpec()
    c_spec = corridor_spec or CorridorSpec()

    vessel_val = (
        v_spec.insured_vessel_usd if insured_vessel_usd is None else float(insured_vessel_usd)
    )
    demurrage_rate = (
        v_spec.daily_demurrage_usd if daily_demurrage_usd is None else float(daily_demurrage_usd)
    )
    catastrophic_rate = (
        v_spec.catastrophic_boarding_loss_usd
        if catastrophic_boarding_loss_usd is None
        else float(catastrophic_boarding_loss_usd)
    )
    benchmark_bps = (
        c_spec.jwc_market_benchmark_bps
        if jwc_market_benchmark_bps is None
        else float(jwc_market_benchmark_bps)
    )

    if vessel_transit_exposure_factor is not None:
        transit_factor = float(vessel_transit_exposure_factor)
    elif vessel_spec is not None:
        transit_factor = float(v_spec.single_vessel_exposure_factor)
    else:
        transit_factor = 1.0

    p_7d = max(min(float(calibrated_7d_breach_prob), 1.0), 0.0)
    cvar_99 = max(float(composite_cvar_99), 0.0)
    vessel_usd = max(float(vessel_val), 1_000_000.0)
    transit_factor = max(min(transit_factor, 1.0), 0.0)
    hydro_feas = max(min(float(hydro_boarding_feasibility), 1.0), 0.0)
    reg_mult = max(float(regime_multiplier), 0.0)
    resolved_op_state = str(operational_state or getattr(c_spec, "operational_state", "UNDERWAY"))

    # 1. Effective vessel transit breach probability modulated by exposure & hydrodynamics
    effective_vessel_prob = p_7d * transit_factor * (0.5 + 0.5 * hydro_feas)

    # 2. Operational tail delay mapping
    delay_days = cvar_99 * v_spec.delay_days_per_cvar_unit
    cvar_99_demurrage_usd = delay_days * demurrage_rate

    # 3. Catastrophic boarding severity fraction
    catastrophic_loss_usd = (cvar_99 / 10.0) * catastrophic_rate

    # 4. First-principles expected 7-day tail exposure for the transiting vessel (scaled by regime multiplier)
    expected_7d_tail_loss_usd = effective_vessel_prob * (cvar_99_demurrage_usd + catastrophic_loss_usd) * reg_mult
    # Tail Risk Cap Guard: expected tail loss cannot exceed insured vessel hull value
    expected_7d_tail_loss_usd = min(expected_7d_tail_loss_usd, vessel_usd)

    # 5. Fair actuarial war-risk AP in basis points (1 bps = 0.0001 of insured hull value)
    actuarial_ap_bps = (expected_7d_tail_loss_usd / vessel_usd) * 10_000.0
    floor_bps = (
        commercial_baseline_bps
        if commercial_baseline_bps is not None
        else (getattr(cox_spec, "commercial_baseline_bps", 0.0) if cox_spec is not None else 0.0)
    )
    if floor_bps > 0.0:
        actuarial_ap_bps = max(actuarial_ap_bps, floor_bps)

    # 6. Commercial spread and per-transit mispricing USD
    mispricing_spread_bps = actuarial_ap_bps - benchmark_bps
    per_transit_mispricing_usd = (mispricing_spread_bps / 10_000.0) * vessel_usd

    # 7. Actuarial Credible Interval for 7-Day AP derived from CVaR_0.99 uncertainty bounds
    cvar_lower = kwargs.get("composite_cvar_99_lower")
    cvar_upper = kwargs.get("composite_cvar_99_upper")
    ap_ci_lower_bps: Optional[float] = None
    ap_ci_upper_bps: Optional[float] = None

    if cvar_lower is not None:
        c_low = max(float(cvar_lower), 0.0)
        delay_low = c_low * v_spec.delay_days_per_cvar_unit
        demurrage_usd_low = delay_low * demurrage_rate
        catastrophic_loss_usd_low = (c_low / 10.0) * catastrophic_rate
        exp_loss_low = min(
            effective_vessel_prob * (demurrage_usd_low + catastrophic_loss_usd_low) * reg_mult,
            vessel_usd,
        )
        ap_ci_lower_bps = (exp_loss_low / vessel_usd) * 10_000.0
        if floor_bps > 0.0:
            ap_ci_lower_bps = max(ap_ci_lower_bps, floor_bps)

    if cvar_upper is not None:
        c_high = max(float(cvar_upper), 0.0)
        delay_high = c_high * v_spec.delay_days_per_cvar_unit
        demurrage_usd_high = delay_high * demurrage_rate
        catastrophic_loss_usd_high = (c_high / 10.0) * catastrophic_rate
        exp_loss_high = min(
            effective_vessel_prob * (demurrage_usd_high + catastrophic_loss_usd_high) * reg_mult,
            vessel_usd,
        )
        ap_ci_upper_bps = (exp_loss_high / vessel_usd) * 10_000.0
        if floor_bps > 0.0:
            ap_ci_upper_bps = max(ap_ci_upper_bps, floor_bps)

    dividend_data = compute_tactical_hardening_dividend(
        mothership_loitering_idx=mothership_loitering_idx,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        composite_cvar_99=cvar_99,
        wind_knots=wind_knots,
        vessel_spec=v_spec,
        corridor_spec=c_spec,
        cox_spec=cox_spec,
        hydro_spec=hydro_spec,
        regime_multiplier=reg_mult,
    )

    return JWCPricingResult(
        calibrated_7d_breach_prob=p_7d,
        composite_cvar_99=cvar_99,
        delay_days=delay_days,
        cvar_99_demurrage_usd=cvar_99_demurrage_usd,
        catastrophic_tail_loss_usd=catastrophic_loss_usd,
        expected_7d_tail_loss_usd=expected_7d_tail_loss_usd,
        actuarial_7d_war_risk_ap_bps=actuarial_ap_bps,
        jwc_market_benchmark_bps=benchmark_bps,
        mispricing_spread_bps=mispricing_spread_bps,
        per_transit_mispricing_usd=per_transit_mispricing_usd,
        insured_vessel_usd=vessel_usd,
        vessel_transit_exposure_factor=transit_factor,
        hydro_boarding_feasibility=hydro_feas,
        effective_vessel_breach_prob=effective_vessel_prob,
        daily_hazard_rate=0.0,
        operational_hardening_index=0.0,
        pricing_model="lloyds_first_principles",
        regime_multiplier=reg_mult,
        operational_state=resolved_op_state,
        delta_ap_usd=dividend_data["delta_ap_usd"],
        dividend_net_usd=dividend_data["dividend_net_usd"],
        delta_reserve_usd=dividend_data["delta_reserve_usd"],
        escort_opex_cost_usd=dividend_data["escort_opex_cost_usd"],
        ap_lone_usd=dividend_data["ap_lone_usd"],
        ap_escorted_usd=dividend_data["ap_escorted_usd"],
        ap_lone_bps=dividend_data["ap_lone_bps"],
        ap_escorted_bps=dividend_data["ap_escorted_bps"],
        ap_unprotected_anchor_bps=dividend_data["ap_unprotected_anchor_bps"],
        ap_secured_anchor_bps=dividend_data["ap_secured_anchor_bps"],
        composite_cvar_99_usd=dividend_data["composite_cvar_99_usd"],
        ap_credible_interval_lower_bps=ap_ci_lower_bps,
        ap_credible_interval_upper_bps=ap_ci_upper_bps,
    )


# Alias for backward-compatible naming
price_jwc_7day_transit = compute_jwc_7day_war_risk_ap


def compute_operational_hardening_index(
    vessel_spec: Optional[VesselProfileSpec] = None,
    cox_spec: Optional[CoxHazardSpec] = None,
) -> float:
    """Compute vessel Operational Hardening Index (OHI).

    Combines freeboard, sustained speed, and armed security guard presence:
    OHI = w_fb * freeboard + w_spd * speed + (w_guard if guards_present else 0.0)
    """
    v_spec = vessel_spec or VesselProfileSpec()
    c_spec = cox_spec or CoxHazardSpec()

    guard_component = c_spec.ohi_armed_guard_weight if v_spec.pms_guards_present else 0.0
    ohi = (
        c_spec.ohi_freeboard_weight * float(v_spec.freeboard_meters)
        + c_spec.ohi_speed_weight * float(v_spec.max_sustained_speed_knots)
        + guard_component
    )
    return float(max(ohi, 0.0))


def compute_cox_7day_breach_probability(
    mothership_loitering_idx: float,
    distance_pmsc_km: float,
    wave_height_m: float,
    wind_knots: Optional[float] = None,
    vessel_spec: Optional[VesselProfileSpec] = None,
    cox_spec: Optional[CoxHazardSpec] = None,
    hydro_spec: Optional[HydroEnvelopeSpec] = None,
    corridor_spec: Optional[CorridorSpec] = None,
) -> tuple[float, float, float]:
    """Calculate voyage breach probability via Cox Proportional Hazards Model.

    lambda_v(t) = lambda_0 * exp(beta_mli * MLI + beta_pmsc * d_PMSC + beta_ohi * OHI + beta_hydro * Phi(Hs, W))
    P_breach_7d = 1.0 - exp(-lambda_v * T_days)

    Returns
    -------
    tuple[float, float, float]
        (p_breach_7d, daily_hazard_rate, ohi)
    """
    c_spec = cox_spec or CoxHazardSpec()
    v_spec = vessel_spec or VesselProfileSpec()
    h_spec = hydro_spec or HydroEnvelopeSpec()

    mli = max(min(float(mothership_loitering_idx), 1.0), 0.0)
    dist_pmsc = max(float(distance_pmsc_km), 0.0)
    wave_h = max(float(wave_height_m), 0.0)

    # Evaluate small-skiff boarding feasibility using smooth logistic swamping curve
    hydro_feasibility = skiff_boarding_feasibility(
        wave_height_m=wave_h,
        wind_knots=wind_knots,
        spec=h_spec,
    )

    ohi = compute_operational_hardening_index(vessel_spec=v_spec, cox_spec=c_spec)

    # Cox log-hazard exponent
    log_hazard_exponent = (
        c_spec.beta_mli * mli
        + c_spec.beta_pmsc_distance_km * dist_pmsc
        + c_spec.beta_ohi * ohi
        + c_spec.beta_hydro_feasibility * hydro_feasibility
    )

    # Numerical stability clamp for exponent
    clamped_exponent = max(min(log_hazard_exponent, 50.0), -50.0)
    op_state = (
        corridor_spec.operational_state if corridor_spec and corridor_spec.operational_state else "UNDERWAY"
    ).upper()
    if op_state in ("AT_ANCHOR_SECURED",):
        baseline_hazard = getattr(c_spec, "baseline_hazard_anchor_secured", 0.00010)
    elif op_state in ("AT_ANCHOR",):
        baseline_hazard = getattr(c_spec, "baseline_hazard_anchor", c_spec.baseline_daily_hazard)
    elif op_state in ("UNDERWAY_ESCORTED", "ESCORTED"):
        baseline_hazard = getattr(c_spec, "baseline_hazard_escorted", 0.00015)
    elif op_state in ("AT_ANCHOR_UNPROTECTED", "UNPROTECTED_ANCHOR"):
        baseline_hazard = getattr(c_spec, "baseline_hazard_anchor_unprotected", 0.00045)
    else:
        baseline_hazard = getattr(c_spec, "baseline_hazard_underway", c_spec.baseline_daily_hazard)
    daily_hazard = baseline_hazard * math.exp(clamped_exponent)

    # 7-day cumulative voyage breach probability
    cum_hazard = daily_hazard * c_spec.voyage_window_days
    if cum_hazard > 50.0:
        p_breach_7d = 1.0
    else:
        p_breach_7d = 1.0 - math.exp(-cum_hazard)

    p_breach_7d = float(max(min(p_breach_7d, 1.0), 0.0))
    return p_breach_7d, float(daily_hazard), float(ohi)


def compute_tactical_hardening_dividend(
    mothership_loitering_idx: float,
    distance_pmsc_km: float,
    wave_height_m: float,
    composite_cvar_99: float,
    wind_knots: Optional[float] = None,
    vessel_spec: Optional[VesselProfileSpec] = None,
    corridor_spec: Optional[CorridorSpec] = None,
    cox_spec: Optional[CoxHazardSpec] = None,
    hydro_spec: Optional[HydroEnvelopeSpec] = None,
    regime_multiplier: float = 1.0,
) -> dict[str, float]:
    """Calculate the Escort & Anchorage Tactical Hardening Arbitrage.

    Evaluates the financial savings and Expected Shortfall (CVaR_99) reduction of security/armed escort:
    1. delta_ap_usd = ap_lone_usd - ap_escorted_usd (Gross AP Savings)
    2. dividend_net_usd = delta_ap_usd - (voyage_window_days * daily_escort_cost_usd) (Net Arbitrage)
    3. delta_reserve_usd = (p_breach_lone - p_breach_escorted) * composite_cvar_99_usd (Expected Shortfall / CVaR_99 Reduction)

    Returns
    -------
    dict[str, float]
        Complete arbitrage breakdown dictionary.
    """
    v_spec = vessel_spec or VesselProfileSpec()
    c_spec = corridor_spec or CorridorSpec()
    cx_spec = cox_spec or CoxHazardSpec()
    h_spec = hydro_spec or HydroEnvelopeSpec()

    cvar_99 = max(float(composite_cvar_99), 0.0)
    vessel_usd = max(float(v_spec.insured_vessel_usd), 1_000_000.0)
    reg_mult = max(float(regime_multiplier), 0.0)
    commercial_floor = getattr(cx_spec, "commercial_baseline_bps", 0.0)

    # Operational delay & demurrage
    delay_days = cvar_99 * v_spec.delay_days_per_cvar_unit
    cvar_99_demurrage_usd = delay_days * v_spec.daily_demurrage_usd
    catastrophic_loss_usd = (cvar_99 / 10.0) * v_spec.catastrophic_boarding_loss_usd
    composite_cvar_99_usd = cvar_99_demurrage_usd + catastrophic_loss_usd

    # 1. Lone voyage pricing (UNDERWAY_LONE)
    c_lone = CorridorSpec(
        corridor_id=c_spec.corridor_id,
        operational_state="UNDERWAY_LONE",
        jwc_market_benchmark_bps=c_spec.jwc_market_benchmark_bps,
    )
    p_lone, _, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_idx,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        wind_knots=wind_knots,
        vessel_spec=v_spec,
        cox_spec=cx_spec,
        hydro_spec=h_spec,
        corridor_spec=c_lone,
    )
    expected_loss_lone = min(p_lone * composite_cvar_99_usd * reg_mult, vessel_usd)
    ap_bps_lone = (expected_loss_lone / vessel_usd) * 10_000.0
    if commercial_floor > 0.0:
        ap_bps_lone = max(ap_bps_lone, commercial_floor)
    ap_lone_usd = (ap_bps_lone / 10_000.0) * vessel_usd

    # 2. Escorted voyage pricing (UNDERWAY_ESCORTED)
    c_escorted = CorridorSpec(
        corridor_id=c_spec.corridor_id,
        operational_state="UNDERWAY_ESCORTED",
        jwc_market_benchmark_bps=c_spec.jwc_market_benchmark_bps,
    )
    p_escorted, _, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_idx,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        wind_knots=wind_knots,
        vessel_spec=v_spec,
        cox_spec=cx_spec,
        hydro_spec=h_spec,
        corridor_spec=c_escorted,
    )
    expected_loss_escorted = min(p_escorted * composite_cvar_99_usd * reg_mult, vessel_usd)
    ap_bps_escorted = (expected_loss_escorted / vessel_usd) * 10_000.0
    if commercial_floor > 0.0:
        ap_bps_escorted = max(ap_bps_escorted, commercial_floor)
    ap_escorted_usd = (ap_bps_escorted / 10_000.0) * vessel_usd

    # 3. Unprotected Anchor pricing (AT_ANCHOR_UNPROTECTED)
    c_unprotected = CorridorSpec(
        corridor_id=c_spec.corridor_id,
        operational_state="AT_ANCHOR_UNPROTECTED",
        jwc_market_benchmark_bps=c_spec.jwc_market_benchmark_bps,
    )
    p_unprotected, _, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_idx,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        wind_knots=wind_knots,
        vessel_spec=v_spec,
        cox_spec=cx_spec,
        hydro_spec=h_spec,
        corridor_spec=c_unprotected,
    )
    expected_loss_unprotected = min(p_unprotected * composite_cvar_99_usd * reg_mult, vessel_usd)
    ap_bps_unprotected = (expected_loss_unprotected / vessel_usd) * 10_000.0
    if commercial_floor > 0.0:
        ap_bps_unprotected = max(ap_bps_unprotected, commercial_floor)

    # 4. Secured Anchor pricing (AT_ANCHOR_SECURED)
    c_secured = CorridorSpec(
        corridor_id=c_spec.corridor_id,
        operational_state="AT_ANCHOR_SECURED",
        jwc_market_benchmark_bps=c_spec.jwc_market_benchmark_bps,
    )
    p_secured, _, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_idx,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        wind_knots=wind_knots,
        vessel_spec=v_spec,
        cox_spec=cx_spec,
        hydro_spec=h_spec,
        corridor_spec=c_secured,
    )
    expected_loss_secured = min(p_secured * composite_cvar_99_usd * reg_mult, vessel_usd)
    ap_bps_secured = (expected_loss_secured / vessel_usd) * 10_000.0
    if commercial_floor > 0.0:
        ap_bps_secured = max(ap_bps_secured, commercial_floor)

    # Arbitrage Metrics
    delta_ap_usd = max(float(ap_lone_usd - ap_escorted_usd), 0.0)
    voyage_days = float(cx_spec.voyage_window_days)
    daily_escort = float(getattr(cx_spec, "escort_daily_rate_usd", 0.0)) or float(
        getattr(v_spec, "daily_escort_cost_usd", 0.0)
    )
    escort_opex_cost_usd = float(voyage_days * daily_escort)
    dividend_net_usd = float(delta_ap_usd - escort_opex_cost_usd)
    delta_reserve_usd = float((p_lone - p_escorted) * composite_cvar_99_usd)

    return {
        "ap_lone_usd": float(ap_lone_usd),
        "ap_escorted_usd": float(ap_escorted_usd),
        "ap_lone_bps": float(ap_bps_lone),
        "ap_escorted_bps": float(ap_bps_escorted),
        "ap_unprotected_anchor_bps": float(ap_bps_unprotected),
        "ap_secured_anchor_bps": float(ap_bps_secured),
        "delta_ap_usd": delta_ap_usd,
        "escort_opex_cost_usd": escort_opex_cost_usd,
        "dividend_net_usd": dividend_net_usd,
        "delta_reserve_usd": delta_reserve_usd,
        "composite_cvar_99_usd": composite_cvar_99_usd,
        "p_breach_lone": float(p_lone),
        "p_breach_escorted": float(p_escorted),
        "p_breach_unprotected": float(p_unprotected),
        "p_breach_secured": float(p_secured),
    }


def price_cox_7day_war_risk_ap(
    mothership_loitering_idx: float,
    distance_pmsc_km: float,
    wave_height_m: float,
    composite_cvar_99: float,
    wind_knots: Optional[float] = None,
    vessel_spec: Optional[VesselProfileSpec] = None,
    corridor_spec: Optional[CorridorSpec] = None,
    cox_spec: Optional[CoxHazardSpec] = None,
    hydro_spec: Optional[HydroEnvelopeSpec] = None,
    regime_multiplier: float = 1.0,
) -> JWCPricingResult:
    """Calculate fair Additional Premium under Cox Proportional Hazards voyage model."""
    v_spec = vessel_spec or VesselProfileSpec()
    c_spec = corridor_spec or CorridorSpec()
    cx_spec = cox_spec or CoxHazardSpec()
    h_spec = hydro_spec or HydroEnvelopeSpec()

    p_breach_7d, daily_hazard, ohi = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mothership_loitering_idx,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        wind_knots=wind_knots,
        vessel_spec=v_spec,
        cox_spec=cx_spec,
        hydro_spec=h_spec,
        corridor_spec=c_spec,
    )

    cvar_99 = max(float(composite_cvar_99), 0.0)
    vessel_usd = max(float(v_spec.insured_vessel_usd), 1_000_000.0)
    benchmark_bps = float(c_spec.jwc_market_benchmark_bps)
    reg_mult = max(float(regime_multiplier), 0.0)
    resolved_op_state = str(getattr(c_spec, "operational_state", "UNDERWAY"))

    # Operational delay & demurrage
    delay_days = cvar_99 * v_spec.delay_days_per_cvar_unit
    cvar_99_demurrage_usd = delay_days * v_spec.daily_demurrage_usd

    # Catastrophic boarding exposure
    catastrophic_loss_usd = (cvar_99 / 10.0) * v_spec.catastrophic_boarding_loss_usd

    # First-principles expected loss: p_breach_7d directly models vessel voyage breach (scaled by regime multiplier)
    expected_7d_tail_loss_usd = p_breach_7d * (cvar_99_demurrage_usd + catastrophic_loss_usd) * reg_mult
    # Tail Risk Cap Guard: expected tail loss cannot exceed insured vessel hull value
    expected_7d_tail_loss_usd = min(expected_7d_tail_loss_usd, vessel_usd)

    # Fair actuarial AP in basis points (1 bps = 0.0001 of hull)
    actuarial_ap_bps = (expected_7d_tail_loss_usd / vessel_usd) * 10_000.0
    commercial_floor = getattr(cx_spec, "commercial_baseline_bps", 0.0)
    if commercial_floor > 0.0:
        actuarial_ap_bps = max(actuarial_ap_bps, commercial_floor)
    mispricing_spread_bps = actuarial_ap_bps - benchmark_bps
    per_transit_mispricing_usd = (mispricing_spread_bps / 10_000.0) * vessel_usd

    hydro_feas = skiff_boarding_feasibility(
        wave_height_m=wave_height_m, wind_knots=wind_knots, spec=h_spec
    )

    dividend_data = compute_tactical_hardening_dividend(
        mothership_loitering_idx=mothership_loitering_idx,
        distance_pmsc_km=distance_pmsc_km,
        wave_height_m=wave_height_m,
        composite_cvar_99=composite_cvar_99,
        wind_knots=wind_knots,
        vessel_spec=v_spec,
        corridor_spec=c_spec,
        cox_spec=cx_spec,
        hydro_spec=h_spec,
        regime_multiplier=reg_mult,
    )

    return JWCPricingResult(
        calibrated_7d_breach_prob=p_breach_7d,
        composite_cvar_99=cvar_99,
        delay_days=delay_days,
        cvar_99_demurrage_usd=cvar_99_demurrage_usd,
        catastrophic_tail_loss_usd=catastrophic_loss_usd,
        expected_7d_tail_loss_usd=expected_7d_tail_loss_usd,
        actuarial_7d_war_risk_ap_bps=actuarial_ap_bps,
        jwc_market_benchmark_bps=benchmark_bps,
        mispricing_spread_bps=mispricing_spread_bps,
        per_transit_mispricing_usd=per_transit_mispricing_usd,
        insured_vessel_usd=vessel_usd,
        vessel_transit_exposure_factor=v_spec.single_vessel_exposure_factor,
        hydro_boarding_feasibility=hydro_feas,
        effective_vessel_breach_prob=p_breach_7d,
        daily_hazard_rate=daily_hazard,
        operational_hardening_index=ohi,
        pricing_model="cox_proportional_hazards_jwc",
        regime_multiplier=reg_mult,
        operational_state=resolved_op_state,
        delta_ap_usd=dividend_data["delta_ap_usd"],
        dividend_net_usd=dividend_data["dividend_net_usd"],
        delta_reserve_usd=dividend_data["delta_reserve_usd"],
        escort_opex_cost_usd=dividend_data["escort_opex_cost_usd"],
        ap_lone_usd=dividend_data["ap_lone_usd"],
        ap_escorted_usd=dividend_data["ap_escorted_usd"],
        ap_lone_bps=dividend_data["ap_lone_bps"],
        ap_escorted_bps=dividend_data["ap_escorted_bps"],
        ap_unprotected_anchor_bps=dividend_data["ap_unprotected_anchor_bps"],
        ap_secured_anchor_bps=dividend_data["ap_secured_anchor_bps"],
        composite_cvar_99_usd=dividend_data["composite_cvar_99_usd"],
    )


__all__ = [
    "JWCPricingResult",
    "JWCPriceResult",
    "compute_jwc_7day_war_risk_ap",
    "price_jwc_7day_transit",
    "compute_operational_hardening_index",
    "compute_cox_7day_breach_probability",
    "price_cox_7day_war_risk_ap",
    "compute_tactical_hardening_dividend",
]
