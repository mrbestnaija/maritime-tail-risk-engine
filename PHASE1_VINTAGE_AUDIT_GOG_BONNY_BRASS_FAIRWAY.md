# PHASE 1 VINTAGE AUDIT: GULF OF GUINEA (GOG) - BONNY / BRASS FAIRWAY

### COMMERCIAL DISCLAIMER
This document and the underlying risk model outputs are generated strictly for academic, underwriting research, and quantitative risk evaluation purposes based exclusively on publicly available Open Source Intelligence (OSINT) maritime security data. This report does not constitute official nautical advice, security operational clearance, or guaranteed insurance pricing. Neither the authors nor the operators of the maritime-tail-risk-engine assume liability for maritime navigation, chartering decisions, or asset deployment in war risk or high-risk areas (HRA).

---

### IDENTITY & AUDIT BLOCK
- **Engine**: `maritime-tail-risk-engine` (Phase 2B First-Principles & Multi-Sensor Fusion)
- **Target Geographic Fairway**: Gulf of Guinea (GoG) - Bonny / Brass Fairway (`4.0°N - 4.5°N, 6.5°E - 7.5°E`)
- **Operational State**: `UNDERWAY`
- **Regime Multiplier**: `1.4688x`
- **Audit Timestamp**: `2026-11-04 06:54:43 UTC`
- **Architecture**: Clean Architecture / Modular Monolith (Core Domain Layer Isolation)
- **Verification Paradigm**: Python-Native Verification (Pydantic + SQLite CHECK Constraints + Hypothesis Fuzzing + Tri-State CLI)
- **Dataset SHA-256 Lineage Hash**: `cac4ca9116cbb0f0038e4df511092f2a1025eabc840a0a5447f97849f88af39c`
- **Telemetry SHA-256 Lineage Hash**: `c3685e086d228af1f3d0e44314f3c50e5af000406c0d55559d68d77c95157db7`
- **Audit Manifest**: `PHASE1_AUDIT_MANIFEST.json` (Cryptographic Lineage Verifiable)
- **Input Incident Dataset**: Ingested (40 records)
- **Input Telemetry Dataset**: Multi-Sensor Stream

---

### 1. Reporting-Lag Blind-Spot Distortion Analysis

In high-risk maritime corridors, intelligence reporting latency creates an insidious **underwriting blind spot**:
underwriters pricing risk based on published intelligence bulletins are pricing yesterday's threat level, while real-time security events remain unpublicized for days.

| Reporting Lag Metric | Observed Value | Underwriting Impact |
|---|---|---|
| **Mean Reporting Lag** | **`3.40 days`** | Average delay before an incident appears in OSINT feeds |
| **Maximum Reporting Lag** | **`8.00 days`** | Worst-case information blackout observed in vintage |
| **Multi-Day Lag Ratio ($\ge 3$ Days)** | **`50.0%`** | Proportion of incidents operating in the blind-spot window |

> [!WARNING]
> **Underwriter Blind-Spot Hazard**: During a 3 to 7 day reporting lag window, active pirate action groups (PAGs) remain undetected by published feeds. If underwriters compute rolling 14-day VaR on publication date rather than occurrence date, active fairway risk is underestimated by up to **34.8%** during surge periods.

#### Ingestion Hygiene & Deduplication Audit
- **Raw OSINT Reports Ingested**: `40`
- **Deduplicated Physical Incidents**: `31`
- **Duplicate Reduction Ratio**: `22.5%`

#### The Union Envelope Invariant in Cross-Feed Reconciliation
When multiple intelligence agencies report the same incident (e.g. MDAT-GOG, IMB, and Dryad), severity intervals often diverge due to differing assessment criteria. Underwriter solvency mandates computing the **Union Envelope** ($\min(\text{min}), \max(\text{max})$):

| Deduplicated ID | Primary Vessel | Feeds Merged | Individual Feed Severities | Union Envelope Severity | Imputed Centroid (Lat, Lon) |
|---|---|---|---|---|---|
| `DEDUP-GOG-2023-001-MDAT` | **MT BONNY VOYAGER** | IMB + MDAT-GOG | Multiple OSINT sources | **[3.5, 6.5]** | `(4.2265°N, 7.0835°E)` |
| `DEDUP-GOG-2023-002-MDAT` | **MV DELTA TRADER** | DRYAD + MDAT-GOG | Multiple OSINT sources | **[5.5, 9.2]** | `(4.1523°N, 6.8477°E)` |
| `GOG-2023-003-IMB` | CONTAINER FEEDER 1 | IMB | Single Feed | `[2.0, 4.0]` | `(4.3100°N, 7.1500°E)` |
| `GOG-2023-004-MDAT` | UNKNOWN TANKER | MDAT-GOG | Single Feed | `[1.5, 3.0]` | `(4.2250°N, 7.0850°E)` |
| `GOG-2023-005-UKMTO` | LNG CARRIER RIVERS | UKMTO | Single Feed | `[1.5, 3.5]` | `(4.2800°N, 7.2200°E)` |
| `DEDUP-GOG-2023-006-MDAT` | **TUG SUPPLY ATLANTIC** | IMB + MDAT-GOG | Multiple OSINT sources | **[6.5, 9.5]** | `(4.1125°N, 6.7175°E)` |
| `GOG-2023-007-IMB` | BULK CARRIER FORCADOS | IMB | Single Feed | `[2.5, 4.5]` | `(4.2600°N, 7.1100°E)` |
| `GOG-2023-008-DRYAD` | GENERAL CARGO ESCRAVOS | DRYAD | Single Feed | `[3.0, 5.5]` | `(4.2400°N, 7.0500°E)` |
| `DEDUP-GOG-2023-009-MDAT` | **CRUDE CARRIER NIGER** | IMB + MDAT-GOG | Multiple OSINT sources | **[4.5, 7.8]** | `(4.1810°N, 6.9490°E)` |
| `GOG-2023-010-NIMASA` | FISHING TRAWLER DELTA | NIMASA | Single Feed | `[2.0, 3.8]` | `(4.3500°N, 7.2000°E)` |
| `DEDUP-GOG-2023-011-MDAT` | **CHEMICAL TANKER PHOENIX** | DRYAD + MDAT-GOG | Multiple OSINT sources | **[6.5, 9.6]** | `(4.0925°N, 6.6775°E)` |
| `GOG-2023-012-UKMTO` | UNKNOWN CARGO | UKMTO | Single Feed | `[2.0, 4.0]` | `(4.2250°N, 7.0850°E)` |
| ... | *(+19 additional deduplicated incidents)* | ... | ... | ... | ... |

> [!IMPORTANT]
> **Underwriter Risk Note**: Dropping secondary feeds or keeping only the first reported record causes a severe underestimation of the tail risk. The Union Envelope preserves the true upper risk boundary across all reporting intelligence feeds.

---

### 2. Multi-Sensor Civilian OSINT & Hydrodynamic Physics Fusion

The corridor risk picture is enriched using **4 verifiable public civilian satellite & meteorological sensors** alongside hydrodynamic small-skiff boarding physics (Hard Firewall: Zero military or restricted naval C2 feeds):

| Civilian Sensor Channel | Data Provider Equivalent | Physical Hazard Metric | Corridor Observed Mean [Min, Max] |
|---|---|---|---|
| **Marine MetOcean Envelope** | `COPERNICUS_ERA5_METOCEAN` | Significant Wave Height ($H_s$ in meters) | `1.62m` |
| **Spaceborne SAR Dark Ratio** | `GFW_SENTINEL1_SAR` | Radar Targets Lacking Public AIS (%) | `25.9%` |
| **Anchorage Loitering Delay** | `IMF_PORTWATCH_AIS` | Fairway Waiting / Queue Duration (hrs) | `18.5 hrs` |
| **Offshore Thermal Continuity** | `NOAA_VIIRS_FIRMS` | Terminal Gas-Flaring Continuity Index | `0.84 [0.65, 0.98]` |

#### Hydrodynamic Skiff Swamping Physics
- **Observed Mean $H_s$**: `1.62m`
- **Skiff Boarding Feasibility**: **`69.3%`** (logistic transition at $H_0 = 1.85\text{m}$)
- **Composite Dark Vessel Hazard Score**: **`1.79 / 10.0`**

> [!NOTE]
> **Physical Boarding Invariant**: In maritime security fairways, pirate skiff boardings drop to near zero when significant wave height exceeds swamping thresholds. High SAR dark vessel activity coinciding with calm sea-states creates a critical attack window.

---

### 3. MSSA Seasonal Decomposition & Avoided Escort False-Alarm OPEX Savings

Multivariate Singular Spectrum Analysis ($M = 4$ channels, window length $L = 10$) separates secular fairway drift from monsoon sea-state seasonal harmonics and isolated structural shocks:
$$\mathbf{Y}_t = \mathbf{T}_t \text{ (Secular Trend)} + \mathbf{S}_t \text{ (Seasonal Harmonics)} + \mathbf{R}_t \text{ (Structural Shock Residual)}$$

| MSSA Metric | Value | Forensic / Operational Significance |
|---|---|---|
| **Frobenius Reconstruction Error** | **`1.77e-13`** | Strict mathematical invariant ($\|\mathbf{Y} - (\mathbf{T}+\mathbf{S}+\mathbf{R})\|_F < 10^{-9}$) verified |
| **Secular + Seasonal Baseline Anchor** | **`4.46 / 10.0`** | Reconstructed fairway baseline (Channel 0 trend + seasonal harmonics) |
| **Explained Variance Ratio (EVR)** | **`0.9752`** | Proportion of total fairway variance captured by leading 3 triplets |
| **Avoided False Alarm Days** | **`4 days`** | Periods where raw threat spiked purely due to seasonal harmonics while structural shock remained benign |
| **Avoided Escort OPEX Savings** | **`$74,000.00 USD`** | Direct commercial savings from avoiding unnecessary private escort vessel (PMSC) charters |

> [!TIP]
> **Commercial Value Proof**: At standard security escort rates of **$18,500/day**, isolating seasonal sea-state harmonics prevents **4 false-alarm escort mobilizations**, returning **$74,000.00 in verified OPEX savings** across this vintage window.

---

### 4. POT-GPD Tail Risk, Empirical Bayes Regularization & First-Principles JWC Pricing

#### Table 4A: MSSA Structural Shock Residual Tail (POT-GPD with Empirical Bayes Shrinkage)
Small-sample MLE on GPD shape $\xi$ has extreme variance when exceedance counts are small. We apply **Empirical Bayes Shrinkage** against the historical prior ($\xi_0 = 0.18, \sigma_0 = 1.50, \kappa = 12.0$), preventing optimizer railing at $\xi = -0.5000$:

| Parameter | Raw Optimization Value | Shrunk Empirical Bayes Estimate | Regularization Impact |
|---|---|---|---|
| **GPD Shape Parameter ($\xi$)** | `-0.5000` | **`0.3936`** | Regularized toward prior $\xi_0=0.18$; avoids boundary railing |
| **GPD Scale Parameter ($\sigma$)** | N/A | **`2.4740`** | Regularized scale parameter |
| **Shrinkage Weight ($w$)** | N/A | **`0.4545`** | Weight assigned to local data vs prior ($N_u=10$) |
| **Residual $\text{VaR}_{0.95}$** | N/A | **`7.55`** | 95th percentile structural residual shock |
| **Residual $\text{VaR}_{0.99}$** | N/A | **`18.02`** | 99th percentile structural residual shock |
| **Residual $\text{CVaR}_{0.99}$** | N/A | **`32.51`** | Mean structural shock conditional on tail breach |

#### Table 4B: Full Composite Corridor Severity Tail (Reconstructed Baseline + GPD Shock)
To eliminate the visual scale mismatch where residual shock metrics were compared against raw empirical metrics, the composite corridor severity tail anchors the GPD structural shock to the reconstructed MSSA baseline. Unclamped composite quantiles preserve strict monotonic differentiation:

| Metric | Empirical Sample Severity | Composite Corridor GPD Severity | Quantile Invariant |
|---|---|---|---|
| **Value at Risk ($\text{VaR}_{0.95}$)** | `9.31` | **`12.01`** | Base threshold |
| **Value at Risk ($\text{VaR}_{0.99}$)** | `9.80` | **`22.49`** | $\ge \text{VaR}_{0.95}$ |
| **Expected Shortfall ($\text{CVaR}_{0.99}$)** | `9.80` | **`36.97`** | $\ge \text{VaR}_{0.99}$ |

> [!NOTE]
> **Open-Ended Composite Severity Scale**: Reconstructed composite metrics combine the secular+seasonal fairway baseline with the GPD extreme tail residual shock without artificial ceiling clamping, preserving strict mathematical quantile ordering: $\text{CVaR}_{0.99} > \text{VaR}_{0.99} > \text{VaR}_{0.95}$.

#### Table 4C: First-Principles Lloyd's JWC 7-Day AP & Demurrage Pricing
Replaces naive multiplier heuristics with first-principles underwriting loss expectation on a **$85,000,000 USD** hull, modeling single-voyage spatial-temporal exposure and hydrodynamic boarding physics:

| Pricing Parameter / Output | Value | Actuarial Definition |
|---|---|---|
| **Operational State** | **`UNDERWAY`** | Navigation posture (e.g. UNDERWAY transit fairway vs AT_ANCHOR anchorage) |
| **Macro Regime Multiplier** | **`1.4688x`** | Liquidity friction / port waiting congestion multiplier |
| **Calibrated 7-Day Corridor Breach Prob** | **`25.0%`** | Probability of corridor risk exceeding baseline in 7d window |
| **Single-Vessel Transit Exposure Factor** | **`25.0%`** | Spatial-temporal exposure of single transiting vessel |
| **Hydrodynamic Boarding Modulator** | **`84.6%`** | Modulation from sea-state small-skiff boarding feasibility |
| **Effective Single-Vessel Breach Prob** | **`5.29%`** | Net single-vessel breach probability over 7-day transit |
| **Expected Tail Delay Duration** | **`31.43 days`** | Operational delay days given extreme tail breach |
| **Tail Demurrage Loss Exposure** | **`$1,414,178.16 USD`** | Financial demurrage loss at $45,000/day charterparty rate |
| **Catastrophic Boarding Loss Exposure** | **`$12,940,192.28 USD`** | Expected damage/ransom conditional on tail breach |
| **Expected 7-Day Tail Loss** | **`$1,115,360.90 USD`** | Unconditional actuarial expected loss over 7-day transit |
| **Fair Actuarial War-Risk AP** | **`131.22 bps`** | Fair additional premium rate (1 bps = 0.01% of hull value) |
| **Lloyd's JWC Market Benchmark** | **`15.00 bps`** | Standard commercial market quote for transit |
| **Underwriter Commercial Spread** | **`+116.22 bps`** | **`$+987,860.90 USD`** per transit underpricing hazard |

#### Table 4D: Tactical Hardening Arbitrage (Escort & Anchorage Capital Dividend)
Evaluates kinetic hazard suppression and capital relief across operational postures:

| Arbitrage / Dividend Metric | Value | Forensic / Operational Significance |
|---|---|---|
| **Lone Underway AP Rate** | **`10.53 bps`** | Fair AP for unescorted fairway voyage (`$89,498.45 USD`) |
| **Escorted Underway AP Rate** | **`3.16 bps`** | Fair AP with dedicated naval escort bubble (`$26,889.52 USD`) |
| **Gross AP Premium Savings** | **`$62,608.93 USD`** | Direct insurance premium discount achieved via escort |
| **Escort Deployment OPEX** | **`$129,500.00 USD`** | Charterparty security cost at $18,500/day |
| **Net Tactical Arbitrage Dividend** | **`$-66,891.07 USD`** | AVOIDED OPEX (Threat benign/suppressed) |
| **Underwriter Capital Relief** | **`$42,627.36 USD`** | Solvency II Expected Shortfall reserve charge reduction |

#### Table 4E: Wald's Sequential Probability Ratio Test (SPRT) Surveillance State
Sequential hypothesis testing ($H_0: p_0 = 0.05$ vs $H_1: p_1 = 0.20$):

| SPRT Surveillance Metric | Value | Operational Watch Status |
|---|---|---|
| **Corridor Watch State** | **`RED_ESCALATION_BREACH`** | Deterministic state: `GREEN_BASELINE` \| `AMBER_CORRIDOR_WATCH` \| `RED_ESCALATION_BREACH` |
| **Cumulative Log-Likelihood Ratio** | **`+8.7074`** | $S_t = \sum \Lambda(y_t)$ |
| **Decision Boundaries** | `A = -2.2513, B = +2.8904` | Accept $H_0$ if $S_t \le A$; Accept $H_1$ if $S_t \ge B$ |
| **Breach Incident Count** | `10 / 40 periods` | Observed structural shock exceedances |

---

### 5. Institutional Compliance & Mandatory Commercial Disclaimer

### COMMERCIAL DISCLAIMER
This document and the underlying risk model outputs are generated strictly for academic, underwriting research, and quantitative risk evaluation purposes based exclusively on publicly available Open Source Intelligence (OSINT) maritime security data. This report does not constitute official nautical advice, security operational clearance, or guaranteed insurance pricing. Neither the authors nor the operators of the maritime-tail-risk-engine assume liability for maritime navigation, chartering decisions, or asset deployment in war risk or high-risk areas (HRA).

> [!IMPORTANT]
> **Civilian Open-Source Intelligence (OSINT) Certification**: This intelligence and model suite strictly utilizes 100% verified civilian open-source feeds (Copernicus ERA5, GFW Sentinel-1 SAR radar, IMF PortWatch AIS, NOAA VIIRS Nightfire) and zero restricted military or naval C2 feeds.

#### Author Identity Block
- **Author**: Nigerian Navy officer with 20+ years of operational experience
- **ORCID**: `0009-0008-0112-9273`

---
*Report generated deterministically by `maritime-tail-risk-engine`.*