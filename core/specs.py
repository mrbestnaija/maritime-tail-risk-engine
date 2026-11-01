"""Declarative Immutable Specifications & Configuration Bundles.

Externalizes all geographic, vessel, hydrodynamic, decomposition, tail-risk,
and surveillance parameters into typed, frozen Pydantic specifications.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CORRIDOR_ID = "GOG_BONNY_BRASS_FAIRWAY"
DEFAULT_VESSEL_PROFILE_ID = "STANDARD_SUEZMAX_85M"


class CorridorSpec(BaseModel):
    """Geographic corridor bounds and prior actuarial tail risk parameters."""

    model_config = ConfigDict(frozen=True)

    corridor_id: str = DEFAULT_CORRIDOR_ID
    description: Optional[str] = "Gulf of Guinea (GoG) - Bonny / Brass Fairway"
    latitude_min: float = 4.0
    latitude_max: float = 4.5
    longitude_min: float = 6.5
    longitude_max: float = 7.5
    prior_xi: float = 0.18
    prior_sigma: float = 1.50
    prior_kappa: float = 12.0
    jwc_market_benchmark_bps: float = 15.0


class VesselProfileSpec(BaseModel):
    """Insured vessel financial valuation, operational delay, and exposure factors."""

    model_config = ConfigDict(frozen=True)

    vessel_profile_id: str = DEFAULT_VESSEL_PROFILE_ID
    description: Optional[str] = "Standard Suezmax crude tanker (85M USD insured hull)"
    insured_vessel_usd: float = 85_000_000.0
    daily_demurrage_usd: float = 45_000.0
    daily_escort_cost_usd: float = 18_500.0
    catastrophic_boarding_loss_usd: float = 3_500_000.0
    single_vessel_exposure_factor: float = 0.25
    delay_days_per_cvar_unit: float = 0.85


class HydroEnvelopeSpec(BaseModel):
    """Hydrodynamic small-craft boarding feasibility and swamping physics hyperparameters."""

    model_config = ConfigDict(frozen=True)

    h_0: float = 1.85
    k_w: float = 3.5
    wind_threshold_knots: float = 15.0
    wind_chop_coefficient: float = 0.02
    hazard_scale: float = 10.0
    default_wind_knots: float = 12.0


class MSSASpec(BaseModel):
    """Multivariate Singular Spectrum Analysis (MSSA) decomposition hyperparameters."""

    model_config = ConfigDict(frozen=True)

    window_length: Optional[int] = 10
    window_length_divisor: int = 3
    default_window_length: int = 10
    trend_components: Sequence[int] = (0,)
    seasonal_components: Sequence[int] = (1, 2)
    risk_threshold: float = 4.5
    benign_residual_threshold: float = 0.5


class EmpiricalBayesSpec(BaseModel):
    """Empirical Bayes GPD parameter shrinkage hyperparameters."""

    model_config = ConfigDict(frozen=True)

    prior_xi: float = 0.18
    prior_sigma: float = 1.50
    kappa: float = 12.0


class GPDFitterSpec(BaseModel):
    """Peaks-Over-Threshold (POT) Generalized Pareto Distribution fitting hyperparameters."""

    model_config = ConfigDict(frozen=True)

    threshold_u: Optional[float] = None
    shape_cap: float = 0.95
    exponential_limit_threshold: float = 1e-6
    tail_alpha: float = 0.99
    secondary_tail_alpha: float = 0.95
    adaptive_percentile_low_n: float = 75.0
    adaptive_percentile_high_n: float = 85.0
    small_sample_threshold: int = 25
    severity_max: float = 10.0
    apply_shrinkage: bool = True
    default_tail_prob: float = 0.01


class SPRTSpec(BaseModel):
    """Wald's Sequential Probability Ratio Test (SPRT) surveillance gate hyperparameters."""

    model_config = ConfigDict(frozen=True)

    p0: float = 0.05
    p1: float = 0.20
    alpha: float = 0.05
    beta: float = 0.10


class EngineConfigBundle(BaseModel):
    """Complete consolidated configuration bundle for the Maritime Tail Risk Engine."""

    model_config = ConfigDict(frozen=True)

    corridor: CorridorSpec = Field(default_factory=CorridorSpec)
    vessel: VesselProfileSpec = Field(default_factory=VesselProfileSpec)
    hydro: HydroEnvelopeSpec = Field(default_factory=HydroEnvelopeSpec)
    mssa: MSSASpec = Field(default_factory=MSSASpec)
    bayes: EmpiricalBayesSpec = Field(default_factory=EmpiricalBayesSpec)
    gpd: GPDFitterSpec = Field(default_factory=GPDFitterSpec)
    sprt: SPRTSpec = Field(default_factory=SPRTSpec)


def load_corridor_spec(corridor_id: str, config_dir: str | Path = "configs") -> CorridorSpec:
    """Load CorridorSpec from declarative JSON configuration directory."""
    path = Path(config_dir) / "corridors.json"
    if not path.exists():
        if corridor_id == DEFAULT_CORRIDOR_ID:
            return CorridorSpec()
        raise FileNotFoundError(f"Corridors config file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if corridor_id not in data:
        raise KeyError(f"Corridor '{corridor_id}' not found in {path}. Available: {list(data.keys())}")
    return CorridorSpec(**data[corridor_id])


def load_vessel_spec(vessel_profile_id: str, config_dir: str | Path = "configs") -> VesselProfileSpec:
    """Load VesselProfileSpec from declarative JSON configuration directory."""
    path = Path(config_dir) / "vessel_profiles.json"
    if not path.exists():
        if vessel_profile_id == DEFAULT_VESSEL_PROFILE_ID:
            return VesselProfileSpec()
        raise FileNotFoundError(f"Vessel profiles config file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if vessel_profile_id not in data:
        raise KeyError(
            f"Vessel profile '{vessel_profile_id}' not found in {path}. Available: {list(data.keys())}"
        )
    return VesselProfileSpec(**data[vessel_profile_id])


def load_model_hyperparams(config_dir: str | Path = "configs") -> dict[str, Any]:
    """Load model hyperparameters dict from declarative JSON configuration directory."""
    path = Path(config_dir) / "model_hyperparams.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_engine_bundle(
    corridor_id: str = DEFAULT_CORRIDOR_ID,
    vessel_profile_id: str = DEFAULT_VESSEL_PROFILE_ID,
    config_dir: str | Path = "configs",
) -> EngineConfigBundle:
    """Load complete EngineConfigBundle from declarative JSON configs."""
    corridor_spec = load_corridor_spec(corridor_id, config_dir=config_dir)
    vessel_spec = load_vessel_spec(vessel_profile_id, config_dir=config_dir)
    raw_hyper = load_model_hyperparams(config_dir=config_dir)

    hydro_spec = HydroEnvelopeSpec(**raw_hyper.get("hydrodynamics", {}))
    mssa_spec = MSSASpec(**raw_hyper.get("mssa", {}))
    bayes_spec = EmpiricalBayesSpec(
        prior_xi=corridor_spec.prior_xi,
        prior_sigma=corridor_spec.prior_sigma,
        kappa=corridor_spec.prior_kappa,
    )
    gpd_spec = GPDFitterSpec(**raw_hyper.get("gpd", {}))
    sprt_spec = SPRTSpec(**raw_hyper.get("sprt", {}))

    return EngineConfigBundle(
        corridor=corridor_spec,
        vessel=vessel_spec,
        hydro=hydro_spec,
        mssa=mssa_spec,
        bayes=bayes_spec,
        gpd=gpd_spec,
        sprt=sprt_spec,
    )


__all__ = [
    "DEFAULT_CORRIDOR_ID",
    "DEFAULT_VESSEL_PROFILE_ID",
    "CorridorSpec",
    "VesselProfileSpec",
    "HydroEnvelopeSpec",
    "MSSASpec",
    "EmpiricalBayesSpec",
    "GPDFitterSpec",
    "SPRTSpec",
    "EngineConfigBundle",
    "load_corridor_spec",
    "load_vessel_spec",
    "load_model_hyperparams",
    "load_engine_bundle",
]
