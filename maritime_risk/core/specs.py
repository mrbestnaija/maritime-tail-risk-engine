"""Declarative Immutable Specifications & Configuration Bundles.

Externalizes all geographic, vessel, hydrodynamic, decomposition, tail-risk,
and surveillance parameters into typed, frozen Pydantic specifications.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field, root_validator

DEFAULT_CORRIDOR_ID = "GOG_BONNY_BRASS_FAIRWAY"
DEFAULT_VESSEL_PROFILE_ID = "STANDARD_SUEZMAX_85M"

VALID_OPERATIONAL_STATES: tuple[str, ...] = (
    "UNDERWAY",
    "UNDERWAY_LONE",
    "UNDERWAY_ESCORTED",
    "AT_ANCHOR",
    "AT_ANCHOR_SECURED",
    "AT_ANCHOR_UNPROTECTED",
)


class CorridorSpec(BaseModel):
    """Geographic corridor bounds and prior actuarial tail risk parameters."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    corridor_id: str = DEFAULT_CORRIDOR_ID
    description: Optional[str] = "Gulf of Guinea (GoG) - Bonny / Brass Fairway"
    name: Optional[str] = None
    latitude_min: float = 4.0
    latitude_max: float = 4.5
    longitude_min: float = 6.5
    longitude_max: float = 7.5
    min_latitude: Optional[float] = None
    max_latitude: Optional[float] = None
    min_longitude: Optional[float] = None
    max_longitude: Optional[float] = None
    prior_xi: float = 0.18
    prior_sigma: float = 1.50
    prior_kappa: float = 12.0
    jwc_market_benchmark_bps: float = 15.0
    operational_state: str = "UNDERWAY"
    incident_dataset_path: Optional[str] = None
    telemetry_dataset_path: Optional[str] = None

    @root_validator(pre=True)
    def _normalize_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            data = dict(values)
            # lat/lon mappings
            if "min_latitude" in data and "latitude_min" not in data:
                data["latitude_min"] = data["min_latitude"]
            elif "latitude_min" in data and "min_latitude" not in data:
                data["min_latitude"] = data["latitude_min"]

            if "max_latitude" in data and "latitude_max" not in data:
                data["latitude_max"] = data["max_latitude"]
            elif "latitude_max" in data and "max_latitude" not in data:
                data["max_latitude"] = data["latitude_max"]

            if "min_longitude" in data and "longitude_min" not in data:
                data["longitude_min"] = data["min_longitude"]
            elif "longitude_min" in data and "min_longitude" not in data:
                data["min_longitude"] = data["longitude_min"]

            if "max_longitude" in data and "longitude_max" not in data:
                data["longitude_max"] = data["max_longitude"]
            elif "longitude_max" in data and "max_longitude" not in data:
                data["max_longitude"] = data["longitude_max"]

            # name / description mappings
            if "name" in data and ("description" not in data or not data.get("description")):
                data["description"] = data["name"]
            elif "description" in data and ("name" not in data or not data.get("name")):
                data["name"] = data["description"]
            return data
        return values


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
    freeboard_meters: float = 8.2
    max_sustained_speed_knots: float = 16.5
    pms_guards_present: bool = True


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
    xi_max: float = 0.95


class GPDFitterSpec(BaseModel):
    """Peaks-Over-Threshold (POT) Generalized Pareto Distribution fitting hyperparameters."""

    model_config = ConfigDict(frozen=True)

    threshold_u: Optional[float] = None
    xi_max: float = 0.95
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


class CoxHazardSpec(BaseModel):
    """Cox proportional hazards voyage breach hyperparameters."""

    model_config = ConfigDict(frozen=True)

    baseline_hazard_underway: float = 0.0005
    baseline_hazard_escorted: float = 0.00015
    baseline_hazard_anchor: float = 0.0002
    baseline_hazard_anchor_secured: float = 0.00010
    baseline_hazard_anchor_unprotected: float = 0.00045
    baseline_daily_hazard: float = 0.0005
    escort_hazard_suppression_ratio: float = 0.30
    escort_daily_rate_usd: float = 18500.0
    beta_mli: float = 2.85
    beta_pmsc_distance_km: float = 0.004
    beta_ohi: float = -0.15
    beta_hydro_feasibility: float = 0.75
    ohi_freeboard_weight: float = 0.40
    ohi_speed_weight: float = 0.40
    ohi_armed_guard_weight: float = 2.00
    voyage_window_days: float = 7.0
    commercial_baseline_bps: float = 1.0


class MacroGPDScaleSpec(BaseModel):
    """Macro-modulated GPD scale hyperparameters."""

    model_config = ConfigDict(frozen=True)

    macro_residual_alpha: float = 0.30
    max_scale_multiplier: float = 5.0
    mli_inflection_threshold: float = 0.65


class MacroRegimeSpec(BaseModel):
    """Macro-economic liquidity friction (port congestion) regime hyperparameters."""

    model_config = ConfigDict(frozen=True)

    baseline_port_wait_hours: float = 24.0
    congestion_shock_alpha: float = 0.50
    max_regime_multiplier: float = 2.0


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
    cox: CoxHazardSpec = Field(default_factory=CoxHazardSpec)
    macro_gpd: MacroGPDScaleSpec = Field(default_factory=MacroGPDScaleSpec)
    macro_regime: MacroRegimeSpec = Field(default_factory=MacroRegimeSpec)


def _resolve_config_path(filename: str, config_dir: str | Path | None = None) -> Path:
    """Resolve declarative configuration file path with package fallback."""
    if config_dir is not None:
        explicit_path = Path(config_dir) / filename
        if explicit_path.exists():
            return explicit_path

    cwd_path = Path("configs") / filename
    if cwd_path.exists():
        return cwd_path

    pkg_configs_dir = Path(__file__).resolve().parent.parent / "configs" / filename
    if pkg_configs_dir.exists():
        return pkg_configs_dir

    repo_configs_dir = Path(__file__).resolve().parent.parent.parent / "configs" / filename
    if repo_configs_dir.exists():
        return repo_configs_dir

    return Path(config_dir or "configs") / filename


def load_corridor_spec(corridor_id: str, config_dir: str | Path = "configs") -> CorridorSpec:
    """Load CorridorSpec from declarative JSON configuration directory."""
    path = _resolve_config_path("corridors.json", config_dir)
    if not path.exists():
        if corridor_id == DEFAULT_CORRIDOR_ID:
            return CorridorSpec()
        raise FileNotFoundError(f"Corridors config file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    corridors_map = data.get("corridors", data)
    if corridor_id not in corridors_map:
        raise KeyError(f"Corridor '{corridor_id}' not found in {path}. Available: {list(corridors_map.keys())}")
    return CorridorSpec(**corridors_map[corridor_id])


def load_vessel_spec(vessel_profile_id: str, config_dir: str | Path = "configs") -> VesselProfileSpec:
    """Load VesselProfileSpec from declarative JSON configuration directory."""
    path = _resolve_config_path("vessel_profiles.json", config_dir)
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
    path = _resolve_config_path("model_hyperparams.json", config_dir)
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
    gpd_spec = GPDFitterSpec(**raw_hyper.get("gpd", {}))
    bayes_spec = EmpiricalBayesSpec(
        prior_xi=corridor_spec.prior_xi,
        prior_sigma=corridor_spec.prior_sigma,
        kappa=corridor_spec.prior_kappa,
        xi_max=gpd_spec.xi_max,
    )
    sprt_spec = SPRTSpec(**raw_hyper.get("sprt", {}))
    cox_spec = CoxHazardSpec(**raw_hyper.get("cox_hazard", {}))
    macro_gpd_spec = MacroGPDScaleSpec(**raw_hyper.get("macro_gpd_scale", {}))
    macro_regime_spec = MacroRegimeSpec(**raw_hyper.get("macro_regime", {}))

    return EngineConfigBundle(
        corridor=corridor_spec,
        vessel=vessel_spec,
        hydro=hydro_spec,
        mssa=mssa_spec,
        bayes=bayes_spec,
        gpd=gpd_spec,
        sprt=sprt_spec,
        cox=cox_spec,
        macro_gpd=macro_gpd_spec,
        macro_regime=macro_regime_spec,
    )


__all__ = [
    "DEFAULT_CORRIDOR_ID",
    "DEFAULT_VESSEL_PROFILE_ID",
    "VALID_OPERATIONAL_STATES",
    "CorridorSpec",
    "VesselProfileSpec",
    "HydroEnvelopeSpec",
    "MSSASpec",
    "EmpiricalBayesSpec",
    "GPDFitterSpec",
    "SPRTSpec",
    "CoxHazardSpec",
    "MacroGPDScaleSpec",
    "MacroRegimeSpec",
    "EngineConfigBundle",
    "load_corridor_spec",
    "load_vessel_spec",
    "load_model_hyperparams",
    "load_engine_bundle",
]
