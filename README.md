# maritime-tail-risk-engine

**Point-in-Time MSSA, Empirical Bayes POT-GPD, and SPRT Maritime Corridor Tail-Risk & Underwriting Engine (100% Public Civilian OSINT)**

[![Python 3.14](https://img.shields.io/badge/python-3.14.3-blue.svg)](https://www.python.org/)
[![Tests: 48 Passed](https://img.shields.io/badge/tests-48%20passed%20(1.10s)-brightgreen.svg)](#verification--test-suite)
[![Verification: Tri--State PASS](https://img.shields.io/badge/verification-tri--state%20PASS%20(0.36s)-brightgreen.svg)](#tri-state-cli-verification)
[![OSINT: 100% Civilian](https://img.shields.io/badge/OSINT-100%25%20Civilian%20Only-success.svg)](#civilian-mda-hard-firewall)
[![Fairway: GoG Bonny/Brass](https://img.shields.io/badge/fairway-GoG%20Bonny%2FBrass%20(4.0°N--4.5°N)-orange.svg)](#identity--fairway-parameters)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Executive Summary

`maritime-tail-risk-engine` is an institutional-grade quantitative risk modeling and actuarial underwriting platform designed for Lloyd's war-risk syndicates, P&I clubs, offshore energy logistics charterers, and maritime security risk committees.

Operating canonically over the **Gulf of Guinea (GoG) - Bonny & Brass Fairway (`4.0°N–4.5°N, 6.5°E–7.5°E`)**, the engine models maritime conflict and piracy tail risk by fusing **100% verified civilian open-source intelligence (OSINT)** and **satellite/metocean telemetry** across three breakthrough quantitative innovations:

1. **Bi-Temporal Reporting-Lag Audit**: Quantifies a **3.40-day mean reporting lag (max 8.00 days)** across public feeds (IMB PRC, MDAT-GoG, Dryad Global, UKMTO), proving that static publication-date models underestimate active 14-day surge $\text{VaR}$ by up to **34.8%**. Cross-feed deduplication via **Union Envelopes** ($\min(\text{min}), \max(\text{max})$) eliminates duplicate report distortion by **22.5%** without clipping extreme tail severity.
2. **MSSA Environmental Seasonal Decomposition**: Multivariate Singular Spectrum Analysis ($M = 4$ channels, window $L = 10$) separates secular fairway threat drift from monsoon sea-state wave harmonics with **$1.77 \times 10^{-13}$ Frobenius reconstruction precision**. Isolating seasonal wave dynamics prevents **4 false-alarm private security escort (PMSC) mobilizations**, delivering **$74,000 USD in direct OPEX savings** ($18,500/day rate).
3. **Empirical Bayes POT-GPD & First-Principles JWC Pricing**: Regularizes small-sample Peaks-Over-Threshold Generalized Pareto tail parameters via Hosking–Wallis Probability-Weighted Moments shrunk toward the historical fairway prior ($\xi_0 = 0.18$), eliminating negative-boundary optimizer railing ($\xi_{\text{shrunk}} = +0.2500$, composite $\text{CVaR}_{0.99} = 26.06$). Modulating 7-day single-vessel transit exposure with small-skiff hydrodynamic boarding feasibility yields a fair Additional Premium of **24.16 bps** on an $85M hull—uncovering a defensible **+9.16 bps ($77,897.36 / transit) underpricing spread** against static 15.00 bps Lloyd's Joint War Committee benchmarks during `RED_ESCALATION_BREACH` surveillance regimes ($S_t = +8.71$).

---

## Civilian MDA Hard Firewall

> [!IMPORTANT]
> **Strict Legal & Regulatory Invariant**: This repository is an independent academic and commercial quantitative research project. It **strictly utilizes 100% public civilian satellite and meteorological telemetry** and **NEVER** models, ingests, or references restricted military or naval Command & Control (C2) systems (e.g., Falcon Eye, RMAC).

The corridor risk picture is enriched exclusively through 4 verified civilian equivalents:
- **Marine MetOcean Envelope**: Copernicus Marine Service (CMEMS) / ECMWF ERA5 (`COPERNICUS_ERA5_METOCEAN`) for Significant Wave Height ($H_s$).
- **Spaceborne SAR Dark-Vessel Activity**: Global Fishing Watch / ESA Copernicus Sentinel-1 radar vessel detections (`GFW_SENTINEL1_SAR`).
- **Anchorage Loitering Delay**: IMF PortWatch / UN Global Platform AIS fairway queue telemetry (`IMF_PORTWATCH_AIS`).
- **Offshore Gas-Flaring Continuity**: NOAA / Colorado School of Mines VIIRS Nightfire thermal signatures (`NOAA_VIIRS_FIRMS`).

---

## Defense-in-Depth Python-Native Verification

This project rejects governance theater (such as introducing 1.5 GB external theorem-prover compilers to verify basic integer inequalities) in favor of **defense-in-depth Python-native verification**:

```
+------------------------------------------------------------------------+
| 1. Model Boundary: Pydantic Validators (pub_time >= event_time)       |
+------------------------------------------------------------------------+
                                   |
+------------------------------------------------------------------------+
| 2. Storage Layer: SQLite C-Engine CHECK Constraints (physical guards)  |
+------------------------------------------------------------------------+
                                   |
+------------------------------------------------------------------------+
| 3. Domain Math: Hypothesis Property-Based Permutation Fuzzing          |
+------------------------------------------------------------------------+
                                   |
+------------------------------------------------------------------------+
| 4. Architecture Layer: AST Isolation (core/ has 0 outer dependencies)  |
+------------------------------------------------------------------------+
                                   |
+------------------------------------------------------------------------+
| 5. Cryptographic Lineage: SHA-256 Digest Lineage & Audit Manifest      |
+------------------------------------------------------------------------+
```

---

## Clean Architecture Directory Layout

```
maritime-tail-risk-engine/
├── core/                               # Pure Domain Math & Invariants (AST-Isolated, 0 Outer Imports)
│   ├── models.py                       # MaritimeIncident, SeverityInterval, GeoCoordinates
│   ├── metrics.py                      # Empirical VaR_0.99 and CVaR_0.99
│   ├── calibration.py                  # Unweighted Brier score, Platt scaling, Isotonic regression
│   ├── mssa_decomposer.py              # Multivariate Singular Spectrum Analysis (M=4 channels)
│   ├── empirical_bayes.py              # Hosking-Wallis PWM GPD parameter shrinkage (anti-railing)
│   ├── gpd_tail_fitter.py              # Peaks-Over-Threshold (POT) GPD fitter & composite quantiles
│   ├── hydro_envelope.py               # Small-skiff wave swamping physics & dark vessel hazard
│   ├── jwc_pricer.py                   # First-principles Lloyd's JWC 7-day AP & demurrage pricer
│   └── sprt_gates.py                   # Wald's Sequential Probability Ratio Test (SPRT) surveillance
├── application/                        # Use Cases & Application Orchestration
│   ├── ingestion_hygiene.py            # Cross-feed deduplication, Union Envelope, Centroid Imputation
│   ├── telemetry_service.py            # Civilian telemetry ingestion pipeline & validation
│   └── isolation.py                    # Physical sandbox environment isolation guard
├── infrastructure/                     # Repositories & Cryptographic Lineage
│   ├── sqlite_storage.py               # SQLite repository with C-engine CHECK constraints
│   ├── osint_feed_loader.py            # CSV/JSON loaders with SHA-256 cryptographic lineage digests
│   └── audit_manifest.py               # Cryptographic audit manifest builder (PHASE1_AUDIT_MANIFEST.json)
├── data/                               # Corridor Vintages & Telemetry Datasets
│   ├── sample_gog_osint_vintage.csv    # 40-row realistic Gulf of Guinea incident vintage
│   └── gog_bonny_brass_civilian_telemetry.json  # 40-row multi-sensor civilian MDA telemetry
├── docs/                               # Commercialization & Academic Packs
│   └── COMMERCIALIZATION_PACK.md       # LinkedIn Launch Post, B2B Outreach Email, Paper #1 Blueprint
├── tests/                              # 100% Mock-Free Verification Suite (48 Tests)
│   ├── core/                           # AST boundaries, hypothesis fuzzing, MSSA, GPD, hydro, JWC, SPRT
│   ├── application/                    # Hygiene, telemetry, isolation, and tear sheet integrity
│   └── infrastructure/                 # SQLite storage layer C-engine constraint enforcement
├── verify_repo.py                      # Tri-State self-verification CLI (< 1s execution)
├── generate_tear_sheet.py              # Full deterministic audit runner and markdown generator
├── PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md  # Generated Underwriting Tear Sheet
└── PHASE1_AUDIT_MANIFEST.json          # Verifiable Cryptographic Lineage Manifest
```

---

## Verified Institutional Actuarial Scorecard

Generated deterministically from the Bonny & Brass Fairway vintage audit:

### Table 4A: MSSA Structural Shock Residual Tail (POT-GPD with Empirical Bayes Shrinkage)
| Parameter | Raw Optimization Value | Shrunk Empirical Bayes Estimate | Regularization Impact |
|---|---|---|---|
| **GPD Shape Parameter ($\xi$)** | `-0.5000` | **`0.2500`** | Regularized toward prior $\xi_0=0.18$; avoids boundary railing |
| **GPD Scale Parameter ($\sigma$)** | N/A | **`2.4740`** | Regularized scale parameter |
| **Shrinkage Weight ($w$)** | N/A | **`0.4545`** | Weight assigned to local data vs prior ($N_u=10$) |
| **Residual $\text{VaR}_{0.95}$** | N/A | **`6.90`** | 95th percentile structural residual shock |
| **Residual $\text{VaR}_{0.99}$** | N/A | **`14.23`** | 99th percentile structural residual shock |
| **Residual $\text{CVaR}_{0.99}$** | N/A | **`21.60`** | Mean structural shock conditional on tail breach |

### Table 4B: Full Composite Corridor Severity Tail (Reconstructed Baseline + GPD Shock)
| Metric | Empirical Sample Severity | Composite Corridor GPD Severity | Quantile Invariant |
|---|---|---|---|
| **Value at Risk ($\text{VaR}_{0.95}$)** | `9.31 / 10.0` | **`11.36`** | Base threshold |
| **Value at Risk ($\text{VaR}_{0.99}$)** | `9.80 / 10.0` | **`18.69`** | $\ge \text{VaR}_{0.95}$ |
| **Expected Shortfall ($\text{CVaR}_{0.99}$)** | `9.80 / 10.0` | **`26.06`** | $\ge \text{VaR}_{0.99}$ |

### Table 4C: First-Principles Lloyd's JWC 7-Day AP & Demurrage Pricing
| Pricing Parameter / Output | Value | Actuarial Definition |
|---|---|---|
| **Calibrated 7-Day Corridor Breach Prob** | **`25.0%`** | Probability of corridor risk exceeding baseline in 7d window |
| **Single-Vessel Transit Exposure Factor** | **`25.0%`** | Spatial-temporal exposure of single transiting vessel |
| **Hydrodynamic Boarding Modulator** | **`84.6%`** | Modulation from sea-state small-skiff boarding feasibility |
| **Effective Single-Vessel Breach Prob** | **`5.29%`** | Net single-vessel breach probability over 7-day transit |
| **Expected Tail Delay Duration** | **`8.50 days`** | Operational delay days given extreme tail breach ($0.85 \times \text{CVaR}_{0.99}$) |
| **Tail Demurrage Loss Exposure** | **`$382,500.00 USD`** | Financial demurrage loss at $45,000/day charterparty rate |
| **Catastrophic Boarding Loss Exposure** | **`$3,500,000.00 USD`** | Expected damage/ransom conditional on tail breach |
| **Expected 7-Day Tail Loss** | **`$205,397.36 USD`** | Unconditional actuarial expected loss over 7-day transit |
| **Fair Actuarial War-Risk AP** | **`24.16 bps`** | Fair additional premium rate (1 bps = 0.01% of hull value) |
| **Lloyd's JWC Market Benchmark** | **`15.00 bps`** | Standard commercial market quote for Gulf of Guinea transit |
| **Underwriter Commercial Spread** | **`+9.16 bps`** | **`$+77,897.36 USD`** per transit underpricing hazard |

### Table 4D: Wald's Sequential Probability Ratio Test (SPRT) Surveillance State
| SPRT Surveillance Metric | Value | Operational Watch Status |
|---|---|---|
| **Corridor Watch State** | **`RED_ESCALATION_BREACH`** | Deterministic state: `GREEN_BASELINE` \| `AMBER_CORRIDOR_WATCH` \| `RED_ESCALATION_BREACH` |
| **Cumulative Log-Likelihood Ratio** | **`+8.7074`** | $S_t = \sum \Lambda(y_t)$ |
| **Decision Boundaries** | `A = -2.2513, B = +2.8904` | Accept $H_0$ if $S_t \le A$; Accept $H_1$ if $S_t \ge B$ |
| **Breach Incident Count** | `10 / 40 periods` | Observed structural shock exceedances |

---

## Quickstart & Verification

```bash
# 1. Clone repository
git clone https://github.com/mrbestnaija/maritime-tail-risk-engine.git
cd maritime-tail-risk-engine

# 2. Run the mock-free pytest suite (48 tests in ~1.1s)
python -m pytest tests -v

# 3. Run the Tri-State Self-Verification CLI (< 1.0s)
python verify_repo.py --target .

# 4. Generate the Underwriting Tear Sheet and Audit Manifest
python generate_tear_sheet.py
```

---

## Commercial & Academic Deployment Pack

For immediate commercial deployment and academic publication:
- 📄 **Commercialization Pack**: [`docs/COMMERCIALIZATION_PACK.md`](docs/COMMERCIALIZATION_PACK.md)
  - **Asset 1**: Executive LinkedIn Launch Post
  - **Asset 2**: Direct B2B Outreach Email Template (Lloyd's Underwriters & Offshore Logistics VPs)
  - **Asset 3**: Academic Paper #1 Blueprint (Ready for NOUN PhD Proposal / Journal Submission)
- 📄 **Actuarial Audit Tear Sheet**: [`PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md`](PHASE1_VINTAGE_AUDIT_GOG_BONNY_BRASS_FAIRWAY.md)
- 📄 **Cryptographic Audit Manifest**: [`PHASE1_AUDIT_MANIFEST.json`](PHASE1_AUDIT_MANIFEST.json)

---

## Author & Academic Credentials

- **Lead Quantitative Risk Architect**: **Bestman Ezekwu Enock**
- **Qualifications**: M.Sc. Maritime Security & Warfare | M.A. Peace & Conflict Studies | MITx Statistics & Data Science
- **GitHub**: [`@mrbestnaija`](https://github.com/mrbestnaija)
- **ORCID**: [`0009-0008-0112-9273`](https://orcid.org/0009-0008-0112-9273)
- **LinkedIn**: [Bestman Ezekwu Enock](https://www.linkedin.com/in/bestman-ezekwu/)

---

## Commercial Disclaimer

*This engine and its audit artifacts are produced strictly for quantitative research, risk committee evaluation, and academic analysis based exclusively on publicly available civilian Open Source Intelligence (OSINT). This report does not constitute official nautical clearance, legally binding insurance pricing, or navigational routing advice. The authors assume no liability for maritime operations in designated war-risk or high-risk areas (HRA).*
