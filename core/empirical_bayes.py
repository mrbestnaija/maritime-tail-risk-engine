"""Empirical Bayes GPD Parameter Shrinkage.

Prevents small-sample optimizer railing at xi = -0.5000 by estimating local
Probability-Weighted Moments (PWM / Hosking-Wallis) and shrinking parameters
toward the historical Gulf of Guinea maritime tail prior (xi_0 = 0.18, sigma_0 = 1.5).

Mathematical Formulation:
- Sample PWM: a_1 = (1 / N_u) * sum_{i=1}^{N_u} ((N_u - i) / (N_u - 1)) * y_{(i)}
- Local PWM estimates:
    xi_local = 2 - y_mean / (y_mean - 2 * a_1)
    sigma_local = (2 * y_mean * a_1) / (y_mean - 2 * a_1)
- Shrinkage weight: w = N_u / (N_u + kappa)
- Shrunk estimates:
    xi_shrunk = w * xi_local + (1 - w) * xi_0
    sigma_shrunk = w * sigma_local + (1 - w) * sigma_0

Pure domain math: ZERO I/O, ZERO PRINT, pure NumPy.
"""

from __future__ import annotations

import numpy as np


def shrink_gpd_parameters(
    local_exceedances: np.ndarray | list[float],
    prior_xi: float = 0.18,
    prior_sigma: float = 1.5,
    kappa: float = 12.0,
) -> tuple[float, float, float]:
    """Estimate and shrink GPD parameters via Empirical Bayes.

    Parameters
    ----------
    local_exceedances : np.ndarray | list[float]
        Positive exceedances above threshold: y = r_t - u > 0.
    prior_xi : float
        Prior GPD shape parameter for Gulf of Guinea fairway (default: 0.18).
    prior_sigma : float
        Prior GPD scale parameter (default: 1.5).
    kappa : float
        Shrinkage weight parameter (degrees of freedom for prior, default: 12.0).

    Returns
    -------
    tuple[float, float, float]
        (xi_shrunk, sigma_shrunk, shrinkage_weight_w)
    """
    arr = np.asarray(local_exceedances, dtype=np.float64)
    arr = arr[np.isfinite(arr) & (arr > 0.0)]
    n_u = len(arr)

    # Empty or single-observation edge case: return exact prior
    if n_u < 2:
        return float(prior_xi), float(prior_sigma), 0.0

    # Sort ascending for PWM calculation
    y_sorted = np.sort(arr)
    y_mean = float(np.mean(y_sorted))

    # Variance guard: identical exceedances
    if float(np.std(y_sorted)) < 1e-9:
        w = float(n_u / (n_u + kappa))
        xi_shrunk = float(w * 0.0 + (1.0 - w) * prior_xi)
        sigma_shrunk = float(w * max(y_mean, 0.1) + (1.0 - w) * prior_sigma)
        return xi_shrunk, sigma_shrunk, w

    # Calculate Probability-Weighted Moment a_1 (Hosking & Wallis 1987)
    # a_1 = (1 / n_u) * sum_{j=0}^{n_u - 1} ((n_u - 1 - j) / (n_u - 1)) * y_sorted[j]
    weights = (n_u - 1 - np.arange(n_u, dtype=np.float64)) / float(n_u - 1)
    a_1 = float(np.sum(weights * y_sorted) / float(n_u))

    denom = y_mean - 2.0 * a_1

    # Invert PWM equations for Generalized Pareto Distribution
    if abs(denom) < 1e-9 or denom <= 0.0:
        xi_local = 0.0
        sigma_local = y_mean
    else:
        xi_local = 2.0 - (y_mean / denom)
        sigma_local = (2.0 * y_mean * a_1) / denom

    # Bound local estimates before shrinkage to prevent numerical explosion
    if not np.isfinite(xi_local) or xi_local < -0.5:
        xi_local = -0.5
    elif xi_local > 0.95:
        xi_local = 0.95

    if not np.isfinite(sigma_local) or sigma_local <= 0.0:
        sigma_local = max(y_mean, 0.1)

    # Apply Empirical Bayes shrinkage
    w = float(n_u / (n_u + kappa))
    xi_shrunk = float(w * xi_local + (1.0 - w) * prior_xi)
    sigma_shrunk = float(w * sigma_local + (1.0 - w) * prior_sigma)

    # Final domain bounds
    xi_shrunk = min(max(xi_shrunk, -0.499), 0.95)
    sigma_shrunk = max(sigma_shrunk, 0.01)

    return xi_shrunk, sigma_shrunk, w
