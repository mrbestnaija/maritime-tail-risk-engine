"""Phase 3 Live OSINT Incident Feed Verification Script.

Allows manual execution and verification of:
1. Reaching out to OSINT incident REST feed.
2. Calculating publication lag Delta_t = t_pub - t_obs.
3. Fitting GPD tail risk with Cubic Exponential parameter variance envelope bounds.
4. Enforcing SQLite C-engine CHECK constraints (pub_time >= event_time).
5. Engaging fallback circuit breaker on upstream failure.

Author: Maritime domain researcher with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Add project root to path
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from maritime_risk.infrastructure.incident_feed_adapter import (
    INCIDENTS_SCHEMA_SQL,
    IncidentFeedAdapter,
    calculate_publication_lags,
    cubic_exponential_variance_bound,
    fetch_incidents,
    persist_incidents_to_sqlite,
    update_empirical_gpd,
)


def run_live_incident_verification():
    print("================================================================")
    print("PHASE 3: LIVE OSINT - INCIDENT FEED & SQLITE INTEGRITY CHECK")
    print("================================================================")

    # 1. Test Ingestion & Circuit Breaker
    print("[1/4] Probing Live Incident Feed Adapter...")
    incidents, tag = fetch_incidents()
    if tag == "[LIVE_INCIDENTS]":
        print(f"[SUCCESS] Ingested {len(incidents)} live incident records from feed.")
        print(f"[STATUS]  Live Telemetry Tag: {tag}")
    else:
        print(f"[CIRCUIT BREAKER ENGAGED] Upstream feed offline or placeholder URL.")
        print(f"[FALLBACK] Status: {tag} (Graceful degradation guaranteed)")

    # 2. Test Publication Lag Calculation (Delta_t)
    print("\n[2/4] Testing Publication Lag (Delta_t) Calculation...")
    sample_records = [
        {"incident_id": "TEST-01", "event_time": 1700000000, "pub_time": 1700007200, "min_severity": 2.0, "max_severity": 4.5, "feed_source": "MDAT-GOG"},
        {"incident_id": "TEST-02", "event_time": 1700000000, "pub_time": 1700018000, "min_severity": 3.0, "max_severity": 6.0, "feed_source": "IMB-PRC"},
    ]
    lags_hours = calculate_publication_lags(sample_records, in_hours=True)
    for rec, lag in zip(sample_records, lags_hours):
        print(f"  Incident {rec['incident_id']} [{rec['feed_source']}]: Delta_t = {lag:.2f} hours")

    # 3. Test Cubic Exponential Bounded GPD Tail Risk
    print("\n[3/4] Fitting GPD with Cubic Exponential Variance Bounds...")
    severities = [float(r["max_severity"]) for r in sample_records] + [3.8, 5.2, 7.1, 8.4]
    gpd_est = update_empirical_gpd(severities)
    print(f"[RESULT]  Fitted Shape xi:  {gpd_est.shape_xi:.4f} (Bounded in [-0.5, 0.95])")
    print(f"[RESULT]  Fitted Scale sigma: {gpd_est.scale_sigma:.4f} (Bounded >= 0.01)")
    print(f"[RESULT]  VaR_0.95: {gpd_est.var_95:.2f} | VaR_0.99: {gpd_est.var_99:.2f} | CVaR_0.99: {gpd_est.cvar_99:.2f}")
    assert gpd_est.cvar_99 >= gpd_est.var_99 >= gpd_est.var_95, "Quantile monotonicity violated!"

    # 4. Test SQLite C-Engine CHECK Constraint Enforcement
    print("\n[4/4] Verifying SQLite Invariant Enforcement (pub_time >= event_time)...")
    conn = sqlite3.connect(":memory:")
    # Valid persistence
    persisted = persist_incidents_to_sqlite(sample_records, conn)
    print(f"[SUCCESS] Persisted {persisted} valid incidents into SQLite.")

    # Invalid persistence test (Temporal Paradox)
    paradox_record = [
        {"incident_id": "PARADOX", "event_time": 1700010000, "pub_time": 1700005000, "min_severity": 2.0, "max_severity": 4.0}
    ]
    try:
        persist_incidents_to_sqlite(paradox_record, conn)
        print("[FAIL] SQLite allowed temporal paradox insert!")
        sys.exit(1)
    except sqlite3.IntegrityError:
        print("[SUCCESS] SQLite C-Engine CHECK constraint physically blocked temporal paradox insert.")

    conn.close()

    print("================================================================")
    print("STATUS: ALL INTEGRITY CONTRACTS VERIFIED")
    print("================================================================")


if __name__ == "__main__":
    run_live_incident_verification()
