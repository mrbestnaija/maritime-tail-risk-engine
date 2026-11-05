# Grant Application: NLnet NGI Zero Commons Fund

**Fund**: NLnet Foundation — NGI Zero Commons Fund  
**Theme**: Verifiable Open Digital Commons, Public Data Infrastructure & Privacy-Preserving Mathematics  
**Project Title**: *Maritime Risk Commons: Open-Source Bi-Temporal Telemetry Verification & Tail-Risk Analytics Pipeline*  
**Requested Funding**: **€35,000 EUR** (Milestone-based disbursement)  
**Project Lead**: **Bestman Ezekwu Enock** (Maritime domain researcher with 20+ years of operational experience)  
**Location**: Abuja, Nigeria  
**ORCID**: [`0009-0008-0112-9273`](https://orcid.org/0009-0008-0112-9273) | **GitHub**: [`@mrbestnaija`](https://github.com/mrbestnaija)  
**Open Source Repository**: [`https://github.com/mrbestnaija/maritime-tail-risk-engine`](https://github.com/mrbestnaija/maritime-tail-risk-engine)  
**License**: MIT License (OSI-approved, 100% Free and Open Source Software)

---

## 1. Executive Summary & Problem Description

### The Problem
Commercial maritime transport across vulnerable international corridors (such as the Gulf of Guinea) relies heavily on proprietary risk scores, opaque war-risk benchmark surcharges, and closed intelligence feeds. This status quo suffers from two systemic flaws:
1. **Asymmetric Data Gatekeeping**: Coastal communities, academic researchers, and developing-nation port authorities cannot verify or audit the data underpinning massive insurance surcharges ($15\text{–}35\text{ bps}$ per transit on $\$85\text{M}$ hulls).
2. **The 3.4-Day Reporting-Lag Blind Spot**: Published bulletins suffer from variable multi-day publication delays (mean $3.40$ days, max $8.00$ days), leading to systemic underestimation of active surge threats by $34.8\%$.

### The Proposed Open Commons Solution
`Maritime Risk Commons` provides a transparent, verifiable, and mathematically auditable public telemetry pipeline. By fusing **100% public civilian satellite and meteorological telemetry** (ESA/Copernicus Sentinel-1 radar, Copernicus ERA5 wave envelopes, IMF PortWatch AIS, NOAA VIIRS Nightfire) with **bi-temporal point-in-time database constraints** and **Multivariate Singular Spectrum Analysis (MSSA)**, the project creates an open-source, non-proprietary public good for transparent risk calculation.

---

## 2. Public Benefit & NGI Alignment

- **Digital Commons & Open Knowledge**: Eliminates vendor lock-in and opaque pricing algorithms in global maritime logistics.
- **Privacy & Security by Design**: Relies strictly on civilian, aggregated, and publicly verifiable telemetry. Zero commercial surveillance, zero private tracking feeds, zero restricted military systems.
- **South-South & African Research Leadership**: Developed in Abuja, Nigeria, providing locally grounded, domain-verified empirical modeling for West African waters while adhering to global scientific standards.

---

## 3. Work Packages, Milestones & Financial Breakdown

The requested €35,000 budget is tied strictly to three verifiable open-source delivery milestones:

### Milestone 1: Multi-Corridor Public Civilian Telemetry Ingestion Adapters
- **Duration**: 2 Months
- **Funding**: **€12,000 EUR**
- **Concrete Deliverables**:
  1. Standardized feed adapters for Copernicus ERA5 (NetCDF4/REST), Global Fishing Watch Sentinel-1 SAR dark-vessel radar observations, and IMF PortWatch AIS fairway loitering queues.
  2. Automated missing-data sentinel imputation (`significant_wave_height_m: -999.0` $\to$ baseline) and temporal paradox validation (`t_pub >= t_event`).
  3. Continuous automated data-integrity test suite using Hypothesis property fuzzing across $10,000$ synthetic telemetry intervals.
- **Verification Evidence**: Passing pytest suite in CI/CD, published public ingestor modules under `maritime_risk.infrastructure`.

### Milestone 2: SQLite C-Engine Point-in-Time Core & Multi-Corridor Benchmarks
- **Duration**: 2 Months
- **Funding**: **€13,000 EUR**
- **Concrete Deliverables**:
  1. Expand verified multi-sensor datasets beyond the Bonny–Brass Fairway to include the **Escravos–Forcados Approach** and **Lagos SAA Anchorage**.
  2. Implement native SQLite bi-temporal storage with strict C-engine `CHECK` constraints and sandboxed permission guards.
  3. Emitted cryptographic SHA-256 lineage manifests (`AUDIT_MANIFEST.json`) for each corridor vintage.
- **Verification Evidence**: Public reproducible dataset releases on Zenodo and GitHub, Quad-Gate automated verification CLI completing in $< 1.0\text{s}$.

### Milestone 3: Pluggable Python SDK Packaging, Open Docs & Community Dissemination
- **Duration**: 2 Months
- **Funding**: **€10,000 EUR**
- **Concrete Deliverables**:
  1. Official PyPI release of `maritime-risk` with PEP 561 typed markers, protocol ports (`typing.Protocol`), and zero-mock automated tests.
  2. Comprehensive documentation hosted on ReadTheDocs / GitHub Pages with interactive Jupyter tutorial notebooks.
  3. Pre-print technical methodology paper published on arXiv / SSRN with reproducible execution instructions.
- **Verification Evidence**: `pip install maritime-risk`, live pre-print DOI, and public documentation site.

---

## 4. Sustainability & Governance

- **Maintainer Commitment**: Bestman Ezekwu Enock will maintain the core repository under the open-source MIT license with public GitHub issue tracking.
- **Non-Conflict Guarantee**: Conducted strictly in a personal academic research capacity with zero connection to restricted military C2 networks.
