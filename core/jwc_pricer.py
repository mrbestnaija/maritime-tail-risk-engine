"""First-Principles Lloyd's Joint War Committee (JWC) 7-Day AP & Demurrage Pricer.

Replaces naive 10x basis-point multipliers with actuarially sound loss expectation:
1. Translates CVaR_0.99 into expected tail operational delay days (delay_days = composite_cvar_99 * 0.85).
2. Computes demurrage financial loss (delay_days * daily_demurrage_usd).
3. Evaluates catastrophic boarding exposure (composite_cvar_99 / 10.0 * catastrophic_boarding_loss_usd).
4. Models single-vessel 7-day transit risk via spatial-temporal exposure and hydrodynamic boarding physics:
     p_vessel = p_7d * vessel_transit_exposure_factor * (0.5 + 0.5 * hydro_boarding_feasibility)
5. Combines into unconditional expected loss:
     E[Loss_7d] = p_vessel * (Demurrage + Catastrophic_Loss)
6. Expresses fair actuarial AP in basis points (bps) of insured vessel value ($85M).
7. Compares against prevailing Lloyd's JWC market quote (benchmark: 15.0 bps) to identify
   over/under-pricing commercial arbitrage spreads.

Pure domain math: ZERO I/O, ZERO PRINT, pure Python/math.
"""

from __future__ import annotations

from dataclasses import dataclass


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


def compute_jwc_7day_war_risk_ap(
    calibrated_7d_breach_prob: float,
    composite_cvar_99: float,
    insured_vessel_usd: float = 85_000_000.0,
    daily_demurrage_usd: float = 45_000.0,
    catastrophic_boarding_loss_usd: float = 3_500_000.0,
    jwc_market_benchmark_bps: float = 15.0,
    vessel_transit_exposure_factor: float = 1.0,
    hydro_boarding_feasibility: float = 1.0,
) -> JWCPricingResult:
    """Calculate first-principles Lloyd's JWC 7-Day Additional Premium and demurrage exposure.

    Parameters
    ----------
    calibrated_7d_breach_prob : float
        Calibrated probability p_7d that fairway risk breaches underwriter threshold.
    composite_cvar_99 : float
        Full composite fairway severity CVaR_0.99 on the [0.0, 10.0] scale.
    insured_vessel_usd : float
        Agreed insured hull & machinery value in USD (default: $85,000,000).
    daily_demurrage_usd : float
        Vessel daily charterparty demurrage rate (default: $45,000/day).
    catastrophic_boarding_loss_usd : float
        Expected loss given successful boarding / hijacking (default: $3,500,000).
    jwc_market_benchmark_bps : float
        Commercial market quote in basis points (default: 15.0 bps).
    vessel_transit_exposure_factor : float
        Single-voyage spatial-temporal corridor exposure factor (default: 1.0 for backwards compatibility).
    hydro_boarding_feasibility : float
        Small-craft boarding feasibility derived from wave height (default: 1.0).

    Returns
    -------
    JWCPricingResult
    """
    p_7d = max(min(float(calibrated_7d_breach_prob), 1.0), 0.0)
    cvar_99 = max(min(float(composite_cvar_99), 10.0), 0.0)
    vessel_usd = max(float(insured_vessel_usd), 1_000_000.0)
    transit_factor = max(min(float(vessel_transit_exposure_factor), 1.0), 0.0)
    hydro_feas = max(min(float(hydro_boarding_feasibility), 1.0), 0.0)

    # 1. Effective vessel transit breach probability modulated by exposure & hydrodynamics
    # When defaults (1.0, 1.0) are passed, effective_prob = p_7d * 1.0 * (0.5 + 0.5) = p_7d
    effective_vessel_prob = p_7d * transit_factor * (0.5 + 0.5 * hydro_feas)

    # 2. Operational tail delay mapping (0.85 days per severity point in the extreme tail)
    delay_days = cvar_99 * 0.85
    cvar_99_demurrage_usd = delay_days * float(daily_demurrage_usd)

    # 3. Catastrophic boarding severity fraction
    catastrophic_loss_usd = (cvar_99 / 10.0) * float(catastrophic_boarding_loss_usd)

    # 4. First-principles expected 7-day tail exposure for the transiting vessel
    expected_7d_tail_loss_usd = effective_vessel_prob * (cvar_99_demurrage_usd + catastrophic_loss_usd)

    # 5. Fair actuarial war-risk AP in basis points
    # 1 bps = 0.0001 (1 / 10,000) of insured vessel value
    actuarial_ap_bps = (expected_7d_tail_loss_usd / vessel_usd) * 10_000.0

    # 6. Mispricing spread vs commercial market benchmark
    mispricing_spread_bps = actuarial_ap_bps - float(jwc_market_benchmark_bps)
    per_transit_mispricing_usd = (mispricing_spread_bps / 10_000.0) * vessel_usd

    return JWCPricingResult(
        calibrated_7d_breach_prob=p_7d,
        composite_cvar_99=cvar_99,
        delay_days=delay_days,
        cvar_99_demurrage_usd=cvar_99_demurrage_usd,
        catastrophic_tail_loss_usd=catastrophic_loss_usd,
        expected_7d_tail_loss_usd=expected_7d_tail_loss_usd,
        actuarial_7d_war_risk_ap_bps=actuarial_ap_bps,
        jwc_market_benchmark_bps=float(jwc_market_benchmark_bps),
        mispricing_spread_bps=mispricing_spread_bps,
        per_transit_mispricing_usd=per_transit_mispricing_usd,
        insured_vessel_usd=vessel_usd,
        vessel_transit_exposure_factor=transit_factor,
        hydro_boarding_feasibility=hydro_feas,
        effective_vessel_breach_prob=effective_vessel_prob,
    )
