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

from dataclasses import dataclass
from typing import Optional

from .specs import CorridorSpec, VesselProfileSpec


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
    cvar_99 = max(min(float(composite_cvar_99), 10.0), 0.0)
    vessel_usd = max(float(vessel_val), 1_000_000.0)
    transit_factor = max(min(transit_factor, 1.0), 0.0)
    hydro_feas = max(min(float(hydro_boarding_feasibility), 1.0), 0.0)

    # 1. Effective vessel transit breach probability modulated by exposure & hydrodynamics
    effective_vessel_prob = p_7d * transit_factor * (0.5 + 0.5 * hydro_feas)

    # 2. Operational tail delay mapping
    delay_days = cvar_99 * v_spec.delay_days_per_cvar_unit
    cvar_99_demurrage_usd = delay_days * demurrage_rate

    # 3. Catastrophic boarding severity fraction
    catastrophic_loss_usd = (cvar_99 / 10.0) * catastrophic_rate

    # 4. First-principles expected 7-day tail exposure for the transiting vessel
    expected_7d_tail_loss_usd = effective_vessel_prob * (cvar_99_demurrage_usd + catastrophic_loss_usd)

    # 5. Fair actuarial war-risk AP in basis points (1 bps = 0.0001 of insured hull value)
    actuarial_ap_bps = (expected_7d_tail_loss_usd / vessel_usd) * 10_000.0

    # 6. Commercial spread and per-transit mispricing USD
    mispricing_spread_bps = actuarial_ap_bps - benchmark_bps
    per_transit_mispricing_usd = (mispricing_spread_bps / 10_000.0) * vessel_usd

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
    )


# Alias for backward-compatible naming
price_jwc_7day_transit = compute_jwc_7day_war_risk_ap

__all__ = [
    "JWCPricingResult",
    "JWCPriceResult",
    "compute_jwc_7day_war_risk_ap",
    "price_jwc_7day_transit",
]
