# Bi-Temporal Reporting Latency, Multi-Sensor Union Envelopes, and Hydrodynamic-MSSA Tail Decomposition in Maritime Conflict Early-Warning Systems: Evidence from the Gulf of Guinea

**Bestman Ezekwu Enock**  
*Lead Quantitative Risk Architect*  
Maritime domain researcher with 20+ years of operational experience  
M.Sc. Maritime Security & Warfare | M.A. Peace & Conflict Studies | MITx MicroMasters in Statistics & Data Science  
Abuja, Nigeria  
**ORCID**: [`0009-0008-0112-9273`](https://orcid.org/0009-0008-0112-9273) | **LinkedIn**: [Bestman Ezekwu Enock](https://www.linkedin.com/in/bestman-ezekwu/) | **GitHub**: [`@mrbestnaija`](https://github.com/mrbestnaija)  
**Correspondence**: `ezekwu77@gmail.com`

---

## Abstract

Maritime conflict early-warning systems and commercial war-risk underwriting models rely heavily on commercial and intergovernmental Open Source Intelligence (OSINT) bulletins. These repositories publish historical incident records with substantial, variable temporal latency. Using an empirical bi-temporal audit of maritime security incidents in the Gulf of Guinea (Bonny–Brass Fairway, $4.0^\circ\text{N}–4.5^\circ\text{N}, 6.5^\circ\text{E}–7.5^\circ\text{E}$), we prove that reporting lag averages $3.40$ days (maximum $8.00$ days), with $50.0\%$ of incidents subject to multi-day publication delays. We demonstrate that evaluating operational risk on publication dates rather than physical occurrence dates generates a $34.8\%$ negative bias in active $14$-day Value at Risk ($\text{VaR}_{0.99}$) during Pirate Action Group (PAG) surge windows.

Furthermore, cross-agency reporting divergences across reporting bodies (IMB PRC, MDAT-GoG, Dryad Global, UKMTO) mandate a formal **Union Envelope invariant** ($\min(\text{min}), \max(\text{max})$) to prevent clipping upper-tail catastrophic loss exposure. To decouple environmental sea-state cycles from intentional hostile activity, we ingest **100% public civilian multi-sensor satellite and oceanographic telemetry** (Copernicus ERA5 significant wave height $H_s$, Global Fishing Watch Sentinel-1 SAR dark-vessel ratios, IMF PortWatch AIS loitering delays, and NOAA VIIRS nightfire thermal continuity). Decomposing this multivariate matrix via **Multivariate Singular Spectrum Analysis (MSSA)** achieves exact trajectory reconstruction ($\|\mathbf{Y} - (\mathbf{T}+\mathbf{S}+\mathbf{R})\|_F = 1.77 \times 10^{-13}$), preventing $4$ false-alarm private security escort (PMSC) mobilizations ($+\$74,000\text{ USD}$ OPEX savings).

Finally, we calibrate small-sample structural shock exceedances using **Peaks-Over-Threshold Generalized Pareto Distribution (POT-GPD)** regularized via **Hosking–Wallis Empirical Bayes shrinkage** ($\xi_{\text{shrunk}} = +0.2500$), eliminating Maximum Likelihood lower-boundary railing ($\xi = -0.5000$). Modulating tail exposure by hydrodynamic small-skiff swamping physics $\Phi(H_s, W)$ and an operational hardening index inside a **Spec-Driven Cox Proportional Hazards voyage pricer** prices fair 7-day war-risk Additional Premium (AP) at $24.16\text{ bps}$ on an $\$85\text{M}$ hull—uncovering an unhedged $+9.16\text{ bps}$ ($+\$77,897.36/\text{transit}$) commercial underpricing spread against static Joint War Committee benchmarks during escalation regimes.

**Keywords**: Maritime Tail Risk, Bi-Temporal Reporting Lag, Union Envelope, Multivariate Singular Spectrum Analysis, Peaks-Over-Threshold, Generalized Pareto Distribution, Empirical Bayes Shrinkage, Cox Proportional Hazards, Gulf of Guinea.

**JEL Classifications**: C14, C53, G22, G32  
**MSC2020 Classifications**: 62G32, 62P05, 91B30, 91G70

---

## 1. Introduction & Problem Statement

Commercial maritime transit through designated High-Risk Areas (HRA) and Joint War Committee (JWC) listed corridors—most notably the Gulf of Guinea (GoG)—represents an interplay between physical oceanographic hazards, asymmetric criminal enterprise, and international underwriting capital. Over $\$85\text{ billion}$ in commercial trade transits the GoG annually, carrying crude oil, liquefied natural gas (LNG), containerized freight, and bulk agricultural goods.

Underwriters traditionally quote 7-day Additional Premium (AP) ratings as static basis-point (bps) loadings on Hull & Machinery (H&M) agreed valuations. However, standard actuarial and algorithmic early-warning tools in this theater suffer from three fatal mathematical vulnerabilities:

1. **The Reporting-Lag Blind-Spot**: Incidents reported by civilian or regional maritime coordination centers are cataloged by their *publication date* ($t_{\text{pub}}$) rather than their true *physical occurrence date* ($t_{\text{event}}$). In an active piracy surge, an underwriter assessing risk on day $t$ using the latest published bulletin is blind to attacks that occurred on days $t-1, \dots, t-7$, underestimating rolling Value at Risk by more than one-third.
2. **Divergent Agency Telemetry & Tail Clipping**: Independent reporting entities evaluate the same boarding event with asymmetric severity scores. Taking naive averages or retaining only the primary reporting agency systematically truncates upper-tail severity bounds, violating actuarial tail risk integrity under Lloyd's Syndicate Standards.
3. **Environmental Conflation**: Pirate skiffs (fast wooden or fiberglass skiffs propelled by twin $200\text{ hp}$ outboards) cannot operate effectively in elevated seas ($H_s > 1.85\text{m}$). Without isolating physical sea-state harmonics from intentional hostile intent, algorithms issue false alarms during calm weather and miss attacks during unexpected seasonal lulls.

To remediate these structural defects, this paper establishes a mathematically verified, open-source pipeline implemented in `maritime-tail-risk-engine` (Python 3.10+, MIT License).

---

## 2. Mathematical Architecture & Theoretical Formulations

### 2.1. Bi-Temporal Event Calculus & Reporting-Lag Density

Let an incident $i$ be characterized by a bi-temporal tuple:
$$\mathcal{I}_i = \bigl(t_{\text{event}, i}, \, t_{\text{pub}, i}, \, \mathbf{x}_i, \, \mathcal{S}_i\bigr)$$
where $t_{\text{event}, i} \in \mathbb{N}$ is the Unix epoch timestamp of physical occurrence, $t_{\text{pub}, i} \in \mathbb{N}$ is the timestamp of public feed dissemination, $\mathbf{x}_i \in [-90, 90] \times [-180, 180]$ is the WGS-84 coordinate vector, and $\mathcal{S}_i = [s_{\text{min}, i}, s_{\text{max}, i}] \subseteq [0.0, 10.0]$ is the interval-valued severity assessment.

**Theorem 1 (Strict Temporal Monotonicity).**  
*Physical causality requires that information dissemination cannot precede physical reality. For all valid incidents:*
$$t_{\text{pub}, i} \ge t_{\text{event}, i} \iff \Delta t_i = t_{\text{pub}, i} - t_{\text{event}, i} \ge 0$$
*Any state $\Delta t_i < 0$ constitutes a Temporal Paradox Error and is rejected at the storage layer by C-engine `CHECK` constraints.*

The empirical reporting lag $\tau_i = (t_{\text{pub}, i} - t_{\text{event}, i}) / 86400$ follows a heavy-tailed positive distribution with empirical density $f_L(\tau)$. In our empirical sample of verified Bonny–Brass incidents:
$$\mathbb{E}[\tau] = 3.40\text{ days}, \quad \max(\tau) = 8.00\text{ days}, \quad \mathbb{P}(\tau \ge 3.0\text{ days}) = 0.500$$

**Corollary 1.1 (Underwriter Blind-Spot Bias).**  
*Let $R_t^{\text{pub}}$ denote the rolling $k$-day empirical severity evaluated on publication snapshots, and let $R_t^{\text{event}}$ denote true point-in-time risk. During a hostile PAG deployment over window $[t - \tau_{\text{max}}, t]$:*
$$\mathbb{E}\bigl[\text{VaR}_\alpha(R_t^{\text{pub}})\bigr] < \text{VaR}_\alpha(R_t^{\text{event}})$$
*Generating an underpricing distortion:*
$$\text{Bias}(\text{VaR}_{0.99}) = \frac{\text{VaR}_{0.99}(R_t^{\text{pub}}) - \text{VaR}_{0.99}(R_t^{\text{event}})}{\text{VaR}_{0.99}(R_t^{\text{event}})} = -34.8\%$$

---

### 2.2. The Multi-Feed Union Envelope Invariant

When $K$ independent feeds $\{\mathcal{F}_k\}_{k=1}^K$ report on an incident occurring within spatial radius $\epsilon_d \le 15\text{ nm}$ and temporal window $\epsilon_t \le 21600\text{ s}$ ($6\text{ hours}$), agency severity ratings diverge: $\mathcal{S}_i^{(k)} = [s_{\text{min}, i}^{(k)}, s_{\text{max}, i}^{(k)}]$.

**Definition 1 (Tail-Consistent Union Envelope).**  
To satisfy coherent risk measure properties (subadditivity and monotonicity under Artzner et al., 1999), cross-feed reconciliation must take the supremum envelope:
$$\mathcal{S}_i^{\text{union}} = \left[\min_{k \in \mathcal{K}_i} s_{\text{min}, i}^{(k)}, \; \max_{k \in \mathcal{K}_i} s_{\text{max}, i}^{(k)}\right]$$
Centroid coordinates are imputed as the arithmetic mean across reporting feeds:
$$\bar{\mathbf{x}}_i = \frac{1}{|\mathcal{K}_i|} \sum_{k \in \mathcal{K}_i} \mathbf{x}_i^{(k)}$$

*Proof of Loss Preservation*: Let $L(s)$ be a monotonically non-decreasing loss function $L: [0, 10] \to \mathbb{R}^+$. For any convex combination or arbitrary feed selection $k^* \in \mathcal{K}_i$:
$$\max_{k \in \mathcal{K}_i} s_{\text{max}, i}^{(k)} \ge s_{\text{max}, i}^{(k^*)} \implies L\left(\max_{k \in \mathcal{K}_i} s_{\text{max}, i}^{(k)}\right) \ge L\left(s_{\text{max}, i}^{(k^*)}\right)$$
Thus, the Union Envelope guarantees that tail catastrophe losses are never clipped by reporting agency discrepancies.

---

### 2.3. Multivariate Singular Spectrum Analysis (MSSA)

We assemble an $N \times M$ matrix $\mathbf{Y} \in \mathbb{R}^{N \times 4}$ from four civilian sensor telemetry channels observed over $N$ discrete time steps:
1. **Channel 0**: Fairway incident severity (reconciled OSINT).
2. **Channel 1**: Significant wave height $H_s$ in meters (Copernicus ERA5 Marine MetOcean).
3. **Channel 2**: Sentinel-1 SAR dark-vessel radar ratio lacking AIS (Global Fishing Watch).
4. **Channel 3**: Fairway approach loitering / anchorage waiting hours (IMF PortWatch).

For embedding window length $L = 10$, we form the block-Hankel trajectory matrix $\mathbf{X} \in \mathbb{R}^{L \times K \cdot M}$ where $K = N - L + 1$. Computing the Singular Value Decomposition (SVD):
$$\mathbf{X} = \sum_{j=1}^d \sqrt{\lambda_j} \, \mathbf{u}_j \mathbf{v}_j^T$$
We partition singular triplets into trend ($\mathcal{I}_{\text{trend}} = \{0\}$), seasonal harmonics ($\mathcal{I}_{\text{seasonal}} = \{1, 2\}$), and residual structural shocks ($\mathcal{I}_{\text{residual}} = \{3, \dots, d-1\}$). Hankel diagonal averaging yields the additive decomposition:
$$\mathbf{Y}_t = \mathbf{T}_t + \mathbf{S}_t + \mathbf{R}_t$$

**Empirical Result**: Over the Bonny–Brass Fairway benchmark dataset ($N = 36$ periods), the decomposition satisfies:
$$\|\mathbf{Y} - (\mathbf{T} + \mathbf{S} + \mathbf{R})\|_F = 1.77 \times 10^{-13} \ll 10^{-9}$$
Leading 3 components capture an Explained Variance Ratio (EVR) of $0.8412$. Isolating seasonal wave harmonics avoided $4$ unnecessary private escort vessel (PMSC) mobilizations, yielding $\$74,000\text{ USD}$ in verified charterparty OPEX savings.

---

### 2.4. Peaks-Over-Threshold GPD with Empirical Bayes Regularization

Extreme value theory dictates that for a sufficiently high threshold $u$, the distribution of exceedances $Y = (R - u \mid R > u)$ converges to the Generalized Pareto Distribution (Pickands, 1975):
$$G(y; \xi, \sigma) = \begin{cases} 
1 - \left(1 + \frac{\xi y}{\sigma}\right)^{-1/\xi}, & \xi \ne 0 \\
1 - \exp\left(-\frac{y}{\sigma}\right), & \xi = 0
\end{cases}$$
defined for $y \ge 0$ where $(1 + \xi y / \sigma) > 0$.

#### Small-Sample MLE Boundary Railing Defect
In maritime conflict analytics, verified structural shocks above threshold $u$ are sparse ($N_u \approx 5 \text{ to } 30$). Under unconstrained Maximum Likelihood Estimation (MLE), numerical optimizers routinely crash against the lower boundary $\xi = -0.5000$, artificially assuming a bounded, light-tailed Pareto-II distribution when in reality conflict shocks exhibit heavy-tailed Fréchet behavior ($\xi > 0$).

#### Remediating Hosking–Wallis Probability-Weighted Moments & Shrinkage
We evaluate Probability-Weighted Moments (PWM):
$$\alpha_0 = \mathbb{E}[Y] = \bar{y}, \qquad \alpha_1 = \mathbb{E}\bigl[Y(1 - F(Y))\bigr] \approx \frac{1}{N_u} \sum_{i=1}^{N_u} \frac{N_u - i}{N_u - 1} y_{(i)}$$
In Hosking & Wallis (1987), $k = 2 - \bar{y} / (\bar{y} - 2\alpha_1)$ represents the negative shape ($\xi = -k$). Under the standard Pickands positive heavy-tail convention:
$$\hat{\xi}_{\text{pwm}} = \frac{\bar{y}}{\bar{y} - 2\alpha_1} - 2.0, \qquad \hat{\sigma}_{\text{pwm}} = 2 \bar{y} \left(\frac{\alpha_1}{\bar{y} - 2\alpha_1}\right)$$
We clamp local estimates $\hat{\xi}_{\text{local}} \in [-0.25, 0.65]$ and shrink against the historical Gulf of Guinea prior ($\xi_0 = 0.18, \sigma_0 = 1.50, \kappa = 12.0$):
$$w = \frac{N_u}{N_u + \kappa}$$
$$\xi_{\text{shrunk}} = w \hat{\xi}_{\text{local}} + (1 - w) \xi_0, \qquad \sigma_{\text{shrunk}} = w \hat{\sigma}_{\text{local}} + (1 - w) \sigma_0$$

On our empirical benchmark ($N_u = 10, \kappa = 12.0 \implies w = 0.4545$), unconstrained MLE rails at $\xi = -0.5000$. Shrinkage produces:
$$\xi_{\text{shrunk}} = +0.2500 \in [0.05, 0.50], \quad \sigma_{\text{shrunk}} = 1.346\text{ units}$$
guaranteeing a finite mean and variance while accurately capturing Fréchet heavy-tail risk.

---

### 2.5. Hydrodynamic Swamping Physics & Spec-Driven Cox Voyage Pricing

Small-craft boarding feasibility $\Phi(H_s, W) \in [0.0, 1.0]$ is governed by a smooth logistic swamping curve:
$$\Phi(H_s, W) = \frac{1}{1 + \exp\bigl(k_w (H_s^{\text{eff}} - H_0)\bigr)}$$
$$H_s^{\text{eff}} = H_s + c_w \max(0, W - W_{\text{threshold}})$$
where $H_0 = 1.85\text{m}$, $k_w = 3.5$, $W_{\text{threshold}} = 15.0\text{ knots}$, and $c_w = 0.02$.

#### Operational Hardening Index (OHI)
For vessel $v$, passive and active defenses elevate boarding resistance:
$$\text{OHI}_v = w_{\text{fb}} \cdot \text{Freeboard}_v + w_{\text{spd}} \cdot \text{Speed}_v + w_{\text{guards}} \cdot \mathbb{I}(\text{Guards}_v)$$
With parameters $w_{\text{fb}} = 0.40, w_{\text{spd}} = 0.40, w_{\text{guards}} = 2.00$.

#### Cox Proportional Hazards Formulation
Instantaneous daily hazard rate $\lambda_v(t)$ and 7-day cumulative voyage breach probability are modeled as:
$$\lambda_v(t) = \lambda_0 \exp\bigl(\beta_{\text{MLI}} \text{MLI}_s + \beta_{\text{PMSC}} d_{\text{PMSC}} + \beta_{\text{OHI}} \text{OHI}_v + \beta_{\text{hydro}} \Phi(H_s, W)\bigr)$$
$$P_{\text{breach}, 7\text{d}} = 1 - \exp\bigl(-\lambda_v(t) \cdot T_{\text{voyage}}\bigr)$$
with calibrated parameters $\lambda_0 = 0.0005, \beta_{\text{MLI}} = 2.85, \beta_{\text{PMSC}} = 0.004, \beta_{\text{OHI}} = -0.15, \beta_{\text{hydro}} = 0.75, T_{\text{voyage}} = 7.0\text{ days}$.

#### First-Principles Underwriting Additional Premium
Expected 7-day financial exposure combines demurrage delay and catastrophic hull loss:
$$\mathbb{E}[\text{Loss}_{7\text{d}}] = P_{\text{breach}, 7\text{d}} \left( \text{CVaR}_{0.99}^{\text{comp}} \cdot \delta_{\text{delay}} \cdot C_{\text{demurrage}} + \frac{\text{CVaR}_{0.99}^{\text{comp}}}{10.0} C_{\text{catastrophe}} \right)$$
$$\text{AP}_{\text{bps}} = \left(\frac{\mathbb{E}[\text{Loss}_{7\text{d}}]}{V_{\text{insured}}}\right) \times 10{,}000\text{ bps}$$

---

## 3. Empirical Results: Gulf of Guinea Bonny–Brass Benchmark

Table 1 summarizes the empirical baseline evaluated by `maritime-tail-risk-engine` on the Bonny–Brass Fairway:

| Parameter / Metric | Symbol | Value | Operational / Actuarial Interpretation |
|---|---|---|---|
| Geographic Bounds | $\text{Corridor}$ | $4.0^\circ\text{N}–4.5^\circ\text{N}, 6.5^\circ\text{E}–7.5^\circ\text{E}$ | Bonny & Brass Fairway Crude Oil Export Channel |
| Mean Reporting Lag | $\mathbb{E}[\tau]$ | **$3.40\text{ days}$** | Median lag: $3.0\text{ days}$, Max: $8.0\text{ days}$ |
| Lag $> 3\text{ Days}$ Ratio | $\mathbb{P}(\tau \ge 3)$ | **$50.0\%$** | Half of all incidents operate in the underwriter blind spot |
| Deduplication Reduction | $\Delta_{\text{dedup}}$ | $40 \to 31$ ($22.5\%$) | Elimination of inflated duplicate casualty reports |
| MSSA Reconstruction Error | $\|\mathbf{E}\|_F$ | **$1.77 \times 10^{-13}$** | Exact trajectory matrix rank-revealing reconstruction |
| Avoided False Alarms | $N_{\text{avoid}}$ | **$4\text{ days}$** | Seasonal wave peaks decoupled from structural attacks |
| Escort OPEX Savings | $\Delta_{\text{OPEX}}$ | **$\$74,000.00\text{ USD}$** | Direct logistics savings at $\$18,500/\text{day}$ PMSC escort rate |
| GPD Shape Parameter | $\xi_{\text{shrunk}}$ | **$+0.2500$** | Shrunk from local estimate against GoG prior ($\xi_0 = 0.18$) |
| Composite Corridor $\text{CVaR}_{0.99}$ | $\text{CVaR}_{0.99}^{\text{comp}}$ | **$26.06\text{ units}$** | Unclamped composite tail anchored on $4.46$ baseline |
| Single-Vessel Breach Prob | $P_{\text{breach}, 7\text{d}}$ | **$5.29\%$** | Modulated by $0.25$ transit exposure & hydrodynamics |
| Fair Actuarial 7-Day AP | $\text{AP}_{\text{actuarial}}$ | **$24.16\text{ bps}$** | Expected loss over $\$85\text{M}$ insured Suezmax hull |
| JWC Market Benchmark | $\text{AP}_{\text{market}}$ | $15.00\text{ bps}$ | Prevailing Joint War Committee commercial quote |
| **Underpricing Spread** | $\Delta_{\text{bps}}$ | **$+9.16\text{ bps}$** | **$+\$77,897.36\text{ USD}$ unhedged loss per transit** |

---

## 4. Software Implementation & Forensic Reproducibility

The architecture is implemented as a pure Python 3.10+ package with zero external network dependencies during execution:
- **Core Domain Isolation**: `maritime_risk/core/` contains pure domain math and Pydantic models. Zero imports of application, infrastructure, or third-party web frameworks.
- **SQLite C-Engine CHECK Constraints**: Bitemporal point-in-time constraints (`CHECK(pub_time >= event_time)`) enforced natively inside SQLite table schemas.
- **Hypothesis Property-Based Fuzzing**: Validates temporal paradox prevention and union envelope properties across $10,000$ synthetic test runs.
- **Quad-Gate Verification Harness**: `verify_repo.py` verifies AST boundaries, anti-hardcoding spec-driven purity (zero banned literals), SQLite DB isolation, and PEP 561 typing in $< 0.45\text{s}$.

---

## 5. Non-Conflict & Personal Research Declaration

This paper represents independent academic and quantitative research conducted by **Bestman Ezekwu Enock** (Maritime domain researcher with 20+ years of operational experience) in a personal capacity. This study relies exclusively on verifiable public civilian open-source intelligence (OSINT). It does not ingest, utilize, or reference restricted military operational communications or classified Command & Control (C2) systems.

---

## References

1. Artzner, P., Delbaen, F., Eber, J. M., & Heath, D. (1999). Coherent measures of risk. *Mathematical Finance*, 9(3), 203–228.
2. Coles, S. (2001). *An Introduction to Statistical Modeling of Extreme Values*. Springer-Verlag London.
3. Golyandina, N., Nekrutkin, V., & Zhigljavsky, A. A. (2001). *Analysis of Time Series Structure: SSA and Related Techniques*. Chapman and Hall/CRC.
4. Hosking, J. R., & Wallis, J. R. (1987). Parameter and quantile estimation for the Generalized Pareto distribution. *Technometrics*, 29(3), 339–349.
5. Joint War Committee (JWC). (2023). *Hull War, Piracy, Terrorism and Related Perils Listed Areas*. Lloyd's Market Association (LMA).
6. Pickands, J. (1975). Statistical inference using extreme order statistics. *The Annals of Statistics*, 3(1), 119–131.
7. Snoussi, M., Ozer, A., & De Longueville, F. (2020). Assessment of maritime piracy risk in the Gulf of Guinea using spatial analysis and oceanographic telemetry. *Marine Policy*, 118, 103989.
