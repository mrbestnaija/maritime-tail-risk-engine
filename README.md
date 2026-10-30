# maritime-tail-risk-engine

**Python-Native Clean Architecture Tail Risk Underwriting Engine for Maritime Security OSINT**

[![CI Verification](https://img.shields.io/badge/verification-python--native-green.svg)](#)
[![Architecture](https://img.shields.io/badge/architecture-clean--monolith-blue.svg)](#)
[![Fairway](https://img.shields.io/badge/fairway-GoG%20Bonny%2FBrass-orange.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Executive Summary

`maritime-tail-risk-engine` is an institutional-grade quantitative tail-risk evaluation platform designed for maritime war-risk and piracy underwriters, charterers, and risk committees. 

The engine processes publicly available Open Source Intelligence (OSINT) feeds covering the **Gulf of Guinea (GoG) - Bonny & Brass Fairway**, enforcing rigorous data hygiene, temporal monotonicity, and extreme value tail metrics ($\text{VaR}_{0.99}$ and $\text{CVaR}_{0.99}$).

### Rejection of Governance Theater (Python-Native Verification)
Rather than introducing complex theorem-prover toolchains (Lean 4) to check basic integer inequalities, this engine implements **defense-in-depth Python-native verification**:
1. **Pydantic Model Validators**: Catch the temporal paradox (`pub_time >= event_time`) and coordinate boundaries at the ingestion perimeter.
2. **SQLite C-Engine `CHECK` Constraints**: Physically enforce temporal ordering and interval validity at the storage layer.
3. **Hypothesis Property-Based Fuzzing**: Proves that the domain logic resists thousands of random timestamp and float permutations.
4. **AST Architecture Guards**: Statically verifies via Python's `ast` parser that the Core Domain layer has **zero** dependencies on outer layers.
5. **SHA-256 Lineage Hashes**: Generates cryptographic audit trails for all datasets and merged records.

---

## Clean Architecture Directory Layout

```
maritime-tail-risk-engine/
├── core/                        # Pure Domain Layer (AST-guarded; 0 outer imports)
│   ├── models.py                # MaritimeIncident, SeverityInterval, GeoCoordinates
│   └── metrics.py               # VaR_0.99, CVaR_0.99 (Expected Shortfall)
├── application/                 # Application Use Cases & Ingestion Services
│   ├── ingestion_hygiene.py     # Cross-feed deduplication, Union Envelope, Centroid
│   └── isolation.py             # Physical sandbox environment isolation guard
├── infrastructure/              # Storage & Data Loaders
│   ├── sqlite_storage.py        # SQLite repository with C-engine CHECK constraints
│   └── osint_feed_loader.py     # OSINT feed loader & SHA-256 digest engine
├── data/                        # Datasets (40-row realistic GoG sample CSV)
│   └── sample_gog_osint_vintage.csv
├── scripts/                     # Operational & Legacy Archival Utilities
│   ├── archive_legacy_pmx.sh
│   └── archive_legacy_pmx.ps1
└── tests/                       # 100% Mock-Free Verification Suite
    ├── core/
    │   ├── test_architecture_boundaries.py
    │   └── test_hypothesis_fuzzing.py
    ├── application/
    │   ├── test_ingestion_hygiene.py
    │   ├── test_isolation.py
    │   └── test_tear_sheet_integrity.py
    └── infrastructure/
        └── test_sqlite_constraints.py
```

---

## Quickstart

```bash
# Clone and setup
git clone https://github.com/mrbestnaija/maritime-tail-risk-engine.git
cd maritime-tail-risk-engine

# Run the full test suite
python -m pytest -v

# Generate the underwriting tear sheet
python generate_tear_sheet.py
```

---

## Commercial Artifact
The engine produces the first commercial underwriter tear sheet:
📄 **`PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md`**

Quantifies reporting-lag blind spots, cross-feed deduplication union envelopes, and the $\text{CVaR}_{0.99}$ tail risk distribution across the Bonny / Brass Fairway.
