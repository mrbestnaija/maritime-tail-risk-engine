"""Thread-Safe Pluggable Component Registry for Maritime Tail Risk Engine.

Supports registering and dynamically resolving:
- Feed Adapters (IncidentSourcePort, TelemetrySourcePort)
- Signal Decomposers (SignalDecomposerPort)
- Tail Fitters (TailRiskFitterPort)
- Actuarial Pricers (ActuarialPricerPort)
- Report Renderers (ReportRendererPort)

Implements the Open-Closed Principle (OCP) via structural protocols, decorator hooks,
and standard Python entry-point discovery (group="maritime_risk.plugins").
"""

from __future__ import annotations

import importlib.metadata
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Sequence, TypeVar, cast
import numpy as np

from ..core.empirical_bayes import shrink_gpd_parameters
from ..core.gpd_tail_fitter import GPDTailRiskEstimate, fit_pot_gpd
from ..core.jwc_pricer import (
    JWCPricingResult,
    compute_jwc_7day_war_risk_ap,
    price_cox_7day_war_risk_ap,
)
from ..core.models import CivilianSensorTelemetry, MaritimeIncident
from ..core.mssa_decomposer import MSSADecompositionResult, decompose_mssa
from ..core.ports import (
    ActuarialPricerPort,
    IncidentSourcePort,
    ReportRendererPort,
    SignalDecomposerPort,
    TailRiskFitterPort,
    TelemetrySourcePort,
)
from ..core.specs import (
    DEFAULT_CORRIDOR_ID,
    CorridorSpec,
    CoxHazardSpec,
    EmpiricalBayesSpec,
    GPDFitterSpec,
    HydroEnvelopeSpec,
    MSSASpec,
    VesselProfileSpec,
)

T = TypeVar("T")


# -----------------------------------------------------------------------------
# Default Built-in Implementations
# -----------------------------------------------------------------------------

class DefaultMSSADecomposer:
    """Default Multivariate Singular Spectrum Analysis decomposer port adapter."""

    def decompose(self, matrix: np.ndarray, spec: MSSASpec) -> MSSADecompositionResult:
        return decompose_mssa(matrix, spec=spec)


class DefaultTailRiskFitter:
    """Default Peaks-Over-Threshold GPD tail fitter with Empirical Bayes shrinkage."""

    def fit_tail(
        self,
        residuals: np.ndarray,
        baseline: float,
        bayes_spec: EmpiricalBayesSpec,
        gpd_spec: GPDFitterSpec,
    ) -> GPDTailRiskEstimate:
        return fit_pot_gpd(
            residuals,
            baseline_anchor=baseline,
            spec=gpd_spec,
            bayes_spec=bayes_spec,
        )


class DefaultLloydsJWCPricer:
    """Default first-principles Lloyd's JWC 7-Day AP and demurrage actuarial pricer."""

    def price_transit(
        self,
        breach_prob_7d: float,
        composite_cvar_99: float,
        hydro_feasibility: float,
        vessel_spec: VesselProfileSpec,
        corridor_spec: CorridorSpec,
        regime_multiplier: float = 1.0,
        **kwargs: Any,
    ) -> JWCPricingResult:
        reg_mult = kwargs.get("regime_multiplier", regime_multiplier)
        cox_spec = kwargs.get("cox_spec")
        comm_floor = kwargs.get("commercial_baseline_bps")
        return compute_jwc_7day_war_risk_ap(
            calibrated_7d_breach_prob=breach_prob_7d,
            composite_cvar_99=composite_cvar_99,
            hydro_boarding_feasibility=hydro_feasibility,
            vessel_spec=vessel_spec,
            corridor_spec=corridor_spec,
            regime_multiplier=reg_mult,
            cox_spec=cox_spec,
            commercial_baseline_bps=comm_floor,
            mothership_loitering_idx=kwargs.get("mothership_loitering_idx", 0.25),
            distance_pmsc_km=kwargs.get("distance_pmsc_km", 180.0),
            wave_height_m=kwargs.get("wave_height_m", 1.2),
            wind_knots=kwargs.get("wind_knots"),
            hydro_spec=kwargs.get("hydro_spec"),
        )


class CoxProportionalHazardsJWCPricer:
    """Cox Proportional Hazards voyage pricer port adapter."""

    def __init__(
        self,
        cox_spec: Optional[CoxHazardSpec] = None,
        hydro_spec: Optional[HydroEnvelopeSpec] = None,
        mothership_loitering_idx: float = 0.25,
        distance_pmsc_km: float = 180.0,
        wave_height_m: float = 1.2,
        wind_knots: Optional[float] = None,
    ) -> None:
        self.cox_spec = cox_spec or CoxHazardSpec()
        self.hydro_spec = hydro_spec or HydroEnvelopeSpec()
        self.mothership_loitering_idx = mothership_loitering_idx
        self.distance_pmsc_km = distance_pmsc_km
        self.wave_height_m = wave_height_m
        self.wind_knots = wind_knots

    def price_transit(
        self,
        breach_prob_7d: float,
        composite_cvar_99: float,
        hydro_feasibility: float,
        vessel_spec: VesselProfileSpec,
        corridor_spec: CorridorSpec,
        regime_multiplier: float = 1.0,
        **kwargs: Any,
    ) -> JWCPricingResult:
        mli = kwargs.get("mothership_loitering_idx", self.mothership_loitering_idx)
        dist = kwargs.get("distance_pmsc_km", self.distance_pmsc_km)
        wave_h = kwargs.get("wave_height_m", self.wave_height_m)
        wind = kwargs.get("wind_knots", self.wind_knots)
        c_spec = kwargs.get("cox_spec", self.cox_spec)
        h_spec = kwargs.get("hydro_spec", self.hydro_spec)
        reg_mult = kwargs.get("regime_multiplier", regime_multiplier)

        return price_cox_7day_war_risk_ap(
            mothership_loitering_idx=mli,
            distance_pmsc_km=dist,
            wave_height_m=wave_h,
            composite_cvar_99=composite_cvar_99,
            wind_knots=wind,
            vessel_spec=vessel_spec,
            corridor_spec=corridor_spec,
            cox_spec=c_spec,
            hydro_spec=h_spec,
            regime_multiplier=reg_mult,
        )


class CopernicusGFWStandardizedAdapter:
    """Standardized multi-sensor telemetry adapter for Copernicus and GFW feeds.

    Automatically handles sentinel missing-data imputation:
    - Imputes negative sentinel wave heights (e.g. -999.0) to corridor baseline wave height.
    - Imputes negative or missing SAR dark vessel ratio, loitering index, etc.
    - Enforces temporal paradox invariants and constructs valid CivilianSensorTelemetry models.
    """

    def __init__(
        self,
        baseline_wave_height_m: float = 1.35,
        default_sar_dark_ratio: float = 0.15,
        default_anchorage_waiting_hours: float = 24.0,
        default_mothership_loitering_idx: float = 0.25,
        default_distance_pmsc_km: float = 180.0,
    ) -> None:
        self.baseline_wave_height_m = baseline_wave_height_m
        self.default_sar_dark_ratio = default_sar_dark_ratio
        self.default_anchorage_waiting_hours = default_anchorage_waiting_hours
        self.default_mothership_loitering_idx = default_mothership_loitering_idx
        self.default_distance_pmsc_km = default_distance_pmsc_km
        self._cached_telemetry: list[CivilianSensorTelemetry] = []

    def _parse_timestamp(self, val: Any) -> datetime:
        """Parse various timestamp representations into a valid datetime."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(val, tz=timezone.utc)
        if isinstance(val, str):
            clean_str = val.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(clean_str)
            except Exception:
                pass
        return datetime.now(timezone.utc)

    def adapt_record(
        self,
        record: dict[str, Any],
        baseline_wave_height_m: Optional[float] = None,
    ) -> CivilianSensorTelemetry:
        """Adapt a single raw record, imputing negative sentinel values."""
        base_wave = (
            baseline_wave_height_m
            if baseline_wave_height_m is not None
            else self.baseline_wave_height_m
        )

        # 1. Resolve Wave Height with sentinel imputation
        raw_wave = (
            record.get("significant_wave_height_m")
            if "significant_wave_height_m" in record
            else record.get("wave_height_m", record.get("VHM0", record.get("hs", base_wave)))
        )
        try:
            wave_val = float(raw_wave)
            if wave_val < 0.0:  # Sentinel fill-value (e.g. -999.0, -1.0)
                wave_val = float(base_wave)
        except (TypeError, ValueError):
            wave_val = float(base_wave)
        wave_val = max(min(wave_val, 25.0), 0.0)

        # 2. Resolve SAR Dark Vessel Ratio
        raw_sar = (
            record.get("sar_dark_vessel_ratio")
            if "sar_dark_vessel_ratio" in record
            else record.get("dark_ratio", record.get("sar_ratio", self.default_sar_dark_ratio))
        )
        try:
            sar_val = float(raw_sar)
            if sar_val < 0.0:
                sar_val = float(self.default_sar_dark_ratio)
        except (TypeError, ValueError):
            sar_val = float(self.default_sar_dark_ratio)
        sar_val = max(min(sar_val, 1.0), 0.0)

        # 3. Anchorage Waiting Hours
        raw_waiting = (
            record.get("anchorage_waiting_hours")
            if "anchorage_waiting_hours" in record
            else record.get("waiting_hours", self.default_anchorage_waiting_hours)
        )
        try:
            waiting_val = float(raw_waiting)
            if waiting_val < 0.0:
                waiting_val = float(self.default_anchorage_waiting_hours)
        except (TypeError, ValueError):
            waiting_val = float(self.default_anchorage_waiting_hours)
        waiting_val = max(waiting_val, 0.0)

        # 4. VIIRS Continuity
        raw_viirs = (
            record.get("viirs_flaring_continuity_idx")
            if "viirs_flaring_continuity_idx" in record
            else record.get("flaring_idx", 1.0)
        )
        try:
            viirs_val = float(raw_viirs)
            if viirs_val < 0.0:
                viirs_val = 1.0
        except (TypeError, ValueError):
            viirs_val = 1.0
        viirs_val = max(min(viirs_val, 1.0), 0.0)

        # 5. Mothership Loitering Index
        raw_mli = (
            record.get("mothership_loitering_index")
            if "mothership_loitering_index" in record
            else record.get("loitering_index", record.get("mli", self.default_mothership_loitering_idx))
        )
        try:
            mli_val = float(raw_mli)
            if mli_val < 0.0:
                mli_val = float(self.default_mothership_loitering_idx)
        except (TypeError, ValueError):
            mli_val = float(self.default_mothership_loitering_idx)
        mli_val = max(min(mli_val, 1.0), 0.0)

        # 6. PMSC Distance
        raw_pmsc = (
            record.get("distance_pmsc_km")
            if "distance_pmsc_km" in record
            else record.get("pmsc_km", self.default_distance_pmsc_km)
        )
        try:
            pmsc_val = float(raw_pmsc)
            if pmsc_val < 0.0:
                pmsc_val = float(self.default_distance_pmsc_km)
        except (TypeError, ValueError):
            pmsc_val = float(self.default_distance_pmsc_km)
        pmsc_val = max(min(pmsc_val, 2000.0), 0.0)

        # 7. Timestamps
        obs_raw = record.get("observation_timestamp") or record.get("time") or record.get("obs_time")
        obs_dt = self._parse_timestamp(obs_raw)

        pub_raw = record.get("publication_timestamp") or record.get("pub_time")
        if pub_raw is not None:
            pub_dt = self._parse_timestamp(pub_raw)
        else:
            pub_dt = obs_dt

        # 8. Identifiers
        tel_id = str(
            record.get("telemetry_id")
            or record.get("id")
            or f"TEL-STD-{int(obs_dt.timestamp())}"
        )
        corridor = str(record.get("corridor_id") or DEFAULT_CORRIDOR_ID)

        sar_prov = record.get("sar_provider", "GFW_SENTINEL1_SAR")
        met_prov = record.get("metocean_provider", "COPERNICUS_ERA5_METOCEAN")
        ais_prov = record.get("ais_provider", "IMF_PORTWATCH_AIS")

        return CivilianSensorTelemetry(
            telemetry_id=tel_id,
            corridor_id=corridor,
            observation_timestamp=obs_dt,
            publication_timestamp=pub_dt,
            sar_provider=sar_prov,
            metocean_provider=met_prov,
            ais_provider=ais_prov,
            significant_wave_height_m=wave_val,
            sar_dark_vessel_ratio=sar_val,
            anchorage_waiting_hours=waiting_val,
            viirs_flaring_continuity_idx=viirs_val,
            mothership_loitering_index=mli_val,
            distance_pmsc_km=pmsc_val,
        )

    def adapt_records(
        self,
        records: Sequence[dict[str, Any]],
        baseline_wave_height_m: Optional[float] = None,
    ) -> list[CivilianSensorTelemetry]:
        """Adapt a collection of raw records."""
        adapted = [
            self.adapt_record(r, baseline_wave_height_m=baseline_wave_height_m) for r in records
        ]
        self._cached_telemetry.extend(adapted)
        return adapted

    def fetch_telemetry(
        self, corridor_id: str, as_of: Optional[datetime] = None
    ) -> Sequence[CivilianSensorTelemetry]:
        """Fetch telemetry matching corridor, filtered by point-in-time as_of."""
        results = [t for t in self._cached_telemetry if t.corridor_id == corridor_id]
        if as_of is not None:
            results = [t for t in results if t.publication_timestamp <= as_of]
        return results

    def __call__(self, data: Any) -> Any:
        if isinstance(data, dict):
            return self.adapt_record(data)
        if isinstance(data, (list, tuple)):
            return self.adapt_records(data)
        return data


class DefaultMarkdownTearsheetRenderer:
    """Default Markdown tear sheet renderer formatting full vintage audit tearsheets."""

    def render(self, bundle: Any) -> str:
        if hasattr(bundle, "to_markdown_string"):
            return str(bundle.to_markdown_string())
        return str(bundle)


class DefaultJsonManifestRenderer:
    """Default JSON manifest renderer for cryptographic lineage audit trails."""

    def render(self, bundle: Any) -> str:
        if hasattr(bundle, "to_json"):
            return str(bundle.to_json(indent=2))
        import json
        return json.dumps(bundle, default=str, indent=2)


class DefaultDictPayloadRenderer:
    """Default dict payload renderer returning JSON-serializable dictionaries."""

    def render(self, bundle: Any) -> dict[str, Any]:
        if hasattr(bundle, "to_dict"):
            return cast(dict[str, Any], bundle.to_dict())
        return dict(bundle)


# -----------------------------------------------------------------------------
# Thread-Safe Plugin Registry
# -----------------------------------------------------------------------------

class PluginRegistry:
    """Thread-safe registry for managing swappable components and plugins."""

    def __init__(self, auto_discover: bool = True) -> None:
        self._lock = threading.RLock()
        self._feed_adapters: Dict[str, Any] = {}
        self._decomposers: Dict[str, SignalDecomposerPort] = {}
        self._tail_fitters: Dict[str, TailRiskFitterPort] = {}
        self._pricers: Dict[str, ActuarialPricerPort] = {}
        self._renderers: Dict[str, ReportRendererPort] = {}

        self._register_defaults()
        if auto_discover:
            self.discover_entry_points()

    def _register_defaults(self) -> None:
        """Register default built-in components."""
        self.register_decomposer("mssa_svd", DefaultMSSADecomposer())
        self.register_tail_fitter("empirical_bayes_pot_gpd", DefaultTailRiskFitter())
        self.register_pricer("lloyds_jwc_7d_first_principles", DefaultLloydsJWCPricer())
        self.register_pricer("cox_proportional_hazards_jwc", CoxProportionalHazardsJWCPricer())
        self.register_feed_adapter("copernicus_gfw_standardized", CopernicusGFWStandardizedAdapter())
        self.register_renderer("markdown_tearsheet", DefaultMarkdownTearsheetRenderer())
        self.register_renderer("json_manifest", DefaultJsonManifestRenderer())
        self.register_renderer("dict_payload", DefaultDictPayloadRenderer())

    # --- Decomposers ---
    def register_decomposer(
        self, name: str, decomposer: Any = None
    ) -> Any:
        def decorator(cls_or_fn: Any) -> Any:
            with self._lock:
                instance = cls_or_fn() if isinstance(cls_or_fn, type) else cls_or_fn
                self._decomposers[name] = instance
            return cls_or_fn

        if decomposer is not None:
            return decorator(decomposer)
        return decorator

    def get_decomposer(self, name: str = "mssa_svd") -> SignalDecomposerPort:
        with self._lock:
            if name not in self._decomposers:
                raise KeyError(
                    f"Signal decomposer '{name}' not found. Available: {list(self._decomposers.keys())}"
                )
            return self._decomposers[name]

    # --- Tail Fitters ---
    def register_tail_fitter(
        self, name: str, fitter: Any = None
    ) -> Any:
        def decorator(cls_or_fn: Any) -> Any:
            with self._lock:
                instance = cls_or_fn() if isinstance(cls_or_fn, type) else cls_or_fn
                self._tail_fitters[name] = instance
            return cls_or_fn

        if fitter is not None:
            return decorator(fitter)
        return decorator

    def get_tail_fitter(self, name: str = "empirical_bayes_pot_gpd") -> TailRiskFitterPort:
        with self._lock:
            if name not in self._tail_fitters:
                raise KeyError(
                    f"Tail fitter '{name}' not found. Available: {list(self._tail_fitters.keys())}"
                )
            return self._tail_fitters[name]

    # --- Pricers ---
    def register_pricer(
        self, name: str, pricer: Any = None
    ) -> Any:
        def decorator(cls_or_fn: Any) -> Any:
            with self._lock:
                instance = cls_or_fn() if isinstance(cls_or_fn, type) else cls_or_fn
                self._pricers[name] = instance
            return cls_or_fn

        if pricer is not None:
            return decorator(pricer)
        return decorator

    def get_pricer(self, name: str = "lloyds_jwc_7d_first_principles") -> ActuarialPricerPort:
        with self._lock:
            if name not in self._pricers:
                raise KeyError(
                    f"Pricer '{name}' not found. Available: {list(self._pricers.keys())}"
                )
            return self._pricers[name]

    # --- Renderers ---
    def register_renderer(
        self, name: str, renderer: Any = None
    ) -> Any:
        def decorator(cls_or_fn: Any) -> Any:
            with self._lock:
                instance = cls_or_fn() if isinstance(cls_or_fn, type) else cls_or_fn
                self._renderers[name] = instance
            return cls_or_fn

        if renderer is not None:
            return decorator(renderer)
        return decorator

    def get_renderer(self, name: str = "markdown_tearsheet") -> ReportRendererPort:
        with self._lock:
            if name not in self._renderers:
                raise KeyError(
                    f"Renderer '{name}' not found. Available: {list(self._renderers.keys())}"
                )
            return self._renderers[name]

    # --- Feed Adapters ---
    def register_feed_adapter(
        self, name: str, adapter: Any = None
    ) -> Any:
        def decorator(cls_or_fn: Any) -> Any:
            with self._lock:
                instance = cls_or_fn() if isinstance(cls_or_fn, type) else cls_or_fn
                self._feed_adapters[name] = instance
            return cls_or_fn

        if adapter is not None:
            return decorator(adapter)
        return decorator

    def get_feed_adapter(self, name: str) -> Any:
        with self._lock:
            if name not in self._feed_adapters:
                raise KeyError(
                    f"Feed adapter '{name}' not found. Available: {list(self._feed_adapters.keys())}"
                )
            return self._feed_adapters[name]

    # --- Query & Inspection Methods ---
    def list_decomposers(self) -> list[str]:
        with self._lock:
            return list(self._decomposers.keys())

    def list_tail_fitters(self) -> list[str]:
        with self._lock:
            return list(self._tail_fitters.keys())

    def list_pricers(self) -> list[str]:
        with self._lock:
            return list(self._pricers.keys())

    def list_renderers(self) -> list[str]:
        with self._lock:
            return list(self._renderers.keys())

    def list_feed_adapters(self) -> list[str]:
        with self._lock:
            return list(self._feed_adapters.keys())

    def register_incident_source(self, name: str, adapter: Any = None) -> Any:
        return self.register_feed_adapter(name, adapter)

    def register_telemetry_source(self, name: str, adapter: Any = None) -> Any:
        return self.register_feed_adapter(name, adapter)

    # --- Auto-Discovery via Entry Points ---
    def discover_entry_points(self, group: str = "maritime_risk.plugins") -> int:
        """Scan python entry-points and auto-register third-party plugins."""
        count = 0
        try:
            eps = importlib.metadata.entry_points()
            if hasattr(eps, "select"):
                matched = eps.select(group=group)
            else:
                matched = eps.get(group, [])

            for ep in matched:
                try:
                    plugin_init = ep.load()
                    if callable(plugin_init):
                        try:
                            plugin_init(self)
                            count += 1
                            continue
                        except TypeError:
                            pass
                    target = plugin_init() if isinstance(plugin_init, type) else plugin_init
                    if isinstance(target, ActuarialPricerPort) or hasattr(target, "price_transit"):
                        self.register_pricer(ep.name, target)
                        count += 1
                    elif isinstance(target, SignalDecomposerPort) or hasattr(target, "decompose"):
                        self.register_decomposer(ep.name, target)
                        count += 1
                    elif isinstance(target, TailRiskFitterPort) or hasattr(target, "fit_tail"):
                        self.register_tail_fitter(ep.name, target)
                        count += 1
                    elif isinstance(target, ReportRendererPort) or hasattr(target, "render"):
                        self.register_renderer(ep.name, target)
                        count += 1
                    elif isinstance(target, IncidentSourcePort) or hasattr(target, "fetch_incidents"):
                        self.register_incident_source(ep.name, target)
                        count += 1
                    elif isinstance(target, TelemetrySourcePort) or hasattr(target, "fetch_telemetry"):
                        self.register_telemetry_source(ep.name, target)
                        count += 1
                except Exception:
                    pass
        except Exception:
            pass
        return count


# Singleton default registry
default_registry = PluginRegistry()

__all__ = [
    "PluginRegistry",
    "default_registry",
    "DefaultMSSADecomposer",
    "DefaultTailRiskFitter",
    "DefaultLloydsJWCPricer",
    "CoxProportionalHazardsJWCPricer",
    "CopernicusGFWStandardizedAdapter",
    "DefaultMarkdownTearsheetRenderer",
    "DefaultJsonManifestRenderer",
    "DefaultDictPayloadRenderer",
]
