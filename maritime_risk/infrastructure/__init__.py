"""Infrastructure layer for Maritime Tail Risk Engine."""

from .audit_manifest import AuditManifestBuilder, compute_sha256
from .open_meteo_adapter import (
    OpenMeteoHydroAdapter,
    OpenMeteoHydroResult,
    cubic_delta_kernel,
    fetch_wave_heights,
    load_external_feeds_config,
    smooth_cubic_delta,
    smooth_wave_heights_cubic_delta,
)
from .osint_feed_loader import OSINTFeedLoader, compute_file_sha256
from .sqlite_storage import SCHEMA_SQL, SQLiteIncidentRepository
from .incident_feed_adapter import (
    INCIDENTS_SCHEMA_SQL,
    IncidentFeedAdapter,
    calculate_publication_lags,
    cubic_exponential_variance_bound,
    fetch_incidents,
    persist_incidents_to_sqlite,
    update_empirical_gpd,
)

__all__ = [
    "AuditManifestBuilder",
    "compute_sha256",
    "OSINTFeedLoader",
    "compute_file_sha256",
    "SCHEMA_SQL",
    "SQLiteIncidentRepository",
    "OpenMeteoHydroAdapter",
    "OpenMeteoHydroResult",
    "cubic_delta_kernel",
    "smooth_wave_heights_cubic_delta",
    "smooth_cubic_delta",
    "fetch_wave_heights",
    "load_external_feeds_config",
    "INCIDENTS_SCHEMA_SQL",
    "IncidentFeedAdapter",
    "calculate_publication_lags",
    "cubic_exponential_variance_bound",
    "persist_incidents_to_sqlite",
    "update_empirical_gpd",
    "fetch_incidents",
]
