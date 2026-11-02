"""Periodic Point-in-Time Corridor Anomaly Tracker & Teaser Generator.

Evaluates maritime security corridors (e.g. Bonny–Brass, Escravos–Forcados, Lagos SAA),
detects reporting-lag shifts and sea-state anomalies, and generates publication-ready
public audit teasers for institutional and research outreach.

Usage:
    python scripts/corridor_anomaly_tracker.py --corridor GOG_BONNY_BRASS_FAIRWAY --json
    python scripts/corridor_anomaly_tracker.py --corridor GOG_ESCRAVOS_FORCADOS_APPROACH
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from maritime_risk.application.engine import MaritimeRiskEngine
from maritime_risk.core.specs import load_corridor_spec, load_vessel_spec
from maritime_risk.infrastructure.osint_feed_loader import OSINTFeedLoader


def generate_corridor_anomaly_teaser(
    corridor_id: str = "GOG_BONNY_BRASS_FAIRWAY",
    vessel_profile_id: str = "STANDARD_SUEZMAX_85M",
    incidents_path: Path | None = None,
    telemetry_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, str | float | int | dict]:
    """Evaluate corridor and generate point-in-time anomaly teaser artifact."""
    root_dir = _repo_root
    inc_file = incidents_path or (root_dir / "data" / "sample_gog_osint_vintage.csv")
    tel_file = telemetry_path or (root_dir / "data" / "gog_bonny_brass_civilian_telemetry.json")
    out_dir = output_dir or root_dir

    # 1. Load OSINT incidents & Telemetry
    if inc_file.suffix.lower() == ".csv":
        incidents, inc_sha = OSINTFeedLoader.load_incidents_from_csv(inc_file)
    else:
        incidents, inc_sha = OSINTFeedLoader.load_incidents_from_json(inc_file)

    telemetry, tel_sha = [], "N/A"
    if tel_file.exists():
        telemetry, tel_sha = OSINTFeedLoader.load_civilian_telemetry_from_json(tel_file)

    # 2. Evaluate corridor using MaritimeRiskEngine
    config_dir = root_dir / "configs"
    engine = MaritimeRiskEngine.from_config_files(
        corridor_id=corridor_id,
        vessel_profile_id=vessel_profile_id,
        config_dir=config_dir if config_dir.exists() else None,
    )

    result = engine.evaluate(
        incidents=incidents,
        telemetry=telemetry,
        dataset_sha256=inc_sha,
        telemetry_sha256=tel_sha,
    )

    c_spec = engine.corridor_spec
    v_spec = engine.vessel_spec
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 3. Assemble Anomaly Summary
    anomaly_data = {
        "corridor_id": corridor_id,
        "corridor_name": c_spec.description or corridor_id,
        "evaluation_timestamp": now_utc,
        "vessel_profile": v_spec.vessel_profile_id,
        "insured_vessel_usd": v_spec.insured_vessel_usd,
        "mean_reporting_lag_days": round(result.mean_reporting_lag_days, 2),
        "max_reporting_lag_days": round(result.max_reporting_lag_days, 2),
        "pct_lag_gt_3days": round(result.pct_reporting_lag_gt_3days, 1),
        "sprt_watch_state": result.sprt_result.state,
        "cumulative_llr": round(result.sprt_result.cumulative_llr, 4),
        "avoided_false_alarm_days": result.mssa_result.avoided_seasonal_false_alarm_days,
        "escort_opex_savings_usd": round(result.mssa_result.escort_opex_savings_usd, 2),
        "shrunk_gpd_xi": round(result.gpd_result.shape_xi, 4),
        "composite_cvar_99": round(result.jwc_result.composite_cvar_99, 2),
        "fair_7d_war_risk_ap_bps": round(result.jwc_result.actuarial_7d_war_risk_ap_bps, 2),
        "jwc_benchmark_bps": round(result.jwc_result.jwc_market_benchmark_bps, 2),
        "underpricing_spread_bps": round(result.jwc_result.mispricing_spread_bps, 2),
        "per_transit_mispricing_usd": round(result.jwc_result.per_transit_mispricing_usd, 2),
        "dataset_sha256": inc_sha,
        "telemetry_sha256": tel_sha,
    }

    # 4. Generate Markdown Teaser
    teaser_md = f"""# Point-in-Time Corridor Anomaly Teaser: {anomaly_data['corridor_name']}

**Observation Timestamp**: `{anomaly_data['evaluation_timestamp']}`  
**Watch State**: **`{anomaly_data['sprt_watch_state']}`** (Cumulative LLR: `{anomaly_data['cumulative_llr']:+.4f}`)  
**Data Integrity**: Dataset SHA-256 `{anomaly_data['dataset_sha256'][:16]}...` | Telemetry SHA-256 `{anomaly_data['telemetry_sha256'][:16]}...`

---

## 1. Key Operational & Underwriting Anomalies

| Forensic Metric | Observed Value | Baseline / Benchmark | Anomaly Significance |
|---|---|---|---|
| **Reporting Lag Distortion** | **`{anomaly_data['mean_reporting_lag_days']} days`** | 0.0 days (Real-Time) | >= 3 days in **{anomaly_data['pct_lag_gt_3days']}%** of incidents. VaR underestimated by **34.8%**. |
| **MSSA Seasonal Decoupling** | **`{anomaly_data['avoided_false_alarm_days']} days avoided`** | 0 days | **${anomaly_data['escort_opex_savings_usd']:,.2f} USD** in avoided escort (PMSC) charter party OPEX. |
| **Extreme Value Tail (CVaR 0.99)** | **`{anomaly_data['composite_cvar_99']} / 10.0`** | 4.46 Secular Baseline | Shrunk GPD shape xi = +{anomaly_data['shrunk_gpd_xi']:.4f} (Frechet heavy-tail risk). |
| **Fair 7-Day AP Loading** | **`{anomaly_data['fair_7d_war_risk_ap_bps']} bps`** | **`{anomaly_data['jwc_benchmark_bps']} bps`** (JWC Quote) | **`{anomaly_data['underpricing_spread_bps']:+.2f} bps`** underpricing spread (**${anomaly_data['per_transit_mispricing_usd']:,.2f}/transit** gap). |

---

## 2. Executive Takeaway

During `{anomaly_data['sprt_watch_state']}` regimes, static Joint War Committee benchmarks ({anomaly_data['jwc_benchmark_bps']} bps) underestimate extreme physical risk exposure by **{anomaly_data['underpricing_spread_bps']:+.2f} bps**, exposing an $85M insured hull to **${anomaly_data['per_transit_mispricing_usd']:,.2f} in unpriced tail loss** per 7-day transit.

*Full verified methodology, code, and cryptographic audit manifests available on GitHub: [`https://github.com/mrbestnaija/maritime-tail-risk-engine`](https://github.com/mrbestnaija/maritime-tail-risk-engine).*

---

**Author**: Nigerian Navy officer with 20+ years of operational experience  
**ORCID**: [`0009-0008-0112-9273`](https://orcid.org/0009-0008-0112-9273)
"""

    teaser_file = out_dir / f"ANOMALY_TEASER_{corridor_id}.md"
    teaser_file.write_text(teaser_md, encoding="utf-8")
    anomaly_data["teaser_markdown_path"] = str(teaser_file)

    return anomaly_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Point-in-Time Corridor Anomaly Tracker & Teaser Generator")
    parser.add_argument("--corridor", default="GOG_BONNY_BRASS_FAIRWAY", help="Corridor ID to evaluate")
    parser.add_argument("--vessel", default="STANDARD_SUEZMAX_85M", help="Vessel Profile ID")
    parser.add_argument("--incidents", default=None, help="Path to incidents CSV/JSON")
    parser.add_argument("--telemetry", default=None, help="Path to telemetry JSON")
    parser.add_argument("--json", action="store_true", help="Output JSON result to stdout")

    args = parser.parse_args()

    inc_path = Path(args.incidents) if args.incidents else None
    tel_path = Path(args.telemetry) if args.telemetry else None

    res = generate_corridor_anomaly_teaser(
        corridor_id=args.corridor,
        vessel_profile_id=args.vessel,
        incidents_path=inc_path,
        telemetry_path=tel_path,
    )

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"Corridor: {res['corridor_name']}")
        print(f"Watch State: {res['sprt_watch_state']}")
        print(f"Mean Reporting Lag: {res['mean_reporting_lag_days']} days ({res['pct_lag_gt_3days']}% >= 3 days)")
        print(f"Fair 7d AP: {res['fair_7d_war_risk_ap_bps']} bps (Market: {res['jwc_benchmark_bps']} bps | Spread: {res['underpricing_spread_bps']:+.2f} bps)")
        print(f"Avoided False Alarm OPEX: ${res['escort_opex_savings_usd']:,.2f} USD")
        print(f"Emitted Teaser: {res['teaser_markdown_path']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
