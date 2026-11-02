# Security Policy & Forensic Audit Controls

## Scope & Legal Boundaries (100% Public Civilian OSINT Hard Firewall)
The `maritime-tail-risk-engine` processes strictly Open Source Intelligence (OSINT) maritime security data. It operates with zero classified, proprietary naval, or private commercial tracking inputs.
Under no circumstances does this repository reference, model, or ingest restricted military/naval Command & Control (C2) systems (such as Falcon Eye or RMAC).

## Personal Capacity & Non-Conflict Declaration
This project is an independent personal academic and quantitative research initiative created by a Nigerian Navy officer with 20+ years of operational experience. It is conducted strictly in a personal capacity using exclusively verifiable public civilian open-source intelligence (OSINT). It is entirely separate from and unconnected to official service duties, naval operations, or classified service communications. All code, datasets, and documentation are public civilian scientific artifacts published under the open-source MIT License.

The fairway corridor picture is enriched exclusively through 4 verifiable public civilian satellite and meteorological sensor feeds:
1. **Spaceborne SAR Dark-Vessel Ratio**: Global Fishing Watch (GFW) / ESA Copernicus Sentinel-1 public radar vessel detections (`GFW_SENTINEL1_SAR`).
2. **Marine MetOcean Envelope**: Copernicus Marine Service (CMEMS) / ECMWF ERA5 / Open-Meteo Marine (`COPERNICUS_ERA5_METOCEAN`) for Significant Wave Height ($H_s$) and wind speed.
3. **Public AIS Anchorage & Loitering Exposure**: IMF PortWatch / UN Global Platform public AIS port-call & anchorage waiting metrics (`IMF_PORTWATCH_AIS`).
4. **Offshore Infrastructure Thermal Continuity**: NASA FIRMS / NOAA VIIRS Nightfire public shortwave IR gas-flaring anomaly index (`NOAA_VIIRS_FIRMS`).

## Physical Isolation Invariants
1. **Sandbox Default**: The engine defaults to `MARITIME_ENV_MODE=sandbox`.
2. **Physical Exception Boundary**: In `application/isolation.py`, any attempt to open, write, or query `prod_maritime_vintage.db` while `env_mode="sandbox"` physically raises a `PermissionError`. This is an unbypassable programmatic barrier enforced at the connection acquisition layer.
3. **Storage CHECK Constraints**: The SQLite persistence schema strictly enforces `CHECK (pub_time >= event_time)` and severity interval bounds at the C-engine layer.

## Reporting a Vulnerability
If you discover a security vulnerability, temporal boundary bypass, or data contamination vector, please report it privately:
- **Email**: `security@maritime-tail-risk.internal` (or submit a private security advisory on GitHub).
- Do not disclose issues publicly until a fix and regression test have been merged.

