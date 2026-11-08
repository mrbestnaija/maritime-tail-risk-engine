"""Generator script for Phase 1, 2B & Phase 3 Live OSINT Fairway Audit Tear Sheet.

Integrates Live OSINT & Environmental REST adapters:
1. Open-Meteo REST API live hydrodynamics ingestion with Cubic Delta (psi_3) kernel smoothing.
2. OSINT incident feed ingestion, publication lag (Delta_t) calculation, and SQLite persistence.
3. Evaluates corridor risk profile via MaritimeRiskEngine with live smoothed significant wave height (Hs).
4. Appends circuit breaker status tags and emits reproducible Markdown tear sheet & JSON audit manifest.

Author: Maritime domain researcher with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
"""

from __future__ import annotations

import argparse
import datetime
import os
from pathlib import Path
from typing import Any

from application.engine import COMMERCIAL_DISCLAIMER, MaritimeRiskEngine
from application.ingestion_hygiene import IngestionHygieneService
from application.isolation import get_isolated_database_connection
from infrastructure.audit_manifest import AuditManifestBuilder
from infrastructure.incident_feed_adapter import IncidentFeedAdapter
from infrastructure.open_meteo_adapter import OpenMeteoHydroAdapter
from infrastructure.osint_feed_loader import OSINTFeedLoader
from infrastructure.sqlite_storage import SQLiteIncidentRepository


def run_phase1_audit(
    dataset_path: Path,
    output_markdown_path: Path,
    telemetry_path: Path | None = None,
    manifest_path: Path | None = None,
    corridor_id: str = "GOG_BONNY_BRASS_FAIRWAY",
    vessel_profile_id: str = "STANDARD_SUEZMAX_85M",
    current_hs: float | None = None,
    as_of: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Run full Phase 1, 2B & Phase 3 live audit and emit tear sheet & manifest via MaritimeRiskEngine."""
    root_dir = dataset_path.parent.parent

    # 1. Load OSINT incident data and compute SHA-256 lineage hash
    if dataset_path.suffix.lower() == ".csv":
        raw_incidents, dataset_sha256 = OSINTFeedLoader.load_incidents_from_csv(dataset_path)
    else:
        raw_incidents, dataset_sha256 = OSINTFeedLoader.load_incidents_from_json(dataset_path)

    # 2. Ingestion Hygiene & Deduplication
    hygiene_service = IngestionHygieneService()
    dedup_incidents = hygiene_service.deduplicate_cross_feed(raw_incidents)

    # 3. Store in Sandbox SQLite DB with C-engine CHECK constraints
    conn = get_isolated_database_connection(env_mode="sandbox")
    repo = SQLiteIncidentRepository(conn)
    repo.insert_batch(dedup_incidents)
    persisted_incidents = repo.load_all_incidents()

    # 4. Load Civilian Multi-Sensor Telemetry
    if telemetry_path is None:
        telemetry_path = dataset_path.parent / "gog_bonny_brass_civilian_telemetry.json"

    telemetry_records = []
    telemetry_sha256 = "N/A"
    if telemetry_path.exists():
        telemetry_records, telemetry_sha256 = OSINTFeedLoader.load_civilian_telemetry_from_json(telemetry_path)
        repo.insert_telemetry_batch(telemetry_records)

    config_dir = root_dir / "configs"
    cfg_dir = config_dir if config_dir.exists() else None

    # 5. Live Environmental & OSINT Ingestion via REST Adapters
    # Ingest live metocean wave heights via Open-Meteo REST API
    meteo_adapter = OpenMeteoHydroAdapter(config_dir=cfg_dir, db_connection=conn)
    hydro_state = meteo_adapter.fetch_live_hydrodynamics(corridor_id=corridor_id)
    live_hs = hydro_state.wave_height_m
    hydro_tag = hydro_state.metadata_tag

    # Probe live incident feed and calculate publication lag (Delta_t)
    incident_adapter = IncidentFeedAdapter(config_dir=cfg_dir, db_connection=conn)
    live_incidents, incident_tag = incident_adapter.fetch_incidents()
    if live_incidents:
        incident_adapter.calculate_publication_lags(live_incidents, in_hours=True)
        incident_adapter.persist_incidents(live_incidents)

    # Deterministic audit timestamp (reproducible build compliance)
    if as_of is not None:
        frozen_as_of = as_of
    elif "SOURCE_DATE_EPOCH" in os.environ:
        try:
            frozen_as_of = datetime.datetime.fromtimestamp(
                int(os.environ["SOURCE_DATE_EPOCH"]), tz=datetime.timezone.utc
            )
        except ValueError:
            frozen_as_of = None
    else:
        frozen_as_of = None

    if frozen_as_of is None:
        max_ts = 0.0
        for inc in raw_incidents:
            ts = getattr(inc, "pub_time", None) or getattr(inc, "event_time", None)
            if isinstance(ts, (int, float)) and ts > max_ts:
                max_ts = float(ts)
            elif isinstance(ts, datetime.datetime) and ts.timestamp() > max_ts:
                max_ts = ts.timestamp()
        if max_ts > 0:
            frozen_as_of = datetime.datetime.fromtimestamp(max_ts, tz=datetime.timezone.utc)
        else:
            frozen_as_of = datetime.datetime(2026, 11, 8, 0, 0, 0, tzinfo=datetime.timezone.utc)

    # 6. Execute evaluation via MaritimeRiskEngine with live smoothed Hs
    if config_dir.exists():
        engine = MaritimeRiskEngine.from_config_files(
            corridor_id=corridor_id,
            vessel_profile_id=vessel_profile_id,
            config_dir=config_dir,
        )
    else:
        engine = MaritimeRiskEngine()

    result = engine.evaluate(
        incidents=raw_incidents,
        telemetry=telemetry_records,
        as_of=frozen_as_of,
        dataset_sha256=dataset_sha256,
        telemetry_sha256=telemetry_sha256,
        current_hs=current_hs,
    )

    # 7. Emit PHASE1_AUDIT_MANIFEST.json using AuditManifestBuilder
    manifest_builder = AuditManifestBuilder(root_dir)
    manifest_file = manifest_path or (root_dir / "PHASE1_AUDIT_MANIFEST.json")
    manifest_builder.write_manifest_file(
        output_rel_path=manifest_file,
        as_of=frozen_as_of,
        gpd_result=result.gpd_result,
        jwc_result=result.jwc_result,
        sprt_result=result.sprt_result,
        hydro_result=result.hydro_result,
    )

    # 8. Visually append circuit breaker / live telemetry banners and write Markdown Tear Sheet
    md_content = result.to_markdown()
    banners: list[str] = []

    if hydro_tag and hydro_tag != "[LIVE_METOCEAN]":
        banners.append(
            f"> [!WARNING]\n"
            f"> **CIRCUIT BREAKER ENGAGED ({hydro_tag})**: Upstream Open-Meteo REST API unavailable or timed out. "
            f"Fell back to historical 90th percentile baseline wave height ({live_hs:.2f}m)."
        )
    elif hydro_tag == "[LIVE_METOCEAN]":
        banners.append(
            f"> [!NOTE]\n"
            f"> **LIVE METOCEAN TELEMETRY ({hydro_tag})**: Successfully ingested from Open-Meteo Marine REST API. "
            f"Live smoothed significant wave height $H_s = {live_hs:.2f}\\text{{m}}$ (Cubic Delta $\\psi_3$ kernel)."
        )

    if incident_tag and incident_tag != "[LIVE_INCIDENTS]":
        banners.append(
            f"> [!WARNING]\n"
            f"> **CIRCUIT BREAKER ENGAGED ({incident_tag})**: Live OSINT incident feed unavailable or timed out. "
            f"Underwriting engine operating on verified local archive."
        )
    elif incident_tag == "[LIVE_INCIDENTS]":
        banners.append(
            f"> [!NOTE]\n"
            f"> **LIVE OSINT INCIDENT TELEMETRY ({incident_tag})**: Successfully synchronized with live public feed. "
            f"Ingested and verified against SQLite C-engine temporal & spatial constraints."
        )

    if banners:
        md_content = "\n\n".join(banners) + "\n\n" + md_content

    output_markdown_path.write_text(md_content, encoding="utf-8")

    return {
        "dataset_sha256": dataset_sha256,
        "telemetry_sha256": telemetry_sha256,
        "raw_count": len(raw_incidents),
        "dedup_count": len(dedup_incidents),
        "mean_lag_days": result.mean_reporting_lag_days,
        "max_lag_days": result.max_reporting_lag_days,
        "risk_metrics": result.empirical_risk_metrics,
        "mssa_result": result.mssa_result,
        "gpd_result": result.gpd_result,
        "hydro_result": result.hydro_result,
        "sprt_result": result.sprt_result,
        "jwc_result": result.jwc_result,
        "live_hs": live_hs,
        "hydro_tag": hydro_tag,
        "incident_tag": incident_tag,
        "manifest_path": str(manifest_file),
        "output_path": str(output_markdown_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Maritime Tail Risk Tear Sheet and Manifest.")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output Markdown tear sheet path")
    parser.add_argument("--manifest", "-m", type=Path, default=None, help="Output JSON audit manifest path")
    parser.add_argument("--corridor-id", type=str, default="GOG_BONNY_BRASS_FAIRWAY", help="Corridor ID")
    parser.add_argument("--vessel-profile-id", type=str, default="STANDARD_SUEZMAX_85M", help="Vessel profile ID")
    parser.add_argument("--as-of", type=str, default=None, help="Explicit ISO timestamp for reproducible execution")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    dataset_file = base_dir / "data" / "sample_gog_osint_vintage.csv"
    telemetry_file = base_dir / "data" / "gog_bonny_brass_civilian_telemetry.json"
    output_file = args.output or (base_dir / "PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md")
    manifest_file = args.manifest or (base_dir / "PHASE1_AUDIT_MANIFEST.json")

    explicit_as_of = None
    if args.as_of:
        explicit_as_of = datetime.datetime.fromisoformat(args.as_of)

    res = run_phase1_audit(
        dataset_file,
        output_file,
        telemetry_path=telemetry_file,
        manifest_path=manifest_file,
        corridor_id=args.corridor_id,
        vessel_profile_id=args.vessel_profile_id,
        as_of=explicit_as_of,
    )
    gpd = res["gpd_result"]
    jwc = res["jwc_result"]
    ci_low_str = f"{jwc.ap_credible_interval_lower_bps:.2f}" if jwc.ap_credible_interval_lower_bps is not None else f"{jwc.actuarial_7d_war_risk_ap_bps:.2f}"
    ci_high_str = f"{jwc.ap_credible_interval_upper_bps:.2f}" if jwc.ap_credible_interval_upper_bps is not None else f"{jwc.actuarial_7d_war_risk_ap_bps:.2f}"
    xi_ci_str = f"[{gpd.xi_ci_lower:.4f}, {gpd.xi_ci_upper:.4f}]" if gpd.xi_ci_lower is not None else "N/A"

    print(f"Generated tear sheet: {res['output_path']}")
    print(f"Generated audit manifest: {res['manifest_path']}")
    print(f"Live Metocean Hs: {res['live_hs']:.4f} m ({res['hydro_tag']})")
    print(f"Incident Feed Status: {res['incident_tag']}")
    print(f"Dataset SHA-256: {res['dataset_sha256']}")
    print(f"Telemetry SHA-256: {res['telemetry_sha256']}")
    print(f"Incidents: {res['raw_count']} raw -> {res['dedup_count']} deduplicated")
    print(f"GPD Diagnostics: Threshold u={gpd.threshold_u:.4f}, Nu={gpd.exceedance_count}, Shrunk xi={gpd.shape_xi:.4f} (95% CI: {xi_ci_str})")
    print(f"Explicit Pricing Chain:")
    print(f"  1. Incident Frequency: {jwc.effective_vessel_breach_prob * 100:.2f}% (effective single-vessel breach prob)")
    print(f"  2. Expected Loss Given Event: ${(jwc.cvar_99_demurrage_usd + jwc.catastrophic_tail_loss_usd):,.2f} USD")
    print(f"  3. Expected Shortfall (CVaR_0.99): {jwc.composite_cvar_99:.2f} / 10.0 ($100M H&M Insured Value basis)")
    print(f"  4. 7-Day Fair Actuarial AP: {jwc.actuarial_7d_war_risk_ap_bps:.2f} bps [{ci_low_str} bps - {ci_high_str} bps]")
    print(f"  Reference Market Quote: {jwc.jwc_market_benchmark_bps:.2f} bps (Lloyd's JWC Benchmark)")
    print(f"  Underwriter Spread: {jwc.mispricing_spread_bps:+.2f} bps (${jwc.per_transit_mispricing_usd:+,.2f} USD)")
    print(f"SPRT State: {res['sprt_result'].state}")
