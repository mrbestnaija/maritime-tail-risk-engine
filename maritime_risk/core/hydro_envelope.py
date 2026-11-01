"""Hydrodynamic Small-Craft Boarding Physics & Swamping Envelope.

Models the physical hydrodynamic constraints of small pirate skiffs (PAGs) operating
in maritime security corridors:
- Logistic swamping transition curve: small skiffs swamp rapidly when wave height exceeds threshold.
- Wind chop compounding: sustained winds above threshold elevate effective wave hazard.
- Composite dark vessel attack hazard: combines radar dark vessel presence with
  real-time sea-state boarding feasibility.

Pure domain math: ZERO I/O, ZERO PRINT, pure NumPy/math.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from .specs import HydroEnvelopeSpec


@dataclass(frozen=True)
class HydrodynamicEnvelopeResult:
    """Immutable domain container for hydrodynamic boarding feasibility."""

    significant_wave_height_m: float
    wind_knots: float
    effective_wave_height_m: float
    boarding_feasibility: float
    sar_dark_vessel_ratio: float
    composite_hazard_score: float


def skiff_boarding_feasibility(
    wave_height_m: float,
    wind_knots: Optional[float] = None,
    h_0: Optional[float] = None,
    k_w: Optional[float] = None,
    spec: Optional[HydroEnvelopeSpec] = None,
) -> float:
    """Compute physical small-skiff boarding feasibility via logistic swamping curve.

    Parameters
    ----------
    wave_height_m : float
        Significant wave height H_s (meters).
    wind_knots : Optional[float]
        Surface wind speed (knots). Sustained wind adds chop.
    h_0 : Optional[float]
        Median swamping wave height threshold.
    k_w : Optional[float]
        Steepness parameter of the logistic curve.
    spec : Optional[HydroEnvelopeSpec]
        Hydrodynamic specification. Defaults to HydroEnvelopeSpec().

    Returns
    -------
    float
        Boarding probability in [0.0, 1.0].
    """
    h_spec = spec or HydroEnvelopeSpec()
    wind_val = h_spec.default_wind_knots if wind_knots is None else wind_knots
    h_0_val = h_spec.h_0 if h_0 is None else h_0
    k_w_val = h_spec.k_w if k_w is None else k_w

    hs = max(float(wave_height_m), 0.0)
    wind = max(float(wind_val), 0.0)

    # Wind chop elevation
    wind_chop = h_spec.wind_chop_coefficient * max(0.0, wind - h_spec.wind_threshold_knots)
    hs_eff = hs + wind_chop

    # Logistic swamping function: P = 1 / (1 + exp(k_w * (hs_eff - h_0)))
    exponent = k_w_val * (hs_eff - h_0_val)
    exponent_clamped = max(min(exponent, 50.0), -50.0)
    feasibility = 1.0 / (1.0 + math.exp(exponent_clamped))

    return float(max(min(feasibility, 1.0), 0.0))


def composite_dark_vessel_hazard(
    wave_height_m: float,
    sar_dark_ratio: float,
    wind_knots: Optional[float] = None,
    spec: Optional[HydroEnvelopeSpec] = None,
) -> float:
    """Compute composite fairway attack hazard on [0.0, 10.0] scale.

    Hazard peaks when high dark-vessel radar activity coincides with calm sea-states.
    """
    h_spec = spec or HydroEnvelopeSpec()
    feasibility = skiff_boarding_feasibility(wave_height_m, wind_knots=wind_knots, spec=h_spec)
    dark_ratio = max(min(float(sar_dark_ratio), 1.0), 0.0)
    hazard = h_spec.hazard_scale * feasibility * dark_ratio
    return float(max(min(hazard, h_spec.hazard_scale), 0.0))


def evaluate_hydrodynamic_envelope(
    wave_height_m: float,
    sar_dark_ratio: float,
    wind_knots: Optional[float] = None,
    spec: Optional[HydroEnvelopeSpec] = None,
) -> HydrodynamicEnvelopeResult:
    """Evaluate complete hydrodynamic boarding and dark vessel hazard profile."""
    h_spec = spec or HydroEnvelopeSpec()
    wind_val = h_spec.default_wind_knots if wind_knots is None else wind_knots
    hs = max(float(wave_height_m), 0.0)
    wind = max(float(wind_val), 0.0)
    hs_eff = hs + h_spec.wind_chop_coefficient * max(0.0, wind - h_spec.wind_threshold_knots)
    feasibility = skiff_boarding_feasibility(hs, wind_knots=wind, spec=h_spec)
    dark_ratio = max(min(float(sar_dark_ratio), 1.0), 0.0)
    hazard = h_spec.hazard_scale * feasibility * dark_ratio

    return HydrodynamicEnvelopeResult(
        significant_wave_height_m=hs,
        wind_knots=wind,
        effective_wave_height_m=hs_eff,
        boarding_feasibility=feasibility,
        sar_dark_vessel_ratio=dark_ratio,
        composite_hazard_score=hazard,
    )


__all__ = [
    "HydrodynamicEnvelopeResult",
    "skiff_boarding_feasibility",
    "composite_dark_vessel_hazard",
    "evaluate_hydrodynamic_envelope",
]
