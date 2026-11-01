"""Command-Line Interface (CLI) for Maritime Tail Risk Engine.

Entry-point for `maritime-risk` console script.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .application.engine import MaritimeRiskEngine
from .infrastructure.osint_feed_loader import OSINTFeedLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maritime-risk",
        description="Maritime Tail Risk Engine: Actuarial OSINT Underwriting & Multi-Sensor Fusion CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Evaluate / Audit command
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
        default="data/sample_gog_osint_vintage.csv",
        help="Path to incidents CSV or JSON file",
    )
    audit_parser.add_argument(
        "--telemetry",
        default="data/gog_bonny_brass_civilian_telemetry.json",
        help="Path to civilian telemetry JSON file",
    )
    audit_parser.add_argument(
        "--output-md",
        default="PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md",
        help="Output path for Markdown tearsheet",
    )
    audit_parser.add_argument(
        "--output-manifest",
        default="PHASE1_AUDIT_MANIFEST.json",
        help="Output path for JSON audit manifest",
    )
    audit_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON result to stdout",
    )

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Run tri-state repository verification")
    verify_parser.add_argument(
        "--target",
        "--target-dir",
        dest="target_dir",
        default=".",
        help="Target directory to verify (default: .)",
    )

    args = parser.parse_args(argv)

    if args.command == "verify":
        from .verification import run_verification
        return run_verification(Path(args.target_dir))

    elif args.command == "audit" or args.command is None:
        if args.command is None and len(sys.argv) > 1 and sys.argv[1] not in ["-h", "--help"]:
            parser.print_help()
            return 1

        corridor_id = getattr(args, "corridor", "GOG_BONNY_BRASS_FAIRWAY")
        vessel_id = getattr(args, "vessel", "STANDARD_SUEZMAX_85M")
        config_dir = getattr(args, "config_dir", "configs")
        incidents_path = Path(getattr(args, "incidents", "data/sample_gog_osint_vintage.csv"))
        telemetry_path = Path(getattr(args, "telemetry", "data/gog_bonny_brass_civilian_telemetry.json"))
        output_md = Path(getattr(args, "output_md", "PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md"))
        output_manifest = Path(getattr(args, "output_manifest", "PHASE1_AUDIT_MANIFEST.json"))

        engine = MaritimeRiskEngine.from_config_files(
            corridor_id=corridor_id,
            vessel_profile_id=vessel_id,
            config_dir=config_dir,
        )

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
            from infrastructure.audit_manifest import AuditManifestBuilder

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
            print(f"Composite CVaR_0.99: {result.jwc_result.composite_cvar_99:.2f} / 10.0")
            print(f"JWC 7d Fair AP: {result.jwc_result.actuarial_7d_war_risk_ap_bps:.2f} bps (Market: {result.jwc_result.jwc_market_benchmark_bps:.2f} bps)")
            print(f"SPRT State: {result.sprt_result.state}")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
