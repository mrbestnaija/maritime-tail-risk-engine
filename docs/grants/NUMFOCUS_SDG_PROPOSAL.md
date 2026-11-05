# Grant Application: NumFOCUS Small Development Grant (SDG)

**Organization**: NumFOCUS  
**Program**: Small Development Grants (SDG)  
**Project Title**: *Packaging `maritime_risk`: Production-Grade Scientific Python Packaging, Property Fuzzing & Open Documentation*  
**Requested Amount**: **$10,000 USD**  
**Principal Investigator**: **Bestman Ezekwu Enock** (Maritime domain researcher with 20+ years of operational experience)  
**ORCID**: [`0009-0008-0112-9273`](https://orcid.org/0009-0008-0112-9273) | **GitHub**: [`@mrbestnaija`](https://github.com/mrbestnaija)  
**Target Package**: [`maritime-tail-risk-engine` (`maritime_risk`)](https://github.com/mrbestnaija/maritime-tail-risk-engine)  
**Upstream Scientific Ecosystem**: NumPy, SciPy, Pydantic, Hypothesis, pytest

---

## 1. Project Overview & Scientific Relevance

`maritime_risk` is an open-source, modular Python SDK designed for extreme value tail modeling (Peaks-Over-Threshold Generalized Pareto Distribution regularized via Hosking–Wallis Empirical Bayes shrinkage), signal decomposition (Multivariate Singular Spectrum Analysis), and bi-temporal reporting-lag analysis.

While the mathematical core is fully validated with 56 passing unit tests and an AST-based Quad-Gate verification CLI, transitioning this domain codebase into an established component of the global scientific Python ecosystem requires dedicated developer infrastructure:
1. **Packaging & PyPI Wheel Pipelines**: Automated multi-architecture binary wheel builds via GitHub Actions.
2. **Property-Based Fuzzing**: Expanding Hypothesis fuzz testing across extreme numerical boundaries (e.g. zero-variance exceedances, shape cap limits, infinite-mean guards).
3. **Interactive Documentation**: Building Sphinx / ReadTheDocs documentation with executable Jupyter tutorials for quantitative researchers.

---

## 2. Proposed Work & Milestones

### Milestone 1: Automated Multi-Platform Wheel Distribution & CI/CD Hardening ($3,500 USD)
- Set up automated `cibuildwheel` workflows on GitHub Actions for Linux, macOS, and Windows.
- Automate trusted publishing to PyPI on tagged releases.
- Implement automated linting, AST boundary checking, and type verification (MyPy / PEP 561 compliance) in CI.

### Milestone 2: Hypothesis Fuzz Testing & Mathematical Numerical Stability ($3,500 USD)
- Expand property-based fuzz tests to verify:
  - Exact analytical exponential limits as $|\xi| \to 0$ ($< 10^{-6}$).
  - Strict shape cap enforcement ($\xi \le 0.95$) preventing infinite-mean divergence.
  - Frobenius error bounds for MSSA Hankel matrix reconstruction across non-stationary time series.
- Benchmark performance against pure SciPy/NumPy baselines.

### Milestone 3: Interactive ReadTheDocs Documentation & Tutorials ($3,000 USD)
- Deploy official Sphinx documentation on ReadTheDocs (`maritime-risk.readthedocs.io`).
- Author two interactive Jupyter tutorial notebooks:
  - *Notebook 1*: Ingesting raw Copernicus ERA5 NetCDF & GFW SAR data into `CivilianSensorTelemetry`.
  - *Notebook 2*: Fitting Empirical Bayes POT-GPD tails and pricing 7-day spot transits via the Cox Proportional Hazards pricer.

---

## 3. Financial Budget Breakdown

| Item | Cost | Description |
|---|---|---|
| Maintainer Time (Packaging & CI) | $3,500 | 70 hours @ $50/hr for wheel pipelines and CI hardening |
| Maintainer Time (Hypothesis Fuzzing) | $3,500 | 70 hours @ $50/hr for property-based test suites |
| Documentation Authoring & Tutorials | $3,000 | 60 hours @ $50/hr for Sphinx docs & interactive notebooks |
| **Total Requested** | **$10,000 USD** | |

---

## 4. Community Benefit & Licensing

- 100% MIT Licensed.
- Code contributions adhere strictly to Python packaging standards (PEP 517, PEP 518, PEP 561, PEP 621).
- All tools and documentation remain freely accessible to the global scientific research community.
