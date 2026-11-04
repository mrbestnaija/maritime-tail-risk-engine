---
name: build-track3-adapters
description: Scaffolds the Phase 3 Live OSINT and Environmental REST adapters for the maritime tail-risk engine, ensuring zero-hardcoding and cubic smoothing mathematics.
---

# Build Track 3 Adapters

Scaffolds the Phase 3 Live OSINT and Environmental REST adapters for the maritime tail-risk engine, ensuring zero-hardcoding and cubic smoothing mathematics.

## Instructions

1. **Create `configs/external_feeds.json`:**
   Write a declarative JSON configuration containing:
   - `open_meteo_url`: `"https://marine-api.open-meteo.com/v1/marine"`
   - `incident_feed_url`: `"https://api.example.com/maritime_incidents"`
   - `gulf_of_guinea_bbox`: `{"lat_min": -5.0, "lat_max": 7.0, "lon_min": -10.0, "lon_max": 12.0}`
   - `open_meteo`: Structured configuration with endpoints, bounding boxes, circuit breaker, and cubic delta kernel parameters.
   - Synchronize identical copies in both `configs/external_feeds.json` and `maritime_risk/configs/external_feeds.json`.

2. **Create `maritime_risk/infrastructure/open_meteo_adapter.py`:**
   Write the Python adapter. It MUST:
   - Import `urllib.request` and `json`.
   - Read the URL and bounding box from `configs/external_feeds.json`.
   - Implement `fetch_wave_heights(corridor_id="GOG_BONNY_BRASS_FAIRWAY", ...)` and `fetch_live_hydrodynamics(...)`.
   - Implement `smooth_cubic_delta(h_s)` and `smooth_wave_heights_cubic_delta(...)` mapping the mathematical Cubic Delta ($\psi_3(u) = (1 - |u|^3)^3$ for $|u| \le 1$) kernel to discrete wave heights.
   - Implement a circuit breaker (`try/except`) that returns `(historical_90th_percentile, "[ESTIMATED_HYDRODYNAMICS]")` if `urllib` times out or fails.
   - Expose root forwarder shim in `infrastructure/open_meteo_adapter.py`.

3. **Create `maritime_risk/infrastructure/incident_feed_adapter.py`:**
   Write the Python adapter. It MUST:
   - Import `urllib.request`, `json`, and `sqlite3`.
   - Read `incident_feed_url` and parameters from `configs/external_feeds.json`.
   - Implement `fetch_incidents(feed_url=None, timeout_sec=5.0)`.
   - Calculate $\Delta t = t_{\text{publication}} - t_{\text{observation}}$ for each ingested incident.
   - Implement `update_empirical_gpd(incidents, baseline_spec)` with Cubic Exponential bounds constraining tail parameter variance.
   - Implement `persist_incidents_to_sqlite(incidents, db_conn)` strictly enforcing SQLite `CHECK` constraints ($t_{\text{pub}} \ge t_{\text{event}}$).
   - Use a `try/except` circuit breaker returning `([], "[ESTIMATED_INCIDENTS]")` on failure.
   - Expose root forwarder shim in `infrastructure/incident_feed_adapter.py`.

4. **Verify:**
   After writing all files:
   - Run `python verify_repo.py --target .` to prove no hardcoded URLs or boundary violations exist.
   - Run `python -m pytest tests -v` to ensure full test suite passes under the 10.0-second SLA.
