# PHASE 1 VINTAGE AUDIT: GULF OF GUINEA - LAGOS SECURE ANCHORAGE AREA (SAA)

### COMMERCIAL DISCLAIMER
This document and the underlying risk model outputs are generated strictly for academic, underwriting research, and quantitative risk evaluation purposes based exclusively on publicly available Open Source Intelligence (OSINT) maritime security data. This report does not constitute official nautical advice, security operational clearance, or guaranteed insurance pricing. Neither the authors nor the operators of the maritime-tail-risk-engine assume liability for maritime navigation, chartering decisions, or asset deployment in war risk or high-risk areas (HRA).

---

### IDENTITY & AUDIT BLOCK
- **Engine**: `maritime-tail-risk-engine` (Phase 2B First-Principles & Multi-Sensor Fusion)
- **Target Geographic Fairway**: Gulf of Guinea - Lagos Secure Anchorage Area (SAA) (`6.0°N - 6.5°N, 3.1°E - 3.6°E`)
- **Audit Timestamp**: `2026-11-01 17:58:17 UTC`
- **Architecture**: Clean Architecture / Modular Monolith (Core Domain Layer Isolation)
- **Verification Paradigm**: Python-Native Verification (Pydantic + SQLite CHECK Constraints + Hypothesis Fuzzing + Tri-State CLI)
- **Dataset SHA-256 Lineage Hash**: `fbc423bdaadaa97d7b7cc9f74f2f5991325bf094b48b41337a7d319d6ddd649f`
- **Telemetry SHA-256 Lineage Hash**: `c1f00568a88f3ec52dd74bd7b63a409ab40311fd4e325cdd95afd8687205bab8`
- **Audit Manifest**: `PHASE1_AUDIT_MANIFEST.json` (Cryptographic Lineage Verifiable)
- **Input Incident Dataset**: Ingested (12 records)
- **Input Telemetry Dataset**: Multi-Sensor Stream

---

### 1. Reporting-Lag Blind-Spot Distortion Analysis

In high-risk maritime corridors, intelligence reporting latency creates an insidious **underwriting blind spot**:
underwriters pricing risk based on published intelligence bulletins are pricing yesterday's threat level, while real-time security events remain unpublicized for days.

| Reporting Lag Metric | Observed Value | Underwriting Impact |
|---|---|---|
| **Mean Reporting Lag** | **`0.16 days`** | Average delay before an incident appears in OSINT feeds |
| **Maximum Reporting Lag** | **`0.17 days`** | Worst-case information blackout observed in vintage |
| **Multi-Day Lag Ratio ($\ge 3$ Days)** | **`0.0%`** | Proportion of incidents operating in the blind-spot window |

> [!WARNING]
> **Underwriter Blind-Spot Hazard**: During a 3 to 7 day reporting lag window, active pirate action groups (PAGs) remain undetected by published feeds. If underwriters compute rolling 14-day VaR on publication date rather than occurrence date, active fairway risk is underestimated by up to **34.8%** during surge periods.

#### Ingestion Hygiene & Deduplication Audit
- **Raw OSINT Reports Ingested**: `12`
- **Deduplicated Physical Incidents**: `11`
- **Duplicate Reduction Ratio**: `8.3%`

#### The Union Envelope Invariant in Cross-Feed Reconciliation
When multiple intelligence agencies report the same incident (e.g. MDAT-GOG, IMB, and Dryad), severity intervals often diverge due to differing assessment criteria. Underwriter solvency mandates computing the **Union Envelope** ($\min(\text{min}), \max(\text{max})$):

| Deduplicated ID | Primary Vessel | Feeds Merged | Individual Feed Severities | Union Envelope Severity | Imputed Centroid (Lat, Lon) |
|---|---|---|---|---|---|
| `DEDUP-LAG-2023-0110-MDAT` | **MV LAGOS TRADER** | IMB + MDAT-GOG | Multiple OSINT sources | **[2.0, 4.5]** | `(6.2210°N, 3.3220°E)` |
| `LAG-2023-0228-MDAT` | MT APAPA STAR | MDAT-GOG | Single Feed | `[3.0, 5.0]` | `(6.1800°N, 3.2800°E)` |
| `LAG-2023-0315-DRYAD` | MV TIN CAN VOYAGER | DRYAD | Single Feed | `[3.5, 5.5]` | `(6.2500°N, 3.3500°E)` |
| `LAG-2023-0410-UKMTO` | MV COMMODORE CHANNEL | UKMTO | Single Feed | `[2.0, 3.5]` | `(6.1500°N, 3.2500°E)` |
| `LAG-2023-0518-MDAT` | MT WESTERN GULF | MDAT-GOG | Single Feed | `[4.0, 6.0]` | `(6.3100°N, 3.4200°E)` |
| `LAG-2023-0622-IMB` | MV AFRICAN HARMONY | IMB | Single Feed | `[2.5, 4.5]` | `(6.2800°N, 3.3800°E)` |
| `LAG-2023-0805-MDAT` | MT LAGOS GLORY | MDAT-GOG | Single Feed | `[3.0, 5.0]` | `(6.2000°N, 3.3000°E)` |
| `LAG-2023-0912-DRYAD` | MV ATLANTIC HIGHWAY | DRYAD | Single Feed | `[3.5, 6.0]` | `(6.2400°N, 3.3600°E)` |
| `LAG-2023-1020-UKMTO` | MT BADAGRY BIGHT | UKMTO | Single Feed | `[2.0, 3.5]` | `(6.1600°N, 3.2600°E)` |
| `LAG-2023-1110-MDAT` | MV EKO CARRIER | MDAT-GOG | Single Feed | `[3.5, 5.5]` | `(6.2900°N, 3.4100°E)` |
| `LAG-2023-1205-IMB` | MV VICTORIA ISLAND | IMB | Single Feed | `[2.5, 4.0]` | `(6.2100°N, 3.3100°E)` |

> [!IMPORTANT]
> **Underwriter Risk Note**: Dropping secondary feeds or keeping only the first reported record causes a severe underestimation of the tail risk. The Union Envelope preserves the true upper risk boundary across all reporting intelligence feeds.

---

### 2. Multi-Sensor Civilian OSINT & Hydrodynamic Physics Fusion

The corridor risk picture is enriched using **4 verifiable public civilian satellite & meteorological sensors** alongside hydrodynamic small-skiff boarding physics (Hard Firewall: Zero military or restricted naval C2 feeds):

| Civilian Sensor Channel | Data Provider Equivalent | Physical Hazard Metric | Corridor Observed Mean [Min, Max] |
|---|---|---|---|
| **Marine MetOcean Envelope** | `COPERNICUS_ERA5_METOCEAN` | Significant Wave Height ($H_s$ in meters) | `1.06m` |
| **Spaceborne SAR Dark Ratio** | `GFW_SENTINEL1_SAR` | Radar Targets Lacking Public AIS (%) | `11.8%` |
| **Anchorage Loitering Delay** | `IMF_PORTWATCH_AIS` | Fairway Waiting / Queue Duration (hrs) | `18.5 hrs` |
| **Offshore Thermal Continuity** | `NOAA_VIIRS_FIRMS` | Terminal Gas-Flaring Continuity Index | `0.84 [0.65, 0.98]` |

#### Hydrodynamic Skiff Swamping Physics
- **Observed Mean $H_s$**: `1.06m`
- **Skiff Boarding Feasibility**: **`94.1%`** (logistic transition at $H_0 = 1.85\text{m}$)
- **Composite Dark Vessel Hazard Score**: **`1.11 / 10.0`**

> [!NOTE]
> **Physical Boarding Invariant**: In maritime security fairways, pirate skiff boardings drop to near zero when significant wave height exceeds swamping thresholds. High SAR dark vessel activity coinciding with calm sea-states creates a critical attack window.

---

### 3. MSSA Seasonal Decomposition & Avoided Escort False-Alarm OPEX Savings

Multivariate Singular Spectrum Analysis ($M = 4$ channels, window length $L = 10$) separates secular fairway drift from monsoon sea-state seasonal harmonics and isolated structural shocks:
$$\mathbf{Y}_t = \mathbf{T}_t \text{ (Secular Trend)} + \mathbf{S}_t \text{ (Seasonal Harmonics)} + \mathbf{R}_t \text{ (Structural Shock Residual)}$$

| MSSA Metric | Value | Forensic / Operational Significance |
|---|---|---|
| **Frobenius Reconstruction Error** | **`2.15e-13`** | Strict mathematical invariant ($\|\mathbf{Y} - (\mathbf{T}+\mathbf{S}+\mathbf{R})\|_F < 10^{-9}$) verified |
| **Secular + Seasonal Baseline Anchor** | **`2.93 / 10.0`** | Reconstructed fairway baseline (Channel 0 trend + seasonal harmonics) |
| **Explained Variance Ratio (EVR)** | **`0.9985`** | Proportion of total fairway variance captured by leading 3 triplets |
| **Avoided False Alarm Days** | **`0 days`** | Periods where raw threat spiked purely due to seasonal harmonics while structural shock remained benign |
| **Avoided Escort OPEX Savings** | **`$0.00 USD`** | Direct commercial savings from avoiding unnecessary private escort vessel (PMSC) charters |

> [!TIP]
> **Commercial Value Proof**: At standard security escort rates of **$18,500/day**, isolating seasonal sea-state harmonics prevents **0 false-alarm escort mobilizations**, returning **$0.00 in verified OPEX savings** across this vintage window.

---

### 4. POT-GPD Tail Risk, Empirical Bayes Regularization & First-Principles JWC Pricing

#### Table 4A: MSSA Structural Shock Residual Tail (POT-GPD with Empirical Bayes Shrinkage)
Small-sample MLE on GPD shape $\xi$ has extreme variance when exceedance counts are small. We apply **Empirical Bayes Shrinkage** against the historical prior ($\xi_0 = 0.12, \sigma_0 = 1.10, \kappa = 15.0$), preventing optimizer railing at $\xi = -0.5000$:

| Parameter | Raw Optimization Value | Shrunk Empirical Bayes Estimate | Regularization Impact |
|---|---|---|---|
| **GPD Shape Parameter ($\xi$)** | `-0.5000` | **`0.2500`** | Regularized toward prior $\xi_0=0.12$; avoids boundary railing |
| **GPD Scale Parameter ($\sigma$)** | N/A | **`2.1918`** | Regularized scale parameter |
| **Shrinkage Weight ($w$)** | N/A | **`0.4000`** | Weight assigned to local data vs prior ($N_u=10$) |
| **Residual $\text{VaR}_{0.95}$** | N/A | **`5.07`** | 95th percentile structural residual shock |
| **Residual $\text{VaR}_{0.99}$** | N/A | **`11.57`** | 99th percentile structural residual shock |
| **Residual $\text{CVaR}_{0.99}$** | N/A | **`18.10`** | Mean structural shock conditional on tail breach |

#### Table 4B: Full Composite Corridor Severity Tail (Reconstructed Baseline + GPD Shock)
To eliminate the visual scale mismatch where residual shock metrics were compared against raw empirical metrics, the composite corridor severity tail anchors the GPD structural shock to the reconstructed MSSA baseline. Unclamped composite quantiles preserve strict monotonic differentiation:

| Metric | Empirical Sample Severity | Composite Corridor GPD Severity | Quantile Invariant |
|---|---|---|---|
| **Value at Risk ($\text{VaR}_{0.95}$)** | `5.70 / 10.0` | **`8.00`** | Base threshold |
| **Value at Risk ($\text{VaR}_{0.99}$)** | `6.00 / 10.0` | **`14.49`** | $\ge \text{VaR}_{0.95}$ |
| **Expected Shortfall ($\text{CVaR}_{0.99}$)** | `6.00 / 10.0` | **`21.03`** | $\ge \text{VaR}_{0.99}$ |

> [!NOTE]
> **Open-Ended Composite Severity Scale**: Reconstructed composite metrics combine the secular+seasonal fairway baseline with the GPD extreme tail residual shock without artificial ceiling clamping, preserving strict mathematical quantile ordering: $\text{CVaR}_{0.99} > \text{VaR}_{0.99} > \text{VaR}_{0.95}$.

#### Table 4C: First-Principles Lloyd's JWC 7-Day AP & Demurrage Pricing
Replaces naive multiplier heuristics with first-principles underwriting loss expectation on a **$85,000,000 USD** hull, modeling single-voyage spatial-temporal exposure and hydrodynamic boarding physics:

| Pricing Parameter / Output | Value | Actuarial Definition |
|---|---|---|
| **Calibrated 7-Day Corridor Breach Prob** | **`25.0%`** | Probability of corridor risk exceeding baseline in 7d window |
| **Single-Vessel Transit Exposure Factor** | **`25.0%`** | Spatial-temporal exposure of single transiting vessel |
| **Hydrodynamic Boarding Modulator** | **`97.1%`** | Modulation from sea-state small-skiff boarding feasibility |
| **Effective Single-Vessel Breach Prob** | **`6.07%`** | Net single-vessel breach probability over 7-day transit |
| **Expected Tail Delay Duration** | **`8.50 days`** | Operational delay days given extreme tail breach |
| **Tail Demurrage Loss Exposure** | **`$382,500.00 USD`** | Financial demurrage loss at $45,000/day charterparty rate |
| **Catastrophic Boarding Loss Exposure** | **`$3,500,000.00 USD`** | Expected damage/ransom conditional on tail breach |
| **Expected 7-Day Tail Loss** | **`$235,527.10 USD`** | Unconditional actuarial expected loss over 7-day transit |
| **Fair Actuarial War-Risk AP** | **`27.71 bps`** | Fair additional premium rate (1 bps = 0.01% of hull value) |
| **Lloyd's JWC Market Benchmark** | **`10.00 bps`** | Standard commercial market quote for transit |
| **Underwriter Commercial Spread** | **`+17.71 bps`** | **`$+150,527.10 USD`** per transit underpricing hazard |

#### Table 4D: Wald's Sequential Probability Ratio Test (SPRT) Surveillance State
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
- **Author**: **Bestman Ezekwu Enock**
- **Role**: Quantitative Risk Architect & Maritime Tail Risk Lead
- **Designation / Background**: Nigerian Navy officer with 20+ years of operational experience
- **GitHub**: [`@mrbestnaija`](https://github.com/mrbestnaija)
- **ORCID**: `0009-0008-0112-9273`
- **LinkedIn**: [Bestman Ezekwu Enock](https://www.linkedin.com/in/bestman-ezekwu/)

---
*Report generated deterministically by `maritime-tail-risk-engine`.*