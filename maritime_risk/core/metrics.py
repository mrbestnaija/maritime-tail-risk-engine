"""Core Quantitative Tail Risk Metrics.

Calculates:
- Value at Risk (VaR_alpha)
- Conditional Value at Risk (CVaR_alpha / Expected Shortfall)
- Interval severity distributions
- Pure domain logic with ZERO dependencies on application or infrastructure layers.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence
from .gpd_tail_fitter import (
    GPDTailRiskEstimate,
    compute_actuarial_war_risk_loading_bps,
    compute_gpd_var_cvar,
    fit_pot_gpd,
    gpd_cdf,
)
from .models import MaritimeIncident, SeverityInterval


def compute_var(values: Sequence[float], alpha: float = 0.99) -> float:
    """Compute empirical Value at Risk (VaR) at confidence level alpha."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    index = int(math.ceil(alpha * n)) - 1
    index = max(0, min(index, n - 1))
    return float(sorted_vals[index])


def compute_cvar(values: Sequence[float], alpha: float = 0.99) -> float:
    """Compute empirical Conditional Value at Risk (CVaR / Expected Shortfall) at confidence level alpha.
    
    CVaR_alpha is the conditional expectation of losses exceeding VaR_alpha.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    var = compute_var(values, alpha)
    tail_losses = [v for v in sorted_vals if v >= var]
    if not tail_losses:
        return var
    return float(sum(tail_losses) / len(tail_losses))


def compute_tail_risk_profile(
    incidents: Sequence[MaritimeIncident],
    alpha: float = 0.99,
) -> dict[str, float]:
    """Compute tail risk underwriting metrics using both lower and upper severity bounds."""
    if not incidents:
        return {
            "incident_count": 0,
            "min_var_99": 0.0,
            "max_var_99": 0.0,
            "min_cvar_99": 0.0,
            "max_cvar_99": 0.0,
            "mean_severity_min": 0.0,
            "mean_severity_max": 0.0,
        }

    min_severities = [inc.severity.min_severity for inc in incidents]
    max_severities = [inc.severity.max_severity for inc in incidents]

    return {
        "incident_count": len(incidents),
        "min_var_99": compute_var(min_severities, alpha),
        "max_var_99": compute_var(max_severities, alpha),
        "min_cvar_99": compute_cvar(min_severities, alpha),
        "max_cvar_99": compute_cvar(max_severities, alpha),
        "mean_severity_min": float(sum(min_severities) / len(min_severities)),
        "mean_severity_max": float(sum(max_severities) / len(max_severities)),
    }
