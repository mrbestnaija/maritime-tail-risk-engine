"""Test Suite for Phase 3.1: Cox Proportional Hazards Voyage Pricer,
MSSA Macro-Scaled GPD & Standardized Copernicus/GFW Feed Adapters.

Validates:
1. Copernicus & GFW standardized telemetry adapter with automatic -999.0 sentinel fill-value imputation.
2. Strict monotonic decrease in Cox 7-day breach probability and AP bps as vessel Operational Hardening Index (OHI) increases.
3. Convex step-up inflection in GPD tail CVaR_0.99 when macro structural shock residual crosses above threshold (0.65).
4. Full integration with PluginRegistry and Hexagonal Architecture ports.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import numpy as np
import pytest

import maritime_risk as mtr
from maritime_risk.application.registry import (
    CopernicusGFWStandardizedAdapter,
    CoxProportionalHazardsJWCPricer,
    default_registry,
)
from maritime_risk.core.gpd_tail_fitter import (
    compute_macro_modulated_gpd_tail,
    fit_pot_gpd,
)
from maritime_risk.core.jwc_pricer import (
    compute_cox_7day_breach_probability,
    compute_operational_hardening_index,
    price_cox_7day_war_risk_ap,
)
from maritime_risk.core.models import CivilianSensorTelemetry
from maritime_risk.core.specs import (
    CorridorSpec,
    CoxHazardSpec,
    EmpiricalBayesSpec,
    GPDFitterSpec,
    HydroEnvelopeSpec,
    MacroGPDScaleSpec,
    VesselProfileSpec,
)


# =============================================================================
# Test 1: Telemetry Bounds & Sentinel Imputation via Copernicus/GFW Adapter
# =============================================================================

def test_copernicus_gfw_standardized_sentinel_imputation():
    """Verify that Copernicus/GFW adapter imputes negative sentinels to baseline values."""
    adapter = CopernicusGFWStandardizedAdapter(
        baseline_wave_height_m=1.35,
        default_sar_dark_ratio=0.18,
        default_anchorage_waiting_hours=24.0,
        default_mothership_loitering_idx=0.25,
        default_distance_pmsc_km=180.0,
    )

    # 1. Raw NetCDF-like dict with -999.0 sentinel fill-values
    raw_with_sentinels = {
        "telemetry_id": "TEL-ERA5-SENTINEL-01",
        "corridor_id": "GOG_BONNY_BRASS_FAIRWAY",
        "observation_timestamp": "2026-03-15T06:00:00Z",
        "publication_timestamp": "2026-03-15T08:00:00Z",
        "significant_wave_height_m": -999.0,  # Negative missing-data fill value!
        "sar_dark_vessel_ratio": -1.0,         # Negative sentinel!
        "anchorage_waiting_hours": -99.0,      # Negative sentinel!
        "mothership_loitering_index": -999.0,  # Negative sentinel!
        "distance_pmsc_km": -999.0,            # Negative sentinel!
    }

    adapted = adapter.adapt_record(raw_with_sentinels)

    assert isinstance(adapted, CivilianSensorTelemetry)
    assert adapted.telemetry_id == "TEL-ERA5-SENTINEL-01"
    # Negative sentinels successfully imputed to baseline defaults
    assert adapted.significant_wave_height_m == 1.35
    assert adapted.sar_dark_vessel_ratio == 0.18
    assert adapted.anchorage_waiting_hours == 24.0
    assert adapted.mothership_loitering_index == 0.25
    assert adapted.distance_pmsc_km == 180.0

    # 2. Raw record with valid physical measurements: must preserve real data
    raw_valid = {
        "telemetry_id": "TEL-ERA5-VALID-02",
        "corridor_id": "GOG_BONNY_BRASS_FAIRWAY",
        "observation_timestamp": "2026-03-15T12:00:00Z",
        "publication_timestamp": "2026-03-15T14:00:00Z",
        "significant_wave_height_m": 2.45,
        "sar_dark_vessel_ratio": 0.42,
        "anchorage_waiting_hours": 36.5,
        "mothership_loitering_index": 0.68,
        "distance_pmsc_km": 95.0,
    }

    adapted_valid = adapter.adapt_record(raw_valid)
    assert adapted_valid.significant_wave_height_m == 2.45
    assert adapted_valid.sar_dark_vessel_ratio == 0.42
    assert adapted_valid.anchorage_waiting_hours == 36.5
    assert adapted_valid.mothership_loitering_index == 0.68
    assert adapted_valid.distance_pmsc_km == 95.0

    # 3. Collection batch adaptation via adapter.adapt_records()
    records = [raw_with_sentinels, raw_valid]
    batch = adapter.adapt_records(records)
    assert len(batch) == 2
    assert batch[0].significant_wave_height_m == 1.35
    assert batch[1].significant_wave_height_m == 2.45

    # 4. Verify feed adapter is registered in default_registry
    registry_adapter = default_registry.get_feed_adapter("copernicus_gfw_standardized")
    assert registry_adapter is not None
    assert hasattr(registry_adapter, "adapt_record")
    assert callable(registry_adapter)


# =============================================================================
# Test 2: Monotonic Decrease in Cox Breach Probability with OHI
# =============================================================================

def test_cox_7day_breach_probability_monotonic_decrease_with_ohi():
    """Verify that Cox 7-day breach probability and AP bps decrease strictly as OHI increases."""
    cox_spec = CoxHazardSpec()
    corridor_spec = CorridorSpec()
    hydro_spec = HydroEnvelopeSpec()

    # Three vessel hardening profiles with strictly increasing defenses
    vessel_low = VesselProfileSpec(
        vessel_profile_id="FEEDER_LOW_HARDENING",
        insured_vessel_usd=85_000_000.0,
        daily_demurrage_usd=45_000.0,
        catastrophic_boarding_loss_usd=3_500_000.0,
        single_vessel_exposure_factor=0.25,
        freeboard_meters=2.8,
        max_sustained_speed_knots=10.5,
        pms_guards_present=False,
    )
    vessel_mid = VesselProfileSpec(
        vessel_profile_id="SUEZMAX_MID_HARDENING",
        insured_vessel_usd=85_000_000.0,
        daily_demurrage_usd=45_000.0,
        catastrophic_boarding_loss_usd=3_500_000.0,
        single_vessel_exposure_factor=0.25,
        freeboard_meters=8.2,
        max_sustained_speed_knots=16.5,
        pms_guards_present=True,
    )
    vessel_high = VesselProfileSpec(
        vessel_profile_id="VLCC_HIGH_HARDENING",
        insured_vessel_usd=85_000_000.0,
        daily_demurrage_usd=45_000.0,
        catastrophic_boarding_loss_usd=3_500_000.0,
        single_vessel_exposure_factor=0.25,
        freeboard_meters=12.5,
        max_sustained_speed_knots=21.0,
        pms_guards_present=True,
    )

    # 1. Operational Hardening Index (OHI) must be strictly increasing
    ohi_low = compute_operational_hardening_index(vessel_low, cox_spec)
    ohi_mid = compute_operational_hardening_index(vessel_mid, cox_spec)
    ohi_high = compute_operational_hardening_index(vessel_high, cox_spec)

    assert ohi_low < ohi_mid < ohi_high
    # Verify exact math: OHI = 0.40 * fb + 0.40 * speed + (2.0 if guards else 0)
    expected_ohi_low = 0.40 * 2.8 + 0.40 * 10.5 + 0.0
    expected_ohi_mid = 0.40 * 8.2 + 0.40 * 16.5 + 2.0
    expected_ohi_high = 0.40 * 12.5 + 0.40 * 21.0 + 2.0
    assert math.isclose(ohi_low, expected_ohi_low, abs_tol=1e-5)
    assert math.isclose(ohi_mid, expected_ohi_mid, abs_tol=1e-5)
    assert math.isclose(ohi_high, expected_ohi_high, abs_tol=1e-5)

    # 2. Evaluate Cox 7-day breach probability under identical corridor conditions
    mli = 0.45
    pmsc_km = 120.0
    wave_h = 1.25

    p_low, haz_low, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mli,
        distance_pmsc_km=pmsc_km,
        wave_height_m=wave_h,
        vessel_spec=vessel_low,
        cox_spec=cox_spec,
        hydro_spec=hydro_spec,
    )
    p_mid, haz_mid, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mli,
        distance_pmsc_km=pmsc_km,
        wave_height_m=wave_h,
        vessel_spec=vessel_mid,
        cox_spec=cox_spec,
        hydro_spec=hydro_spec,
    )
    p_high, haz_high, _ = compute_cox_7day_breach_probability(
        mothership_loitering_idx=mli,
        distance_pmsc_km=pmsc_km,
        wave_height_m=wave_h,
        vessel_spec=vessel_high,
        cox_spec=cox_spec,
        hydro_spec=hydro_spec,
    )

    # Strict monotonic decrease in daily hazard and cumulative breach probability
    assert haz_low > haz_mid > haz_high
    assert p_low > p_mid > p_high
    assert 0.0 < p_high < 1.0

    # 3. First-principles fair AP in bps must also decrease strictly monotonically
    cvar_99 = 6.50
    pricing_low = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=mli,
        distance_pmsc_km=pmsc_km,
        wave_height_m=wave_h,
        composite_cvar_99=cvar_99,
        vessel_spec=vessel_low,
        corridor_spec=corridor_spec,
        cox_spec=cox_spec,
        hydro_spec=hydro_spec,
    )
    pricing_mid = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=mli,
        distance_pmsc_km=pmsc_km,
        wave_height_m=wave_h,
        composite_cvar_99=cvar_99,
        vessel_spec=vessel_mid,
        corridor_spec=corridor_spec,
        cox_spec=cox_spec,
        hydro_spec=hydro_spec,
    )
    pricing_high = price_cox_7day_war_risk_ap(
        mothership_loitering_idx=mli,
        distance_pmsc_km=pmsc_km,
        wave_height_m=wave_h,
        composite_cvar_99=cvar_99,
        vessel_spec=vessel_high,
        corridor_spec=corridor_spec,
        cox_spec=cox_spec,
        hydro_spec=hydro_spec,
    )

    assert (
        pricing_low.actuarial_7d_war_risk_ap_bps
        > pricing_mid.actuarial_7d_war_risk_ap_bps
        > pricing_high.actuarial_7d_war_risk_ap_bps
    )
    assert pricing_mid.pricing_model == "cox_proportional_hazards_jwc"
    assert pricing_mid.daily_hazard_rate == haz_mid
    assert pricing_mid.operational_hardening_index == ohi_mid


# =============================================================================
# Test 3: Macro-Residual GPD Scale Modulation & Convex Step-Up Inflection
# =============================================================================

def test_macro_modulated_gpd_convex_stepup_inflection():
    """Verify macro structural shock residual exponentially modulates GPD scale, inflating CVaR_0.99."""
    # Synthetic structural shock residuals
    np.random.seed(42)
    residuals = np.random.exponential(scale=1.2, size=60) + 0.1
    baseline = 4.46
    macro_spec = MacroGPDScaleSpec(macro_residual_alpha=0.30, max_scale_multiplier=5.0)

    # 1. Unmodulated baseline GPD fit
    base_fit = fit_pot_gpd(residuals, baseline_anchor=baseline)

    # 2. Modulate with low, medium, and high macro shock residuals
    r_benign = 0.10
    r_sub_inflection = 0.40
    r_post_inflection = 0.85

    est_benign = compute_macro_modulated_gpd_tail(
        residuals=residuals,
        baseline=baseline,
        macro_risk_residual=r_benign,
        macro_spec=macro_spec,
    )
    est_sub = compute_macro_modulated_gpd_tail(
        residuals=residuals,
        baseline=baseline,
        macro_risk_residual=r_sub_inflection,
        macro_spec=macro_spec,
    )
    est_post = compute_macro_modulated_gpd_tail(
        residuals=residuals,
        baseline=baseline,
        macro_risk_residual=r_post_inflection,
        macro_spec=macro_spec,
    )

    # Scale parameter modulated strictly monotonically by macro residual
    assert est_benign.scale_sigma < est_sub.scale_sigma < est_post.scale_sigma

    # Tail CVaR_0.99 increases strictly monotonically
    assert est_benign.cvar_99 < est_sub.cvar_99 < est_post.cvar_99
    assert est_benign.composite_corridor_cvar_99 < est_sub.composite_corridor_cvar_99 < est_post.composite_corridor_cvar_99

    # Strict quantile ordering must be preserved: CVaR_99 >= VaR_99 >= VaR_95
    for est in [est_benign, est_sub, est_post]:
        assert est.cvar_99 >= est.var_99 >= est.var_95
        assert (
            est.composite_corridor_cvar_99
            >= est.composite_corridor_var_99
            >= est.composite_corridor_var_95
        )

    # Convex step-up verification: delta from 0.40 -> 0.85 is larger than 0.10 -> 0.40 (normalized)
    delta_1 = est_sub.cvar_99 - est_benign.cvar_99
    delta_2 = est_post.cvar_99 - est_sub.cvar_99
    rate_1 = delta_1 / (r_sub_inflection - r_benign)
    rate_2 = delta_2 / (r_post_inflection - r_sub_inflection)
    assert rate_2 > rate_1  # Convex slope step-up!

    # 3. Max scale multiplier capping guard
    est_extreme = compute_macro_modulated_gpd_tail(
        residuals=residuals,
        baseline=baseline,
        macro_risk_residual=50.0,  # Extreme shock
        macro_spec=macro_spec,
    )
    # Must not exceed max_scale_multiplier (5.0x) * base scale
    assert est_extreme.scale_sigma <= base_fit.scale_sigma * macro_spec.max_scale_multiplier + 1e-4


# =============================================================================
# Test 4: Registry Resolution & Pluggable Adapter Execution
# =============================================================================

def test_registry_resolution_and_cox_pricer_plugged():
    """Verify Cox pricer and standardized feed adapter can be resolved via PluginRegistry."""
    # 1. Resolve pricer via default registry
    pricer = default_registry.get_pricer("cox_proportional_hazards_jwc")
    assert pricer is not None
    assert isinstance(pricer, CoxProportionalHazardsJWCPricer)

    vessel_spec = VesselProfileSpec()
    corridor_spec = CorridorSpec()

    # 2. Call price_transit on the adapter
    result = pricer.price_transit(
        breach_prob_7d=0.08,
        composite_cvar_99=5.50,
        hydro_feasibility=0.75,
        vessel_spec=vessel_spec,
        corridor_spec=corridor_spec,
    )

    assert result.pricing_model == "cox_proportional_hazards_jwc"
    assert result.actuarial_7d_war_risk_ap_bps > 0.0
    assert result.daily_hazard_rate > 0.0
    assert result.operational_hardening_index > 0.0
