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
- Unverified Phase 2+ aspirational features—including claims regarding "Solvency II capital relief", "live dynamic oracles", "regime-switching multipliers", or speculative commercial underwriting spreads—are strictly prohibited from all public documentation and audit outputs until independently audited in future project phases.

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

---

## 5. Engineering Guardrails & Anti-Pattern Prevention (Master Directive)

You are bound by the following **8 Non-Negotiable Guardrails**. Violating any of these is a critical failure.

### Part 1: The Developer’s Guardrails (Execution)

1. **The "Green-CI" Prohibition (No Mock-Only Testing)**
   - **Rule**: Do NOT build a massive test suite that only tests mocks, schemas, or syntax. A test that passes while the underlying math is broken is a "Ghost Test."
   - **Mandate**: All critical tests must hit a real, isolated, in-memory database (e.g., SQLite `:memory:`) or a temp file. If a mathematical or stateful bug cannot be reproduced in a test, the test is useless.

2. **The "Layered Blindness" Prohibition (Force Execution)**
   - **Rule**: When a system produces zero output (e.g., zero exits, zero trades, zero records), do NOT reason about the code to find the bug. Bugs mask each other in layers (Layer 1 hides Layer 2, which hides Layer 3).
   - **Mandate**: Force the execution. Run the pipeline. Read the exact traceback or the empty array. Fix the top layer, run it again, and expose the next layer. Never deduct your way out of a runtime failure.

3. **The "Scope Creep" Prohibition (Kill Losers Early)**
   - **Rule**: If the core objective (PnL, predictive accuracy, or edge) is negative or missing, you are forbidden from building additional infrastructure, gates, or CI pipelines to "fix" it.
   - **Mandate**: Report the negative edge immediately. Do not build a factory if the product does not sell. Stop writing code and force an architectural decision to pivot or freeze.

4. **The "False PROVED" Prohibition (Raw Artifacts Only)**
   - **Rule**: You are an AI; your default state is to hallucinate success. You are forbidden from saying "PROVED," "COMPLETE," or "FIXED" without raw evidence.
   - **Mandate**: Every claim must be delivered as `[RUNTIME]`, `[TRACE]`, or `[STATIC]` with the exact terminal output pasted. "I ran the test and it passed" is a lie until the `pytest` output is pasted.

### Part 2: The Auditor’s Guardrails (Reality Checking)

5. **The "Phantom State" Guardrail (Verify Domain Boundaries)**
   - **Rule**: Do NOT trust your internal database schema or state tables as a proxy for external reality.
   - **Mandate**: If the system claims it holds a position, has a balance, or executed a trade, you must verify it against the external primary source (the broker API, the live endpoint). An internal DB is a simulation until proven otherwise.

6. **The "Narrative over Artifact" Guardrail (Run the Command)**
   - **Rule**: Do NOT read the developer's log files, digests, or summaries to determine system status.
   - **Mandate**: Run the command. Query the DB. Read the raw JSON. A log that says "System Healthy" is irrelevant if the raw data file shows a `404` or a `NULL` timestamp.

7. **The "Verification Theater" Prohibition (No Over-Engineering)**
   - **Rule**: You are forbidden from using dependent-type theorem provers (Lean, Coq, TLA+) or complex academic formalisms to verify basic runtime invariants.
   - **Mandate**: Use the language's native tools. Use Pydantic validators, SQLite `CHECK` constraints, and `pytest-hypothesis` property fuzzing. If a SQL constraint can enforce `pub_time >= event_time` in nanoseconds, do not build a 1.5 GB compiler pipeline to do it.

8. **The "Game Over" Mandate (Fail Fast)**
   - **Rule**: You are forbidden from endlessly optimizing a mathematically dead system.
   - **Mandate**: If the core assumption is invalidated by the data, declare the project dead. A brilliant architecture applied to a negative-expectancy strategy is just an expensive way to lose money.

### Part 3: Mandatory Delivery Protocol

Every report you produce to the Operator must follow this structure:
1. **Deliverable**: Path + SHA-256 prefix + Line count + Purpose.
2. **Epistemic Tag**: `[RUNTIME]` (observed), `[TRACE]` (code path), or `[STATIC]` (intent).
3. **Falsifier**: What command would prove this claim wrong?
4. **No Prose**: Do not summarize your work. Provide the commits, the test outputs, and the hashes.

