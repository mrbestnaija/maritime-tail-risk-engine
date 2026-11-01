"""Macro-Economic Liquidity Friction (Port Congestion) Regime-Switching Engine.

Calculates the forward-looking regime multiplier scaling actuarial Joint War Committee (JWC)
Additional Premium (AP) based on empirical port waiting times and queue friction.

Mathematical Formulation:
    Multiplier = 1.0 + min(
        spec.max_regime_multiplier - 1.0,
        spec.congestion_shock_alpha * max(0.0, (current_wait - baseline_wait) / baseline_wait)
    )

Pure domain math: ZERO I/O, ZERO PRINT, pure Python/math.
"""

from __future__ import annotations

import math
from typing import Optional

from .specs import MacroRegimeSpec


def compute_regime_multiplier(
    current_wait_hours: float,
    spec: Optional[MacroRegimeSpec] = None,
) -> float:
    """Calculate forward-looking liquidity friction regime multiplier.

    Parameters
    ----------
    current_wait_hours : float
        Observed or median anchorage/port waiting duration in hours.
    spec : Optional[MacroRegimeSpec]
        Macro regime hyperparameters. Defaults to MacroRegimeSpec().

    Returns
    -------
    float
        Regime multiplier bounded in [1.0, spec.max_regime_multiplier].
    """
    m_spec = spec or MacroRegimeSpec()
    if m_spec.baseline_port_wait_hours <= 0.0:
        return 1.0
    if current_wait_hours is None or math.isnan(current_wait_hours):
        return 1.0

    current = float(current_wait_hours)
    baseline = float(m_spec.baseline_port_wait_hours)
    if current <= baseline:
        return 1.0

    congestion_ratio = (current - baseline) / baseline
    excess_shock = m_spec.congestion_shock_alpha * max(0.0, congestion_ratio)
    max_excess = max(0.0, m_spec.max_regime_multiplier - 1.0)
    multiplier = 1.0 + min(max_excess, excess_shock)
    return float(multiplier)


__all__ = ["compute_regime_multiplier"]
