# Repository Governance & Operating Rules
## `maritime-tail-risk-engine`

**Binding standard for all human and automated agents working on this repository.**

These rules codify verified professional, legal, and mathematical constraints derived during project development. They ensure operational compliance, identity integrity, and zero-compromise scientific rigor across all public outputs.

---

## 1. Professional Identity & Active-Duty Language Protection

### Rule 1.1 — Active-Duty Phrasing Invariant (Non-Negotiable)
- **Problem**: Ambiguous or inaccurate designations (e.g., "veteran") jeopardize active-service compliance, career safety, and institutional clarity.
- **Enforcement**: All references to "veteran" are permanently banned from this repository. The exact, authoritative formulation must be used across all bios, manifests, documentation, whitepapers, and commit logs:
  $$\text{"Nigerian Navy officer with 20+ years of operational experience"}$$

### Rule 1.2 — Single Immutable Source of Truth for Identity
- **Problem**: Discrepant author names, ORCIDs, or URLs across files undermine academic credibility, peer review, and bibliographic indexing.
- **Enforcement**: Every document, schema, and manifest must bind to the following verified credentials:
  - **Author Identity**: Nigerian Navy officer with 20+ years of operational experience
  - **ORCID**: [`0009-0008-0112-9273`](https://orcid.org/0009-0008-0112-9273)
  - **Legacy Terminology Ban**: All personal names, personal email addresses, personal URLs, commercial titles (e.g., "Lead Quantitative Risk Architect"), academic degree strings, and prohibited service terms ("veteran") are strictly banned.

---

## 2. Institutional Ethics & Legal Non-Conflict Firewall

### Rule 2.1 — Independent Personal Academic Research Capacity
- All work in this repository is conducted strictly in an **independent personal academic research capacity**.
- The repository does not represent official naval policy, strategy, or endorsements of any governmental entity.

### Rule 2.2 — 100% Public Civilian OSINT Only (Hard Firewall)
- Ingestion pipelines must exclusively ingest public, civilian-accessible telemetry and meteorological feeds:
  - Copernicus Marine Environment Monitoring Service (CMEMS) / ERA5
  - Global Fishing Watch (GFW) Sentinel-1 SAR public vessel detections
  - IMF PortWatch maritime corridor trade chokepoints
  - NOAA VIIRS Nightfire offshore flaring / optical observations
- **Zero Military C2 Coupling**: Under zero circumstances may this codebase ingest, interface with, simulate, or reference restricted military or naval Command & Control (C2) systems (e.g., Falcon Eye, RMAC).

### Rule 2.3 — Stated Value Proposition Binding
- The repository's authoritative value proposition is strictly codified as:
  $$\text{"Rigorous, public-OSINT-only, bi-temporal quantification of reporting-lag distortion for West African littoral fairways."}$$

### Rule 2.4 — Prohibition of Unverified Aspirational Claims
- Unverified Phase 2+ aspirational features—including claims regarding statutory reserve reductions, "live dynamic oracles", "regime-switching multipliers", or speculative commercial underwriting spreads—are strictly prohibited from all public documentation and audit outputs until independently audited in future project phases.

---

## 3. Commercialization & Sponsorship Calibration

### Rule 3.1 — Calibrated Community Sponsorship Launch
- In `.github/FUNDING.yml` and `.github/SPONSORS_PROFILE.md`, sponsorship tiers must be maintained conservatively:
  - **$15 / month**: Open-Source Compute & Telemetry Feed Ingestion Support.
  - **$50 / month**: Independent Academic Research Sustainability.
- Higher-tier institutional retainers ($500+) are strictly shelved until multiple independent tear sheets earn peer review and academic publication.

### Rule 3.2 — Non-Dilutive Grant Applications
- Grant proposals (e.g., NLnet NGI Zero Commons Fund, NumFOCUS Small Development Grants, Lacuna Fund) must emphasize:
  - Open-source public digital commons infrastructure.
  - Rigorous Python packaging standards (PEP 561, binary wheels, Hypothesis property fuzzing).
  - Open data benchmarks addressing reporting-lag bias in Sub-Saharan African waters.

---

## 4. Mathematical Rigor & Code Invariants

### Rule 4.1 — Anti-Hardcoding AST Gate (Gate 2)
- All domain literals (asset values, daily charter rates, baseline wave thresholds, prior shape parameters, corridor identifiers) must reside declaratively in `configs/` and load via `maritime_risk/core/specs.py`.
- No magic numbers or hardcoded corridor strings may appear inside `maritime_risk/core/` math modules. Enforced by `verify_repo.py`.

### Rule 4.2 — Strict Quantile Monotonicity
- Composite corridor risk estimates must satisfy strict mathematical ordering:
  $$\text{MSSA Baseline} \le \text{VaR}_{0.95} < \text{VaR}_{0.99} < \text{CVaR}_{0.99}$$
- Synthetic quantile clamping to artificial upper ceilings (e.g., `10.0 / 10.0`) is prohibited. Extreme tail shocks must be preserved to reflect Fréchet heavy-tail mechanics.

### Rule 4.3 — Small-Sample GPD Shrinkage
- Generalized Pareto Distribution (GPD) shape fitting on small sample sizes ($N_u < 50$) must use Hosking-Wallis Probability-Weighted Moments (PWM) and Empirical Bayes shrinkage toward a regional prior ($\xi_0 = 0.18$).
- Railing at optimization boundaries ($\xi \to -0.5000$) is treated as an algorithmic failure. Shrunk $\xi$ must reflect positive heavy-tail risk ($\xi \in [+0.05, +0.25]$).

### Rule 4.4 — Verification Precedes Release
- No commit or pull request may merge without running:
  1. `python verify_repo.py --target .` (All 4 Quad-Gates PASS in $< 1.0\text{s}$)
  2. `python -m pytest tests -v` (All 56+ tests PASS with zero mocks)
