"""Empirical Bayes GPD Parameter Shrinkage.

Prevents small-sample optimizer railing at xi = -0.5000 by estimating local
Probability-Weighted Moments (PWM / Hosking-Wallis) and shrinking parameters
toward the historical corridor maritime tail prior.

Mathematical Formulation:
- Sample PWM: a_1 = (1 / N_u) * sum_{i=1}^{N_u} ((N_u - i) / (N_u - 1)) * y_{(i)}
- Local PWM estimates (Pickands / EVT positive heavy-tail convention xi = -k):
    xi_local = y_mean / (y_mean - 2 * a_1) - 2.0
    sigma_local = (2 * y_mean * a_1) / (y_mean - 2 * a_1)
- Shrinkage weight: w = N_u / (N_u + kappa)
- Shrunk estimates:
    xi_shrunk = w * xi_local + (1 - w) * xi_0
    sigma_shrunk = w * sigma_local + (1 - w) * sigma_0

Pure domain math: ZERO I/O, ZERO PRINT, pure NumPy.
"""

from __future__ import annotations

from typing import Optional
import numpy as np

from .specs import EmpiricalBayesSpec


def shrink_gpd_parameters(
    local_exceedances: np.ndarray | list[float],
    prior_xi: Optional[float] = None,
    prior_sigma: Optional[float] = None,
    kappa: Optional[float] = None,
    spec: Optional[EmpiricalBayesSpec] = None,
) -> tuple[float, float, float]:
    """Estimate and shrink GPD parameters via Empirical Bayes.

    Parameters
    ----------
    local_exceedances : np.ndarray | list[float]
        Positive exceedances above threshold: y = r_t - u > 0.
    prior_xi : Optional[float]
        Prior GPD shape parameter for maritime fairway.
    prior_sigma : Optional[float]
        Prior GPD scale parameter.
    kappa : Optional[float]
        Shrinkage weight parameter (degrees of freedom for prior).
    spec : Optional[EmpiricalBayesSpec]
        Empirical Bayes specification. Defaults to EmpiricalBayesSpec().

    Returns
    -------
    tuple[float, float, float]
        (xi_shrunk, sigma_shrunk, shrinkage_weight_w)
    """
    b_spec = spec or EmpiricalBayesSpec()
    p_xi = b_spec.prior_xi if prior_xi is None else float(prior_xi)
    p_sigma = b_spec.prior_sigma if prior_sigma is None else float(prior_sigma)
    p_kappa = b_spec.kappa if kappa is None else float(kappa)

    arr = np.asarray(local_exceedances, dtype=np.float64)
    arr = arr[np.isfinite(arr) & (arr > 0.0)]
    n_u = len(arr)

    # Empty or single-observation edge case: return exact prior
    if n_u < 2:
        return float(p_xi), float(p_sigma), 0.0

    # Sort ascending for PWM calculation
    y_sorted = np.sort(arr)
    y_mean = float(np.mean(y_sorted))

    # Variance guard: identical exceedances
    if float(np.std(y_sorted)) < 1e-9:
        w = float(n_u / (n_u + p_kappa))
        xi_shrunk = float(w * 0.0 + (1.0 - w) * p_xi)
        sigma_shrunk = float(w * max(y_mean, 0.1) + (1.0 - w) * p_sigma)
        return xi_shrunk, sigma_shrunk, w

    # Calculate Probability-Weighted Moment a_1 (Hosking & Wallis 1987)
    weights = (n_u - 1 - np.arange(n_u, dtype=np.float64)) / float(n_u - 1)
    a_1 = float(np.sum(weights * y_sorted) / float(n_u))

    denom = y_mean - 2.0 * a_1

    # Invert PWM equations for Generalized Pareto Distribution.
    if abs(denom) < 1e-9 or denom <= 0.0:
        xi_local = 0.0
        sigma_local = y_mean
    else:
        xi_local = (y_mean / denom) - 2.0
        sigma_local = (2.0 * y_mean * a_1) / denom

    # Bound local estimates before shrinkage to prevent numerical explosion
    if not np.isfinite(xi_local):
        xi_local = 0.0
    else:
        xi_local = min(max(xi_local, -0.25), 0.65)

    if not np.isfinite(sigma_local) or sigma_local <= 0.0:
        sigma_local = max(y_mean, 0.1)

    # Apply Empirical Bayes shrinkage against historical maritime tail prior
    w = float(n_u / (n_u + p_kappa))
    xi_shrunk = float(w * xi_local + (1.0 - w) * p_xi)
    sigma_shrunk = float(w * sigma_local + (1.0 - w) * p_sigma)

    # Final domain bounds ensuring heavy-tail shrinkage band [0.05, 0.25]
    xi_shrunk = min(max(xi_shrunk, 0.05), 0.25)

    return float(xi_shrunk), float(sigma_shrunk), float(w)


__all__ = ["shrink_gpd_parameters"]
