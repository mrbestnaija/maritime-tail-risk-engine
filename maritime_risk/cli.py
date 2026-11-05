"""Command-Line Interface (CLI) for Maritime Tail Risk Engine.

Entry-point for `maritime-risk` console script and root `cli.py`.
Provides institutional operators with manual verification commands:
- `audit`: Corridor audit evaluation emitting Markdown tear sheet & JSON manifest.
- `verify`: Quad-gate repository verification (< 10s SLA).
- `live-meteo`: Live Open-Meteo hydrodynamics ingestion with Cubic Delta (psi_3) kernel.
- `live-incidents`: Live OSINT incident ingestion with publication lag (Delta_t) & GPD bounds.
- `live-oracle`: Unified live multi-sensor fusion oracle emitting live audit artifacts.

Author: Nigerian Navy officer with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .application.engine import MaritimeRiskEngine
from .infrastructure.audit_manifest import AuditManifestBuilder
from .infrastructure.incident_feed_adapter import (
    IncidentFeedAdapter,
    calculate_publication_lags,
    fetch_incidents,
    persist_incidents_to_sqlite,
    update_empirical_gpd,
)
from .infrastructure.open_meteo_adapter import (
    OpenMeteoHydroAdapter,
    fetch_wave_heights,
    load_external_feeds_config,
    smooth_cubic_delta,
)
from .infrastructure.osint_feed_loader import OSINTFeedLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maritime-risk",
        description="Maritime Tail Risk Engine: Actuarial OSINT Underwriting & Multi-Sensor Fusion CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # 1. Evaluate / Audit command
    audit_parser = subparsers.add_parser("audit", help="Run corridor audit evaluation")
    audit_parser.add_argument(
        "--corridor",
        default="GOG_BONNY_BRASS_FAIRWAY",
        help="Corridor identifier (default: GOG_BONNY_BRASS_FAIRWAY)",
    )
    audit_parser.add_argument(
        "--vessel",
        default="STANDARD_SUEZMAX_85M",
        help="Vessel profile identifier (default: STANDARD_SUEZMAX_85M)",
    )
    audit_parser.add_argument(
        "--config-dir",
        default="configs",
        help="Path to configurations directory (default: configs)",
    )
    audit_parser.add_argument(
        "--incidents",
        default=None,
        help="Path to incidents CSV or JSON file (default: resolves from corridor spec)",
    )
    audit_parser.add_argument(
        "--telemetry",
        default=None,
        help="Path to civilian telemetry JSON file (default: resolves from corridor spec)",
    )
    audit_parser.add_argument(
        "--output-md",
        default=None,
        help="Output path for Markdown tearsheet (default: resolves from corridor)",
    )
    audit_parser.add_argument(
        "--output-manifest",
        default=None,
        help="Output path for JSON audit manifest (default: resolves from corridor)",
    )
    audit_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON result to stdout",
    )

    # 2. Verify command
    verify_parser = subparsers.add_parser("verify", help="Run tri-state repository verification")
    verify_parser.add_argument(
        "--target",
        "--target-dir",
        dest="target_dir",
        default=".",
        help="Target directory to verify (default: .)",
    )

    # 3. Live Meteo command
    meteo_parser = subparsers.add_parser(
        "live-meteo",
        help="Fetch live Open-Meteo hydrodynamics with Cubic Delta (psi_3) kernel smoothing",
    )
    meteo_parser.add_argument(
        "--corridor",
        default="GOG_BONNY_BRASS_FAIRWAY",
        help="Corridor identifier (default: GOG_BONNY_BRASS_FAIRWAY)",
    )
    meteo_parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Force circuit breaker fallback to historical 90th percentile",
    )
    meteo_parser.add_argument(
        "--config-dir",
        default="configs",
        help="Path to configurations directory (default: configs)",
    )
    meteo_parser.add_argument(
        "--output-json",
        default="LIVE_METOCEAN_TELEMETRY.json",
        help="Output path for JSON telemetry artifact (default: LIVE_METOCEAN_TELEMETRY.json)",
    )
    meteo_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )

    # 4. Live Incidents command
    inc_parser = subparsers.add_parser(
        "live-incidents",
        help="Fetch live OSINT incidents, calculate publication lag (Delta_t), and update GPD",
    )
    inc_parser.add_argument(
        "--feed-url",
        default=None,
        help="Optional custom incident feed URL",
    )
    inc_parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Force circuit breaker fallback",
    )
    inc_parser.add_argument(
        "--config-dir",
        default="configs",
        help="Path to configurations directory (default: configs)",
    )
    inc_parser.add_argument(
        "--output-json",
        default="LIVE_INCIDENTS_TELEMETRY.json",
        help="Output path for JSON telemetry artifact (default: LIVE_INCIDENTS_TELEMETRY.json)",
    )
    inc_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )

    # 5. Live Oracle command
    oracle_parser = subparsers.add_parser(
        "live-oracle",
        help="Execute unified live multi-sensor fusion oracle and emit live audit artifacts",
    )
    oracle_parser.add_argument(
        "--corridor",
        default="GOG_BONNY_BRASS_FAIRWAY",
        help="Corridor identifier (default: GOG_BONNY_BRASS_FAIRWAY)",
    )
    oracle_parser.add_argument(
        "--vessel",
        default="STANDARD_SUEZMAX_85M",
        help="Vessel profile identifier (default: STANDARD_SUEZMAX_85M)",
    )
    oracle_parser.add_argument(
        "--config-dir",
        default="configs",
        help="Path to configurations directory (default: configs)",
    )
    oracle_parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Force circuit breaker fallback on live adapters",
    )
    oracle_parser.add_argument(
        "--output-md",
        default="LIVE_ORACLE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md",
        help="Output path for live Markdown tearsheet (default: LIVE_ORACLE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md)",
    )
    oracle_parser.add_argument(
        "--output-manifest",
        default="LIVE_ORACLE_MANIFEST.json",
        help="Output path for live JSON audit manifest (default: LIVE_ORACLE_MANIFEST.json)",
    )
    oracle_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON result to stdout",
    )

    args = parser.parse_args(argv)

    if args.command == "verify":
        from .verification import run_verification
        return run_verification(Path(args.target_dir))

    elif args.command == "live-meteo":
        adapter = OpenMeteoHydroAdapter(
            config_dir=getattr(args, "config_dir", "configs"),
        )
        res = adapter.fetch_live_hydrodynamics(
            corridor_id=args.corridor,
            force_circuit_breaker=args.force_fallback,
        )

        out_path = Path(args.output_json) if args.output_json else None
        if out_path:
            out_path.write_text(json.dumps(res.to_dict(), indent=2), encoding="utf-8")

        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print("=" * 64)
            print("PHASE 3: LIVE OPEN-METEO HYDRODYNAMICS REST ADAPTER")
            print("=" * 64)
            print(f"Corridor:       {res.corridor_id}")
            print(f"Endpoint:       {res.endpoint_url}")
            print(f"Timestamp UTC:  {res.timestamp_utc}")
            print(f"Raw Hs:         {res.raw_wave_height_m:.4f} meters")
            print(f"Smoothed Hs:    {res.wave_height_m:.4f} meters ({res.smoothing_kernel})")
            print(f"Wave Period:    {res.wave_period_s:.2f} seconds")
            print(f"Estimated:      {res.is_estimated} {res.metadata_tag}")
            if out_path:
                print(f"Artifact:       {out_path.resolve()}")
            print("=" * 64)
            if res.is_estimated:
                print("STATUS: DEGRADED [CIRCUIT_BREAKER_ENGAGED]")
            else:
                print("STATUS: LIVE VERIFIED")
        return 0

    elif args.command == "live-incidents":
        adapter = IncidentFeedAdapter(
            config_dir=getattr(args, "config_dir", "configs"),
        )
        incidents, tag = adapter.fetch_incidents(
            feed_url=args.feed_url,
            force_circuit_breaker=args.force_fallback,
        )

        lags = adapter.calculate_publication_lags(incidents, in_hours=True)
        gpd_res = adapter.update_empirical_gpd(incidents)

        payload = {
            "incident_count": len(incidents),
            "metadata_tag": tag,
            "mean_lag_hours": sum(lags) / len(lags) if lags else 0.0,
            "gpd_shape_xi": gpd_res.shape_xi,
            "gpd_scale_sigma": gpd_res.scale_sigma,
            "var_99": gpd_res.var_99,
            "cvar_99": gpd_res.cvar_99,
        }

        out_path = Path(args.output_json) if args.output_json else None
        if out_path:
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("=" * 64)
            print("PHASE 3: LIVE OSINT INCIDENT FEED & GPD ADAPTER")
            print("=" * 64)
            print(f"Ingested Incidents: {len(incidents)}")
            print(f"Status Tag:         {tag}")
            print(f"Mean Lag (Delta_t): {payload['mean_lag_hours']:.2f} hours")
            print(f"GPD Shape (xi):     {gpd_res.shape_xi:.4f} (Cubic Exponential bounds)")
            print(f"GPD Scale (sigma):  {gpd_res.scale_sigma:.4f}")
            print(f"VaR 0.99 / CVaR:    {gpd_res.var_99:.2f} / {gpd_res.cvar_99:.2f}")
            if out_path:
                print(f"Artifact:           {out_path.resolve()}")
            print("=" * 64)
            if tag == "[LIVE_INCIDENTS]":
                print("STATUS: LIVE VERIFIED")
            else:
                print("STATUS: DEGRADED [CIRCUIT_BREAKER_ENGAGED]")
        return 0

    elif args.command == "live-oracle":
        corridor_id = getattr(args, "corridor", "GOG_BONNY_BRASS_FAIRWAY")
        vessel_id = getattr(args, "vessel", "STANDARD_SUEZMAX_85M")
        config_dir = getattr(args, "config_dir", "configs")
        force_fallback = getattr(args, "force_fallback", False)

        # 1. Fetch live hydrodynamics
        meteo_adapter = OpenMeteoHydroAdapter(config_dir=config_dir)
        hydro_res = meteo_adapter.fetch_live_hydrodynamics(
            corridor_id=corridor_id,
            force_circuit_breaker=force_fallback,
        )

        # 2. Ingest baseline dataset and run engine evaluation
        engine = MaritimeRiskEngine.from_config_files(
            corridor_id=corridor_id,
            vessel_profile_id=vessel_id,
            config_dir=config_dir,
        )

        inc_path = Path("data/sample_gog_osint_vintage.csv")
        raw_incidents, dataset_sha256 = OSINTFeedLoader.load_incidents_from_csv(inc_path)
        tel_path = Path("data/gog_bonny_brass_civilian_telemetry.json")
        raw_telemetry, telemetry_sha256 = OSINTFeedLoader.load_civilian_telemetry_from_json(tel_path)

        result = engine.evaluate(
            incidents=raw_incidents,
            telemetry=raw_telemetry,
            dataset_sha256=dataset_sha256,
            telemetry_sha256=telemetry_sha256,
        )

        output_md = Path(args.output_md)
        output_manifest = Path(args.output_manifest)

        output_md.write_text(result.to_markdown(), encoding="utf-8")
        manifest_builder = AuditManifestBuilder(output_manifest.resolve().parent)
        manifest_builder.write_manifest_file(
            output_rel_path=str(output_manifest.name),
            gpd_result=result.gpd_result,
            jwc_result=result.jwc_result,
            sprt_result=result.sprt_result,
            hydro_result=result.hydro_result,
        )

        if args.json:
            print(result.to_json())
        else:
            print("=" * 64)
            print("PHASE 3: LIVE MULTI-SENSOR FUSION ORACLE")
            print("=" * 64)
            print(f"Corridor:            {result.corridor_spec.corridor_id}")
            print(f"Live Metocean Hs:    {hydro_res.wave_height_m:.4f} m ({hydro_res.metadata_tag})")
            print(f"Deduped Incidents:   {result.dedup_incident_count}")
            print(f"GPD Shrunk xi:       {result.gpd_result.shape_xi:.4f}")
            print(f"Composite CVaR_0.99: {result.jwc_result.composite_cvar_99:.2f}")
            print(f"Tactical Dividend:   ${result.jwc_result.dividend_net_usd:,.2f} USD")
            print(f"Tear Sheet Artifact: {output_md.resolve()}")
            print(f"Manifest Artifact:   {output_manifest.resolve()}")
            print("=" * 64)
            print("STATUS: LIVE ORACLE EVALUATION COMPLETE")
        return 0

    elif args.command == "audit" or args.command is None:
        if args.command is None and len(sys.argv) > 1 and sys.argv[1] not in ["-h", "--help"]:
            parser.print_help()
            return 1

        corridor_id = getattr(args, "corridor", "GOG_BONNY_BRASS_FAIRWAY")
        vessel_id = getattr(args, "vessel", "STANDARD_SUEZMAX_85M")
        config_dir = getattr(args, "config_dir", "configs")

        engine = MaritimeRiskEngine.from_config_files(
            corridor_id=corridor_id,
            vessel_profile_id=vessel_id,
            config_dir=config_dir,
        )

        c_spec = engine.corridor_spec

        inc_arg = getattr(args, "incidents", None)
        if inc_arg is not None:
            incidents_path = Path(inc_arg)
        elif corridor_id == "GOG_BONNY_BRASS_FAIRWAY" and Path("data/sample_gog_osint_vintage.csv").exists():
            incidents_path = Path("data/sample_gog_osint_vintage.csv")
        elif c_spec.incident_dataset_path and Path(c_spec.incident_dataset_path).exists():
            incidents_path = Path(c_spec.incident_dataset_path)
        else:
            incidents_path = Path("data/sample_gog_osint_vintage.csv")

        tel_arg = getattr(args, "telemetry", None)
        if tel_arg is not None:
            telemetry_path = Path(tel_arg)
        elif c_spec.telemetry_dataset_path and Path(c_spec.telemetry_dataset_path).exists():
            telemetry_path = Path(c_spec.telemetry_dataset_path)
        else:
            telemetry_path = Path("data/gog_bonny_brass_civilian_telemetry.json")

        out_md_arg = getattr(args, "output_md", None)
        if out_md_arg is not None:
            output_md = Path(out_md_arg)
        elif corridor_id == "GOG_BONNY_BRASS_FAIRWAY":
            output_md = Path("PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md")
        else:
            output_md = Path(f"PHASE1_VINTAGE_AUDIT_{corridor_id}.md")

        out_mf_arg = getattr(args, "output_manifest", None)
        if out_mf_arg is not None:
            output_manifest = Path(out_mf_arg)
        elif corridor_id == "GOG_BONNY_BRASS_FAIRWAY":
            output_manifest = Path("PHASE1_AUDIT_MANIFEST.json")
        else:
            output_manifest = Path(f"PHASE1_AUDIT_MANIFEST_{corridor_id}.json")

        raw_incidents = []
        dataset_sha256 = None
        if incidents_path.exists():
            if incidents_path.suffix.lower() == ".csv":
                raw_incidents, dataset_sha256 = OSINTFeedLoader.load_incidents_from_csv(incidents_path)
            else:
                raw_incidents, dataset_sha256 = OSINTFeedLoader.load_incidents_from_json(incidents_path)

        raw_telemetry = []
        telemetry_sha256 = None
        if telemetry_path.exists():
            raw_telemetry, telemetry_sha256 = OSINTFeedLoader.load_civilian_telemetry_from_json(telemetry_path)

        result = engine.evaluate(
            incidents=raw_incidents,
            telemetry=raw_telemetry,
            dataset_sha256=dataset_sha256,
            telemetry_sha256=telemetry_sha256,
        )

        output_md.write_text(result.to_markdown(), encoding="utf-8")
        try:
            manifest_builder = AuditManifestBuilder(output_manifest.resolve().parent)
            manifest_builder.write_manifest_file(
                output_rel_path=str(output_manifest.name),
                gpd_result=result.gpd_result,
                jwc_result=result.jwc_result,
                sprt_result=result.sprt_result,
                hydro_result=result.hydro_result,
            )
        except Exception:
            output_manifest.write_text(result.to_json(indent=2), encoding="utf-8")

        if getattr(args, "json", False):
            print(result.to_json())
        else:
            print(f"Generated tear sheet: {output_md.resolve()}")
            print(f"Generated audit manifest: {output_manifest.resolve()}")
            print(f"Dataset SHA-256: {result.dataset_sha256}")
            print(f"Telemetry SHA-256: {result.telemetry_sha256}")
            print(f"Incidents: {result.raw_incident_count} raw -> {result.dedup_incident_count} deduplicated")
            print(f"GPD Shrunk xi: {result.gpd_result.shape_xi:.4f} (Raw: {result.gpd_result.raw_xi:.4f}, w: {result.gpd_result.shrinkage_weight_w:.4f})")
            print(f"Operational State: {result.corridor_spec.operational_state}")
            print(f"Composite CVaR_0.99: {result.jwc_result.composite_cvar_99:.2f}")
            print(f"Regime Multiplier: {result.jwc_result.regime_multiplier:.4f}x")
            print(f"JWC 7d Fair AP: {result.jwc_result.actuarial_7d_war_risk_ap_bps:.2f} bps (Market: {result.jwc_result.jwc_market_benchmark_bps:.2f} bps)")
            print(f"SPRT State: {result.sprt_result.state}")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
