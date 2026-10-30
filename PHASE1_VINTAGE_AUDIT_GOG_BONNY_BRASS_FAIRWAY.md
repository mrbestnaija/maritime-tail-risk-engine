# PHASE 1 VINTAGE AUDIT: GULF OF GUINEA (BONNY & BRASS FAIRWAY)

### COMMERCIAL DISCLAIMER
This document and the underlying risk model outputs are generated strictly for academic, underwriting research, and quantitative risk evaluation purposes based exclusively on publicly available Open Source Intelligence (OSINT) maritime security data. This report does not constitute official nautical advice, security operational clearance, or guaranteed insurance pricing. Neither the authors nor the operators of the maritime-tail-risk-engine assume liability for maritime navigation, chartering decisions, or asset deployment in war risk or high-risk areas (HRA).

---

### IDENTITY & AUDIT BLOCK
- **Engine**: `maritime-tail-risk-engine` (Phase 1 Vintage Audit)
- **Target Geographic Fairway**: Gulf of Guinea (GoG) - Bonny / Brass Fairway (`4.0°N - 4.5°N, 6.5°E - 7.5°E`)
- **Audit Timestamp**: `2026-10-30 07:33:19 UTC`
- **Architecture**: Clean Architecture / Modular Monolith (Core Domain Layer Isolation)
- **Verification Paradigm**: Python-Native Verification (Pydantic + SQLite CHECK Constraints + Hypothesis Fuzzing)
- **Dataset SHA-256 Lineage Hash**: `5927c3f07c917270141cb264acc738340e83c990ff80c5d68f86c84e6a533048`
- **Input Dataset Path**: `gog_bonny_brass_vintage_osint.json`

---

### 1. Ingestion Hygiene & Deduplication Audit

- **Raw OSINT Reports Ingested**: `12`
- **Deduplicated Physical Incidents**: `9`
- **Duplicate Reduction Ratio**: `25.0%`

#### The Union Envelope Invariant in Cross-Feed Reconciliation
When multiple intelligence agencies report the same incident (e.g. MDAT-GOG and IMB), severity intervals often diverge due to differing assessment criteria. Underwriter solvency mandates computing the **Union Envelope** ($\min(\text{min}), \max(\text{max})$):

| Deduplicated ID | Primary Vessel | Feeds Merged | Individual Feed Severities | Union Envelope Severity | Imputed Centroid (Lat, Lon) |
|---|---|---|---|---|---|
| `DEDUP-GOG-2023-0101-MDAT` | **MT BONNY VOYAGER** | IMB + MDAT-GOG | Multiple OSINT sources | **[3.5, 6.5]** | `(4.2265°N, 7.0835°E)` |
| `DEDUP-GOG-2023-0214-MDAT` | **MV DELTA TRADER** | DRYAD + MDAT-GOG | Multiple OSINT sources | **[5.5, 9.0]** | `(4.1525°N, 6.8475°E)` |
| `GOG-2023-0402-IMB` | CONTAINER FEEDER 1 | IMB | Single Feed | `[2.0, 4.0]` | `(4.3100°N, 7.1500°E)` |
| `GOG-2023-0518-MDAT` | TUG SUPPLY ATLANTIC | MDAT-GOG | Single Feed | `[7.0, 9.5]` | `(4.1100°N, 6.7200°E)` |
| `GOG-2023-0710-UKMTO` | LNG CARRIER RIVERS | UKMTO | Single Feed | `[1.5, 3.0]` | `(4.2800°N, 7.2200°E)` |
| `DEDUP-GOG-2023-0905-MDAT` | **CRUDE CARRIER NIGER** | IMB + MDAT-GOG | Multiple OSINT sources | **[4.5, 7.8]** | `(4.1810°N, 6.9490°E)` |
| `GOG-2023-1122-DRYAD` | GENERAL CARGO ESCRAVOS | DRYAD | Single Feed | `[3.0, 5.5]` | `(4.2400°N, 7.0500°E)` |
| `GOG-2024-0115-MDAT` | CHEMICAL TANKER PHOENIX | MDAT-GOG | Single Feed | `[6.5, 9.2]` | `(4.0900°N, 6.6800°E)` |
| `GOG-2024-0330-IMB` | BULK CARRIER FORCADOS | IMB | Single Feed | `[2.5, 4.8]` | `(4.2600°N, 7.1100°E)` |

> [!IMPORTANT]
> **Underwriter Risk Note**: Dropping secondary feeds or keeping only the first reported record causes a severe underestimation of the tail risk. In the MT BONNY VOYAGER incident, MDAT-GOG reported an upper severity of 5.0, whereas IMB confirmed automatic weapons elevating the upper severity to 6.5. The Union Envelope preserves the true upper risk boundary at 6.5.

---

### 2. Underwriting Quantitative Tail Risk Profile

Tail risk metrics evaluated across the Bonny / Brass fairway vintage using empirical percentile and Expected Shortfall formulations:

| Metric | Mathematical Definition | Lower Severity Bound (Optimistic) | Upper Severity Bound (Pessimistic / Underwriter) |
|---|---|---|---|
| **Mean Fairway Severity** | $\mathbb{E}[X]$ | `4.00 / 10.0` | **`6.59 / 10.0`** |
| **Value at Risk ($\text{VaR}_{0.99}$)** | $\inf \{ x \mid F(x) \ge 0.99 \}$ | `7.00 / 10.0` | **`9.50 / 10.0`** |
| **Expected Shortfall ($\text{CVaR}_{0.99}$)** | $\mathbb{E}[X \mid X \ge \text{VaR}_{0.99}]$ | `7.00 / 10.0` | **`9.50 / 10.0`** |

---

### 3. Institutional Invariant Verification & Defense Matrix

| Invariant Category | Defense Layer | Implementation Mechanism | Audit Status |
|---|---|---|---|
| **Architecture Boundaries** | Clean Architecture / AST Guard | Python AST inspection confirms `core/` contains 0 imports from `application/` or `infrastructure/` | **VERIFIED (PASS)** |
| **Temporal Monotonicity** | Pydantic + C SQLite CHECK | `CHECK (pub_time >= event_time)` at database layer; Pydantic model validator at boundary | **VERIFIED (PASS)** |
| **Severity Bounds** | SQLite CHECK Constraint | `CHECK (min_severity >= 0.0 AND max_severity <= 10.0 AND max_severity >= min_severity)` | **VERIFIED (PASS)** |
| **Physical Sandbox Isolation** | OS-Level File Guard | `application/isolation.py` raises `PermissionError` when `env_mode='sandbox'` targets production DB | **VERIFIED (PASS)** |
| **Cryptographic Lineage** | SHA-256 Audit Hash | Every incident record and raw file carries immutable SHA-256 digest | **VERIFIED (PASS)** |

---

### 4. Conclusion & Phase 1 Sign-Off

The `maritime-tail-risk-engine` Phase 1 implementation successfully demonstrates institutional-grade quantitative rigor without governance theater. By rejecting heavy theorem-prover detours and adopting Python-native verification (AST static boundary checks, Pydantic temporal validators, SQLite C-engine CHECK constraints, and cross-feed union envelopes), the engine delivers verifiable underwriting intelligence for the Bonny & Brass Fairway.