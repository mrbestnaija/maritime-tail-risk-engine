"""Generator script for Phase 1 & 2B Fairway Vintage Audit Tear Sheet.

Refactored into a lightweight wrapper around MaritimeRiskEngine, reproducing
the exact baseline PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md and PHASE1_AUDIT_MANIFEST.json.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from application.engine import COMMERCIAL_DISCLAIMER, MaritimeRiskEngine
from application.ingestion_hygiene import IngestionHygieneService
from application.isolation import get_isolated_database_connection
from infrastructure.audit_manifest import AuditManifestBuilder
from infrastructure.osint_feed_loader import OSINTFeedLoader
from infrastructure.sqlite_storage import SQLiteIncidentRepository


def run_phase1_audit(
    dataset_path: Path,
    output_markdown_path: Path,
    telemetry_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Run full Phase 1, 1.2, 2A & 2B audit and emit tear sheet & manifest via MaritimeRiskEngine."""
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

    # 5. Execute evaluation via MaritimeRiskEngine
    config_dir = root_dir / "configs"
    if config_dir.exists():
        engine = MaritimeRiskEngine.from_config_files(
            corridor_id="GOG_BONNY_BRASS_FAIRWAY",
            vessel_profile_id="STANDARD_SUEZMAX_85M",
            config_dir=config_dir,
        )
    else:
        engine = MaritimeRiskEngine()

    result = engine.evaluate(
        incidents=raw_incidents,
        telemetry=telemetry_records,
        dataset_sha256=dataset_sha256,
        telemetry_sha256=telemetry_sha256,
    )

    # 6. Emit PHASE1_AUDIT_MANIFEST.json using AuditManifestBuilder
    manifest_builder = AuditManifestBuilder(root_dir)
    manifest_file = manifest_path or (root_dir / "PHASE1_AUDIT_MANIFEST.json")
    manifest_builder.write_manifest_file(
        output_rel_path=str(manifest_file.name),
        gpd_result=result.gpd_result,
        jwc_result=result.jwc_result,
        sprt_result=result.sprt_result,
        hydro_result=result.hydro_result,
    )

    # 7. Write Markdown Tear Sheet
    output_markdown_path.write_text(result.to_markdown(), encoding="utf-8")

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
        "manifest_path": str(manifest_file),
        "output_path": str(output_markdown_path),
    }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    dataset_file = base_dir / "data" / "sample_gog_osint_vintage.csv"
    telemetry_file = base_dir / "data" / "gog_bonny_brass_civilian_telemetry.json"
    output_file = base_dir / "PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md"
    manifest_file = base_dir / "PHASE1_AUDIT_MANIFEST.json"

    res = run_phase1_audit(
        dataset_file, output_file, telemetry_path=telemetry_file, manifest_path=manifest_file
    )
    print(f"Generated tear sheet: {res['output_path']}")
    print(f"Generated audit manifest: {res['manifest_path']}")
    print(f"Dataset SHA-256: {res['dataset_sha256']}")
    print(f"Telemetry SHA-256: {res['telemetry_sha256']}")
    print(f"Incidents: {res['raw_count']} raw -> {res['dedup_count']} deduplicated")
    print(f"GPD Shrunk xi: {res['gpd_result'].shape_xi:.4f} (Raw: {res['gpd_result'].raw_xi:.4f}, w: {res['gpd_result'].shrinkage_weight_w:.4f})")
    print(f"Composite CVaR_0.99: {res['jwc_result'].composite_cvar_99:.2f}")
    print(f"JWC 7d Fair AP: {res['jwc_result'].actuarial_7d_war_risk_ap_bps:.2f} bps (Market: {res['jwc_result'].jwc_market_benchmark_bps:.2f} bps)")
    print(f"SPRT State: {res['sprt_result'].state}")
