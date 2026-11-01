"""Maritime Tail Risk Engine: Modular Monolith Domain Core."""

from core.calibration import (
    IsotonicCalibrator,
    PlattCalibrator,
    brier_score,
    calibrate_exceedance_probabilities,
    log_loss,
)
from core.empirical_bayes import shrink_gpd_parameters
from core.gpd_tail_fitter import (
    GPDTailRiskEstimate,
    compute_actuarial_war_risk_loading_bps,
    compute_gpd_var_cvar,
    fit_pot_gpd,
    gpd_cdf,
)
from core.hydro_envelope import (
    HydrodynamicEnvelopeResult,
    composite_dark_vessel_hazard,
    evaluate_hydrodynamic_envelope,
    skiff_boarding_feasibility,
)
from core.jwc_pricer import (
    JWCPriceResult,
    JWCPricingResult,
    compute_jwc_7day_war_risk_ap,
    price_jwc_7day_transit,
)
from core.models import (
    CivilianSensorTelemetry,
    GeoCoordinates,
    MaritimeIncident,
    SeverityInterval,
    TemporalParadoxError,
)
from core.mssa_decomposer import (
    MSSADecompositionResult,
    decompose_mssa,
    hankel_diagonal_averaging,
)
from core.ports import (
    ActuarialPricerPort,
    AuditSinkPort,
    IncidentSourcePort,
    ReportRendererPort,
    SignalDecomposerPort,
    TailRiskFitterPort,
    TelemetrySourcePort,
)
from core.specs import (
    CorridorSpec,
    EmpiricalBayesSpec,
    EngineConfigBundle,
    GPDFitterSpec,
    HydroEnvelopeSpec,
    MSSASpec,
    SPRTSpec,
    VesselProfileSpec,
    load_corridor_spec,
    load_engine_bundle,
    load_model_hyperparams,
    load_vessel_spec,
)
from core.sprt_gates import (
    SPRTGateResult,
    evaluate_sprt_gate,
    evaluate_sprt_surveillance_gate,
)

compute_skiff_boarding_feasibility = skiff_boarding_feasibility

__version__ = "0.3.0"
__author__ = "Bestman Ezekwu Enock (@mrbestnaija)"

__all__ = [
    "CivilianSensorTelemetry",
    "GPDTailRiskEstimate",
    "GeoCoordinates",
    "HydrodynamicEnvelopeResult",
    "IsotonicCalibrator",
    "JWCPricingResult",
    "JWCPriceResult",
    "MSSADecompositionResult",
    "MaritimeIncident",
    "PlattCalibrator",
    "SPRTGateResult",
    "SeverityInterval",
    "TemporalParadoxError",
    "brier_score",
    "calibrate_exceedance_probabilities",
    "composite_dark_vessel_hazard",
    "compute_actuarial_war_risk_loading_bps",
    "compute_gpd_var_cvar",
    "compute_jwc_7day_war_risk_ap",
    "price_jwc_7day_transit",
    "decompose_mssa",
    "evaluate_hydrodynamic_envelope",
    "evaluate_sprt_surveillance_gate",
    "evaluate_sprt_gate",
    "fit_pot_gpd",
    "gpd_cdf",
    "hankel_diagonal_averaging",
    "log_loss",
    "shrink_gpd_parameters",
    "skiff_boarding_feasibility",
    "compute_skiff_boarding_feasibility",
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
    "IncidentSourcePort",
    "TelemetrySourcePort",
    "SignalDecomposerPort",
    "TailRiskFitterPort",
    "ActuarialPricerPort",
    "ReportRendererPort",
    "AuditSinkPort",
]
