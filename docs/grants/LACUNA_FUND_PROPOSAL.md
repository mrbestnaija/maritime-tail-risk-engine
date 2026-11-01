# Grant Application: Lacuna Fund (Geospatial & Environmental Telemetry)

**Fund**: Lacuna Fund (Geospatial / Climate / Environment in Sub-Saharan Africa)  
**Project Title**: *Gulf of Guinea Maritime Domain Commons: Open, Bias-Corrected MetOcean & Satellite Telemetry Benchmarks for Commercial Risk Equity*  
**Requested Funding**: **$30,000 USD**  
**Principal Investigator**: **Bestman Ezekwu Enock** (Nigerian Navy officer with 20+ years of operational experience)  
**Location**: Abuja, Nigeria  
**ORCID**: [`0009-0008-0112-9273`](https://orcid.org/0009-0008-0112-9273) | **GitHub**: [`@mrbestnaija`](https://github.com/mrbestnaija)  
**Target Repository**: [`https://github.com/mrbestnaija/maritime-tail-risk-engine`](https://github.com/mrbestnaija/maritime-tail-risk-engine)  
**License**: Creative Commons Attribution 4.0 International (CC-BY 4.0) for datasets / MIT for software

---

## 1. Context & The Data Gap in Sub-Saharan Africa

The Gulf of Guinea is one of the world's most critical maritime corridors, handling vital energy and food transit for West and Central Africa. However, maritime risk assessments in this region suffer from severe geospatial and temporal data biases:
1. **Reporting-Lag Asymmetry**: Intergovernmental and commercial piracy bulletins experience a mean publication lag of $3.40$ days, with $50\%$ of incidents delayed by $\ge 3$ days. Risk assessments based on delayed feeds underestimate surge Value at Risk by up to $34.8\%$.
2. **Missing Environmental Context**: Small pirate craft cannot navigate when significant wave height exceeds $1.85\text{m}$. Existing datasets fail to integrate local oceanographic sea-state data with incident reporting, leading to false-alarm security escort mobilizations and inflated risk premiums.
3. **Data Inequity**: African port authorities, shipowners, and local researchers lack access to transparent, bias-corrected benchmarks, forcing them to accept inflated foreign underwriter risk ratings without auditability.

---

## 2. Project Objectives

1. **Build a Standardized, Bias-Corrected Benchmark Dataset**: Compile a multi-year, bi-temporal dataset of maritime incidents and civilian satellite/metocean observations across three key corridors:
   - Bonny–Brass Fairway (`4.0°N–4.5°N, 6.5°E–7.5°E`)
   - Escravos–Forcados Approach (`5.2°N–5.8°N, 4.8°E–5.5°E`)
   - Lagos SAA Anchorage (`6.1°N–6.5°N, 3.1°E–3.6°E`)
2. **Multi-Sensor Fusion**: Harmonize four public civilian telemetry sources:
   - Copernicus ERA5 Marine MetOcean (significant wave height, surface wind).
   - Global Fishing Watch / ESA Sentinel-1 SAR radar dark-vessel detections.
   - IMF PortWatch / UN Global Platform AIS fairway loitering queues.
   - NOAA VIIRS Nightfire offshore infrastructure thermal continuity index.
3. **Open Access Dissemination**: Publish complete datasets on Zenodo with persistent DOIs, cryptographic SHA-256 lineage hashes, and interactive visualization notebooks.

---

## 3. Work Plan, Milestones & Budget

### Milestone 1: Data Ingestion, Reconciliation & Bi-Temporal Timestamping ($10,000 USD)
- Ingest and deduplicate 5+ years of verified incidents across MDAT-GoG, IMB PRC, and Dryad Global.
- Apply the Union Envelope ($\min(\text{min}), \max(\text{max})$) to resolve divergent agency severity ratings.
- Verify strict bi-temporal timestamps ($t_{\text{pub}} \ge t_{\text{event}}$) with coordinate centroid imputation.

### Milestone 2: Multi-Sensor Satellite & Oceanographic Coupling ($12,000 USD)
- Extract and align hourly Copernicus ERA5 wave envelopes and Sentinel-1 SAR radar dark-vessel metrics for each corridor.
- Apply Multivariate Singular Spectrum Analysis (MSSA) to separate monsoon sea-state cycles from structural hostile innovations.
- Compute hydrodynamic small-skiff swamping feasibility curves.

### Milestone 3: Zenodo Publication, FAIR Compliance & Educational Workshops ($8,000 USD)
- Package datasets according to FAIR (Findable, Accessible, Interoperable, Reusable) data principles with open CC-BY 4.0 licensing.
- Publish on Zenodo with persistent DOIs and verifiable SHA-256 lineage digests.
- Host an open virtual technical workshop for West African maritime researchers and port management authorities.

---

## 4. Sustainability & Ethical Compliance

- **Civilian Open-Source Invariant**: 100% public civilian satellite and meteorological telemetry. No classified, military, or private surveillance feeds.
- **Personal Capacity**: Independent academic initiative by Bestman Ezekwu Enock, completely separate from official service duties.
