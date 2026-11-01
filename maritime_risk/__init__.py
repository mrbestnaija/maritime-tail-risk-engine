"""Maritime Tail Risk Engine: Institutional Pluggable Python SDK.

Clean, configuration-driven, and protocol-based SDK for maritime tail risk
underwriting, multi-sensor OSINT intelligence fusion, and extreme value actuarial pricing.

Usage:
    import maritime_risk as mtr

    engine = mtr.MaritimeRiskEngine.from_config_files(
        corridor_id="GOG_BONNY_BRASS_FAIRWAY",
        vessel_profile_id="STANDARD_SUEZMAX_85M",
    )
    result = engine.evaluate(incidents=my_incidents, telemetry=my_telemetry)
    print(result.to_markdown())
"""

from pathlib import Path
import sys

_engine_root = str(Path(__file__).resolve().parent.parent)
if not sys.path or sys.path[0] != _engine_root:
    if _engine_root in sys.path:
        sys.path.remove(_engine_root)
    sys.path.insert(0, _engine_root)

# Core Domain Models
from core.models import (
    CivilianSensorTelemetry,
    GeoCoordinates,
    MaritimeIncident,
    SeverityInterval,
    TemporalParadoxError,
)

# Immutable Specifications
from core.specs import (
    DEFAULT_CORRIDOR_ID,
    DEFAULT_VESSEL_PROFILE_ID,
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

# Structural Protocols / Ports
from core.ports import (
    ActuarialPricerPort,
    AuditSinkPort,
    IncidentSourcePort,
    ReportRendererPort,
    SignalDecomposerPort,
    TailRiskFitterPort,
    TelemetrySourcePort,
)

# Pure Domain Mathematical Functions & Containers
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
from core.mssa_decomposer import (
    MSSADecompositionResult,
    decompose_mssa,
    hankel_diagonal_averaging,
)
from core.sprt_gates import (
    SPRTGateResult,
    evaluate_sprt_gate,
    evaluate_sprt_surveillance_gate,
)

# Calibration Utilities
from core.calibration import (
    IsotonicCalibrator,
    PlattCalibrator,
    brier_score,
    calibrate_exceedance_probabilities,
    log_loss,
)

# Application Engine & Registry
from application.engine import CorridorAuditResult, MaritimeRiskEngine
from application.registry import PluginRegistry, default_registry

compute_skiff_boarding_feasibility = skiff_boarding_feasibility

__version__ = "0.3.0"
__author__ = "Bestman Ezekwu Enock (@mrbestnaija)"

__all__ = [
    # Top-Level Facade
    "MaritimeRiskEngine",
    "CorridorAuditResult",
    "PluginRegistry",
    "default_registry",
    # Domain Models
    "MaritimeIncident",
    "CivilianSensorTelemetry",
    "GeoCoordinates",
    "SeverityInterval",
    "TemporalParadoxError",
    # Specifications
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
    # Structural Protocols / Ports
    "IncidentSourcePort",
    "TelemetrySourcePort",
    "SignalDecomposerPort",
    "TailRiskFitterPort",
    "ActuarialPricerPort",
    "ReportRendererPort",
    "AuditSinkPort",
    # Pure Math & Decomposition Functions
    "decompose_mssa",
    "MSSADecompositionResult",
    "hankel_diagonal_averaging",
    "fit_pot_gpd",
    "GPDTailRiskEstimate",
    "compute_gpd_var_cvar",
    "gpd_cdf",
    "compute_actuarial_war_risk_loading_bps",
    "shrink_gpd_parameters",
    "skiff_boarding_feasibility",
    "compute_skiff_boarding_feasibility",
    "composite_dark_vessel_hazard",
    "evaluate_hydrodynamic_envelope",
    "HydrodynamicEnvelopeResult",
    "compute_jwc_7day_war_risk_ap",
    "price_jwc_7day_transit",
    "JWCPricingResult",
    "JWCPriceResult",
    "evaluate_sprt_gate",
    "evaluate_sprt_surveillance_gate",
    "SPRTGateResult",
    # Calibration
    "IsotonicCalibrator",
    "PlattCalibrator",
    "brier_score",
    "calibrate_exceedance_probabilities",
    "log_loss",
]

# Alias canonical submodules under maritime_risk namespace
import core as _core
import application as _application
import infrastructure as _infrastructure

sys.modules["maritime_risk.core"] = _core
sys.modules["maritime_risk.core.specs"] = sys.modules.get("core.specs", _core)
sys.modules["maritime_risk.core.ports"] = sys.modules.get("core.ports", _core)
sys.modules["maritime_risk.core.models"] = sys.modules.get("core.models", _core)
sys.modules["maritime_risk.core.hydro_envelope"] = sys.modules.get("core.hydro_envelope", _core)
sys.modules["maritime_risk.core.mssa_decomposer"] = sys.modules.get("core.mssa_decomposer", _core)
sys.modules["maritime_risk.core.empirical_bayes"] = sys.modules.get("core.empirical_bayes", _core)
sys.modules["maritime_risk.core.gpd_tail_fitter"] = sys.modules.get("core.gpd_tail_fitter", _core)
sys.modules["maritime_risk.core.jwc_pricer"] = sys.modules.get("core.jwc_pricer", _core)
sys.modules["maritime_risk.core.sprt_gates"] = sys.modules.get("core.sprt_gates", _core)
sys.modules["maritime_risk.core.calibration"] = sys.modules.get("core.calibration", _core)
sys.modules["maritime_risk.core.metrics"] = sys.modules.get("core.metrics", _core)
sys.modules["maritime_risk.application"] = _application
sys.modules["maritime_risk.application.engine"] = sys.modules.get("application.engine", _application)
sys.modules["maritime_risk.application.registry"] = sys.modules.get("application.registry", _application)
sys.modules["maritime_risk.infrastructure"] = _infrastructure
