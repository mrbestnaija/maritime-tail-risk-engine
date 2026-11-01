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
from typing import Any, Callable, Dict, Optional, TypeVar, cast
import numpy as np

from ..core.empirical_bayes import shrink_gpd_parameters
from ..core.gpd_tail_fitter import GPDTailRiskEstimate, fit_pot_gpd
from ..core.jwc_pricer import JWCPricingResult, compute_jwc_7day_war_risk_ap
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
    CorridorSpec,
    EmpiricalBayesSpec,
    GPDFitterSpec,
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
    ) -> JWCPricingResult:
        return compute_jwc_7day_war_risk_ap(
            calibrated_7d_breach_prob=breach_prob_7d,
            composite_cvar_99=composite_cvar_99,
            hydro_boarding_feasibility=hydro_feasibility,
            vessel_spec=vessel_spec,
            corridor_spec=corridor_spec,
        )


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
    "DefaultMarkdownTearsheetRenderer",
    "DefaultJsonManifestRenderer",
    "DefaultDictPayloadRenderer",
]
