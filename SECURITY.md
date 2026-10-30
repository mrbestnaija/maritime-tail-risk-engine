# Security Policy & Forensic Audit Controls

## Scope & Legal Boundaries
The `maritime-tail-risk-engine` processes strictly Open Source Intelligence (OSINT) maritime security data. It operates with zero classified, proprietary naval, or private commercial tracking inputs.

## Physical Isolation Invariants
1. **Sandbox Default**: The engine defaults to `MARITIME_ENV_MODE=sandbox`.
2. **Physical Exception Boundary**: In `application/isolation.py`, any attempt to open, write, or query `prod_maritime_vintage.db` while `env_mode="sandbox"` physically raises a `PermissionError`. This is an unbypassable programmatic barrier enforced at the connection acquisition layer.
3. **Storage CHECK Constraints**: The SQLite persistence schema strictly enforces `CHECK (pub_time >= event_time)` and severity interval bounds at the C-engine layer.

## Reporting a Vulnerability
If you discover a security vulnerability, temporal boundary bypass, or data contamination vector, please report it privately:
- **Email**: `security@maritime-tail-risk.internal` (or submit a private security advisory on GitHub).
- Do not disclose issues publicly until a fix and regression test have been merged.
