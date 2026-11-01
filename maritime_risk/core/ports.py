"""Structural Protocols / Ports for Pluggable Maritime Risk Architecture.

Defines runtime-checkable typing.Protocol interfaces under Hexagonal Architecture
(Ports & Adapters) allowing third-party applications to inject custom telemetry,
incident feeds, signal decomposers, tail fitters, actuarial pricers, and report renderers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Sequence, runtime_checkable
import numpy as np

from .models import CivilianSensorTelemetry, MaritimeIncident
from .specs import (
    CorridorSpec,
    EmpiricalBayesSpec,
    GPDFitterSpec,
    MSSASpec,
    VesselProfileSpec,
)

if TYPE_CHECKING:
    from .gpd_tail_fitter import GPDTailRiskEstimate
    from .jwc_pricer import JWCPricingResult
    from .mssa_decomposer import MSSADecompositionResult


@runtime_checkable
class IncidentSourcePort(Protocol):
    """Port for ingesting raw or curated maritime incident intelligence."""

    def fetch_incidents(
        self, corridor_id: str, as_of: datetime | None = None
    ) -> Sequence[MaritimeIncident]:
        """Fetch incidents for corridor optionally filtered by point-in-time as_of."""
        ...


@runtime_checkable
class TelemetrySourcePort(Protocol):
    """Port for ingesting multi-sensor civilian satellite and metocean telemetry."""

    def fetch_telemetry(
        self, corridor_id: str, as_of: datetime | None = None
    ) -> Sequence[CivilianSensorTelemetry]:
        """Fetch civilian telemetry for corridor optionally filtered by point-in-time as_of."""
        ...


@runtime_checkable
class SignalDecomposerPort(Protocol):
    """Port for decomposing multi-sensor time series into trend, seasonal harmonics, and residuals."""

    def decompose(
        self, matrix: np.ndarray, spec: MSSASpec
    ) -> "MSSADecompositionResult":
        """Decompose an (T, M) multivariate series matrix."""
        ...


@runtime_checkable
class TailRiskFitterPort(Protocol):
    """Port for fitting extreme value distributions to structural shock residuals."""

    def fit_tail(
        self,
        residuals: np.ndarray,
        baseline: float,
        bayes_spec: EmpiricalBayesSpec,
        gpd_spec: GPDFitterSpec,
    ) -> "GPDTailRiskEstimate":
        """Fit tail risk distribution to shock residuals anchored to baseline."""
        ...


@runtime_checkable
class ActuarialPricerPort(Protocol):
    """Port for first-principles Lloyd's JWC additional premium and demurrage calculation."""

    def price_transit(
        self,
        breach_prob_7d: float,
        composite_cvar_99: float,
        hydro_feasibility: float,
        vessel_spec: VesselProfileSpec,
        corridor_spec: CorridorSpec,
    ) -> "JWCPricingResult":
        """Calculate actuarial fair AP and demurrage exposure for vessel transit."""
        ...


@runtime_checkable
class ReportRendererPort(Protocol):
    """Port for formatting audit results into customer-facing representations."""

    def render(self, bundle: Any) -> str:
        """Render complete audit result into target format (e.g. Markdown, JSON, HTML)."""
        ...


@runtime_checkable
class AuditSinkPort(Protocol):
    """Port for persisting cryptographically sealed audit manifests and lineage records."""

    def save_manifest(
        self, manifest_data: dict[str, Any], destination: str | Path
    ) -> None:
        """Persist audit manifest data to target destination."""
        ...


__all__ = [
    "IncidentSourcePort",
    "TelemetrySourcePort",
    "SignalDecomposerPort",
    "TailRiskFitterPort",
    "ActuarialPricerPort",
    "ReportRendererPort",
    "AuditSinkPort",
]
