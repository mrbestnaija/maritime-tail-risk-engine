"""Hydrodynamic Small-Craft Boarding Physics & Swamping Envelope.

Models the physical hydrodynamic constraints of small pirate skiffs (PAGs) operating
in the Gulf of Guinea (Bonny & Brass Fairway approach):
- Logistic swamping transition curve: small skiffs swamp rapidly when H_s > 1.85m.
- Wind chop compounding: sustained winds > 15 knots elevate effective wave hazard.
- Composite dark vessel attack hazard: combines radar dark vessel presence with
  real-time sea-state boarding feasibility.

Pure domain math: ZERO I/O, ZERO PRINT, pure NumPy/math.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


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
    wind_knots: float = 12.0,
    h_0: float = 1.85,
    k_w: float = 3.5,
) -> float:
    """Compute physical small-skiff boarding feasibility via logistic swamping curve.

    Parameters
    ----------
    wave_height_m : float
        Significant wave height H_s (meters).
    wind_knots : float
        Surface wind speed (knots). Sustained wind > 15 kts adds chop.
    h_0 : float
        Median swamping wave height threshold (default: 1.85m).
    k_w : float
        Steepness parameter of the logistic curve (default: 3.5).

    Returns
    -------
    float
        Boarding probability in [0.0, 1.0].
    """
    hs = max(float(wave_height_m), 0.0)
    wind = max(float(wind_knots), 0.0)

    # Wind chop elevation: each knot above 15 kts adds 0.02m effective roughness
    wind_chop = 0.02 * max(0.0, wind - 15.0)
    hs_eff = hs + wind_chop

    # Logistic swamping function: P = 1 / (1 + exp(k_w * (hs_eff - h_0)))
    exponent = k_w * (hs_eff - h_0)
    exponent_clamped = max(min(exponent, 50.0), -50.0)
    feasibility = 1.0 / (1.0 + math.exp(exponent_clamped))

    return float(max(min(feasibility, 1.0), 0.0))


def composite_dark_vessel_hazard(
    wave_height_m: float,
    sar_dark_ratio: float,
    wind_knots: float = 12.0,
) -> float:
    """Compute composite fairway attack hazard on [0.0, 10.0] scale.

    Hazard peaks when high dark-vessel radar activity coincides with calm sea-states.
    """
    feasibility = skiff_boarding_feasibility(wave_height_m, wind_knots=wind_knots)
    dark_ratio = max(min(float(sar_dark_ratio), 1.0), 0.0)
    hazard = 10.0 * feasibility * dark_ratio
    return float(max(min(hazard, 10.0), 0.0))


def evaluate_hydrodynamic_envelope(
    wave_height_m: float,
    sar_dark_ratio: float,
    wind_knots: float = 12.0,
) -> HydrodynamicEnvelopeResult:
    """Evaluate complete hydrodynamic boarding and dark vessel hazard profile."""
    hs = max(float(wave_height_m), 0.0)
    wind = max(float(wind_knots), 0.0)
    hs_eff = hs + 0.02 * max(0.0, wind - 15.0)
    feasibility = skiff_boarding_feasibility(hs, wind_knots=wind)
    dark_ratio = max(min(float(sar_dark_ratio), 1.0), 0.0)
    hazard = 10.0 * feasibility * dark_ratio

    return HydrodynamicEnvelopeResult(
        significant_wave_height_m=hs,
        wind_knots=wind,
        effective_wave_height_m=hs_eff,
        boarding_feasibility=feasibility,
        sar_dark_vessel_ratio=dark_ratio,
        composite_hazard_score=hazard,
    )
