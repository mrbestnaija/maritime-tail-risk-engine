"""Peaks-Over-Threshold (POT) Generalized Pareto Distribution (GPD) Tail Engine.

Implements:
1. GPD fitting on structural shock exceedances: E = {r_t - u | r_t > u}
2. Small-sample regularization via Empirical Bayes shrinkage (core.empirical_bayes)
   to prevent optimizer railing at xi = -0.5000.
3. Hard numerical stability guards:
   - Smooth exact analytical exponential limit for |xi| < 1e-6 (zero-division protection)
   - Strict shape cap xi <= 0.95 (preventing infinite-mean divergence)
   - Anti-1e-9 denominator clamp protection (no million-fold ratio explosions)
   - Zero-variance and pathological boundary resiliency
4. Both residual shock tail and reconstructed composite corridor tail metrics.
5. Quantitative actuarial war-risk loading in basis points (bps).
6. Pure domain math: ZERO I/O, ZERO PRINT, pure NumPy/SciPy.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence
import numpy as np
from scipy.optimize import minimize

from .empirical_bayes import shrink_gpd_parameters
from .specs import EmpiricalBayesSpec, GPDFitterSpec, VesselProfileSpec


@dataclass(frozen=True)
class GPDTailRiskEstimate:
    """Immutable domain container for POT-GPD tail risk evaluation."""

    shape_xi: float
    scale_sigma: float
    threshold_u: float
    exceedance_count: int
    var_95: float
    var_99: float
    cvar_99: float
    actuarial_war_risk_loading_bps: float
    insured_vessel_usd: float = 0.0
    # Phase 2B structural shock vs composite corridor separation
    residual_var_95: float = 0.0
    residual_var_99: float = 0.0
    residual_cvar_99: float = 0.0
    baseline_anchor: float = 0.0
    composite_corridor_var_95: float = 0.0
    composite_corridor_var_99: float = 0.0
    composite_corridor_cvar_99: float = 0.0
    shrinkage_weight_w: float = 0.0
    raw_xi: float = 0.0


def gpd_cdf(y: np.ndarray, xi: float, sigma: float) -> np.ndarray:
    """Compute Generalized Pareto Distribution (GPD) cumulative distribution function.
    
    For |xi| < 1e-6, smoothly evaluates the exact analytical exponential limit.
    """
    y_arr = np.asarray(y, dtype=np.float64)
    if sigma <= 0.0:
        return np.ones_like(y_arr)

    # Smooth analytical exponential limit for |xi| < 1e-6
    if abs(xi) < 1e-6:
        return 1.0 - np.exp(-y_arr / sigma)

    # Standard GPD formula with domain guard
    term = 1.0 + (xi * y_arr) / sigma
    term_safe = np.maximum(term, 0.0)
    return 1.0 - np.power(term_safe, -1.0 / xi)


def compute_gpd_var_cvar(
    u: float,
    xi: float,
    sigma: float,
    p_u: float,
    alpha: float = 0.99,
    shape_cap: float = 0.95,
) -> tuple[float, float]:
    """Compute VaR_alpha and CVaR_alpha under GPD Peaks-Over-Threshold formulation.
    
    Guarantees zero-division stability as xi -> 0 via exact analytical limits.
    """
    if p_u <= 0.0 or sigma <= 0.0:
        return float(u), float(u)

    # Enforce upper shape cap to prevent infinite-mean divergence
    xi_eff = min(float(xi), float(shape_cap))

    if alpha <= 1.0 - p_u:
        var_alpha = float(u)
    else:
        tail_ratio = p_u / (1.0 - alpha)
        if abs(xi_eff) < 1e-6:
            var_alpha = float(u + sigma * math.log(tail_ratio))
        else:
            var_alpha = float(u + (sigma / xi_eff) * (math.pow(tail_ratio, xi_eff) - 1.0))

    # Expected Shortfall (CVaR)
    if abs(xi_eff) < 1e-6:
        cvar_alpha = float(var_alpha + sigma)
    else:
        excess = (sigma + xi_eff * (var_alpha - u)) / (1.0 - xi_eff)
        cvar_alpha = float(var_alpha + excess)

    return var_alpha, cvar_alpha


def compute_actuarial_war_risk_loading_bps(
    cvar_99: float,
    insured_vessel_usd: Optional[float] = None,
    severity_max: Optional[float] = None,
    tail_probability: Optional[float] = None,
    vessel_spec: Optional[VesselProfileSpec] = None,
    gpd_spec: Optional[GPDFitterSpec] = None,
) -> float:
    """Compute Fair War-Risk premium loading in basis points (bps).
    
    1 bps = 0.0001 (0.01%).
    Fair Actuarial Loading = (CVaR_99 / severity_max) * tail_probability * 10,000 bps.
    """
    v_spec = vessel_spec or VesselProfileSpec()
    g_spec = gpd_spec or GPDFitterSpec()

    vessel_usd = v_spec.insured_vessel_usd if insured_vessel_usd is None else float(insured_vessel_usd)
    sev_max = g_spec.severity_max if severity_max is None else float(severity_max)
    tail_prob = g_spec.default_tail_prob if tail_probability is None else float(tail_probability)

    if sev_max <= 0.0 or vessel_usd <= 0.0:
        return 0.0
    loss_fraction = max(0.0, min(float(cvar_99) / float(sev_max), 1.0))
    return float(loss_fraction * tail_prob * 10_000.0)


def fit_pot_gpd(
    data: Sequence[float],
    threshold_u: Optional[float] = None,
    total_observations: Optional[int] = None,
    insured_vessel_usd: Optional[float] = None,
    baseline_anchor: float = 0.0,
    apply_shrinkage: Optional[bool] = None,
    spec: Optional[GPDFitterSpec] = None,
    vessel_spec: Optional[VesselProfileSpec] = None,
    bayes_spec: Optional[EmpiricalBayesSpec] = None,
) -> GPDTailRiskEstimate:
    """Fit Generalized Pareto Distribution (GPD) on positive threshold exceedances.

    Parameters
    ----------
    data : Sequence[float]
        Series of values (e.g. structural shock residuals or incident severities).
    threshold_u : Optional[float]
        Threshold u. If None, adaptively defaults to percentile from spec.
    total_observations : Optional[int]
        Total number of observations T. If None, len(data) is used.
    insured_vessel_usd : Optional[float]
        Vessel insured value for actuarial loading calculation.
    baseline_anchor : float
        Secular trend + seasonal baseline to anchor composite corridor severity.
    apply_shrinkage : Optional[bool]
        Whether to apply Empirical Bayes shrinkage on small samples.
    spec : Optional[GPDFitterSpec]
        GPD fitter hyperparameters. Defaults to GPDFitterSpec().
    vessel_spec : Optional[VesselProfileSpec]
        Vessel profile specification. Defaults to VesselProfileSpec().
    bayes_spec : Optional[EmpiricalBayesSpec]
        Empirical Bayes specification. Defaults to EmpiricalBayesSpec().

    Returns
    -------
    GPDTailRiskEstimate
    """
    g_spec = spec or GPDFitterSpec()
    v_spec = vessel_spec or VesselProfileSpec()
    b_spec = bayes_spec or EmpiricalBayesSpec()

    vessel_usd = v_spec.insured_vessel_usd if insured_vessel_usd is None else float(insured_vessel_usd)
    use_shrinkage = g_spec.apply_shrinkage if apply_shrinkage is None else bool(apply_shrinkage)

    arr = np.asarray(data, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    n_total = len(arr) if total_observations is None else int(total_observations)
    n_total = max(n_total, len(arr), 1)

    if len(arr) == 0:
        u_val = float(threshold_u) if threshold_u is not None else 0.0
        return GPDTailRiskEstimate(
            shape_xi=b_spec.prior_xi,
            scale_sigma=b_spec.prior_sigma,
            threshold_u=u_val,
            exceedance_count=0,
            var_95=u_val,
            var_99=u_val,
            cvar_99=u_val,
            actuarial_war_risk_loading_bps=0.0,
            insured_vessel_usd=vessel_usd,
            residual_var_95=u_val,
            residual_var_99=u_val,
            residual_cvar_99=u_val,
            baseline_anchor=float(baseline_anchor),
            composite_corridor_var_95=float(baseline_anchor + u_val),
            composite_corridor_var_99=float(baseline_anchor + u_val),
            composite_corridor_cvar_99=float(baseline_anchor + u_val),
            shrinkage_weight_w=0.0,
            raw_xi=b_spec.prior_xi,
        )

    # Adaptive quantile selection
    if threshold_u is None:
        p_cut = g_spec.adaptive_percentile_low_n if len(arr) < 50 else g_spec.adaptive_percentile_high_n
        threshold_u = float(np.percentile(arr, p_cut))
    else:
        threshold_u = float(threshold_u)

    exceedances = arr[arr > threshold_u] - threshold_u
    n_u = len(exceedances)

    if n_u == 0:
        return GPDTailRiskEstimate(
            shape_xi=b_spec.prior_xi,
            scale_sigma=b_spec.prior_sigma,
            threshold_u=threshold_u,
            exceedance_count=0,
            var_95=threshold_u,
            var_99=threshold_u,
            cvar_99=threshold_u,
            actuarial_war_risk_loading_bps=0.0,
            insured_vessel_usd=vessel_usd,
            residual_var_95=threshold_u,
            residual_var_99=threshold_u,
            residual_cvar_99=threshold_u,
            baseline_anchor=float(baseline_anchor),
            composite_corridor_var_95=float(baseline_anchor + threshold_u),
            composite_corridor_var_99=float(baseline_anchor + threshold_u),
            composite_corridor_cvar_99=float(baseline_anchor + threshold_u),
            shrinkage_weight_w=0.0,
            raw_xi=b_spec.prior_xi,
        )

    p_u = float(n_u / n_total)
    mean_exc = float(np.mean(exceedances))
    var_exc = float(np.var(exceedances, ddof=1)) if n_u > 1 else 0.0

    # Pathological Guard: Zero variance exceedances (all values identical)
    if var_exc <= 1e-12 or n_u < 3:
        raw_xi = 0.0
        raw_sigma = max(mean_exc, 1e-4)
        xi_shrunk = 0.0
        sigma_shrunk = raw_sigma
        w_weight = 0.0
    else:
        xi_0 = float(np.clip(0.5 * (1.0 - (mean_exc**2) / var_exc), -0.5, g_spec.shape_cap))
        sigma_0 = float(max(0.5 * mean_exc * (1.0 + (mean_exc**2) / var_exc), 1e-4))

        def neg_log_likelihood(params: list[float]) -> float:
            xi_val, sigma_val = params[0], params[1]
            if sigma_val <= 1e-6 or xi_val > g_spec.shape_cap or xi_val < -1.0:
                return 1e12

            if abs(xi_val) < 1e-6:
                return float(n_u * math.log(sigma_val) + np.sum(exceedances) / sigma_val)

            terms = 1.0 + (xi_val * exceedances) / sigma_val
            if np.any(terms <= 0.0):
                return 1e12

            log_terms = np.log(terms)
            return float(n_u * math.log(sigma_val) + (1.0 + 1.0 / xi_val) * np.sum(log_terms))

        try:
            res = minimize(
                neg_log_likelihood,
                [xi_0, sigma_0],
                method="L-BFGS-B",
                bounds=[(-0.5, g_spec.shape_cap), (1e-4, None)],
            )
            if res.success and np.isfinite(res.x[0]) and np.isfinite(res.x[1]):
                raw_xi = float(res.x[0])
                raw_sigma = float(res.x[1])
            else:
                raw_xi = xi_0
                raw_sigma = sigma_0
        except Exception:
            raw_xi = xi_0
            raw_sigma = sigma_0

        # Apply Empirical Bayes shrinkage to avoid small-sample optimizer railing
        if use_shrinkage and n_u < g_spec.small_sample_threshold:
            xi_shrunk, sigma_shrunk, w_weight = shrink_gpd_parameters(exceedances, spec=b_spec)
        else:
            xi_shrunk, sigma_shrunk, w_weight = raw_xi, raw_sigma, 1.0

    xi_shrunk = float(min(max(xi_shrunk, -0.499), g_spec.shape_cap))
    sigma_shrunk = float(max(sigma_shrunk, 0.01))

    # Compute residual shock tail
    res_var_95, _ = compute_gpd_var_cvar(
        threshold_u, xi_shrunk, sigma_shrunk, p_u, alpha=g_spec.secondary_tail_alpha, shape_cap=g_spec.shape_cap
    )
    res_var_99, res_cvar_99 = compute_gpd_var_cvar(
        threshold_u, xi_shrunk, sigma_shrunk, p_u, alpha=g_spec.tail_alpha, shape_cap=g_spec.shape_cap
    )

    # Compute composite corridor severity tail anchored to MSSA baseline
    base = float(baseline_anchor)
    comp_var_95 = base + res_var_95
    comp_var_99 = base + res_var_99
    comp_cvar_99 = base + res_cvar_99

    # Strictly enforce quantile monotonicity: CVaR_99 >= VaR_99 >= VaR_95
    if comp_var_99 < comp_var_95:
        comp_var_99 = comp_var_95
    if comp_cvar_99 < comp_var_99:
        comp_cvar_99 = comp_var_99

    loading_bps = compute_actuarial_war_risk_loading_bps(
        res_cvar_99, insured_vessel_usd=vessel_usd, vessel_spec=v_spec, gpd_spec=g_spec
    )

    return GPDTailRiskEstimate(
        shape_xi=xi_shrunk,
        scale_sigma=sigma_shrunk,
        threshold_u=threshold_u,
        exceedance_count=n_u,
        var_95=res_var_95,
        var_99=res_var_99,
        cvar_99=res_cvar_99,
        actuarial_war_risk_loading_bps=loading_bps,
        insured_vessel_usd=vessel_usd,
        residual_var_95=res_var_95,
        residual_var_99=res_var_99,
        residual_cvar_99=res_cvar_99,
        baseline_anchor=base,
        composite_corridor_var_95=comp_var_95,
        composite_corridor_var_99=comp_var_99,
        composite_corridor_cvar_99=comp_cvar_99,
        shrinkage_weight_w=w_weight,
        raw_xi=raw_xi,
    )


__all__ = [
    "GPDTailRiskEstimate",
    "gpd_cdf",
    "compute_gpd_var_cvar",
    "compute_actuarial_war_risk_loading_bps",
    "fit_pot_gpd",
]
