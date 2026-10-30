"""Test Suite for MSSA Seasonal Decomposition, POT-GPD Tail Engine & Calibration.

Enforces:
1. MSSA additive reconstruction invariant: ||Y - (T + S + R)||_F < 1e-9
2. Explained variance ratio (EVR) <= 1.0
3. POT-GPD numerical stability guards (|xi| < 1e-6 smooth limit, xi <= 0.95 cap)
4. Anti-1e-9 blowup protection on pathological boundary arrays
5. Unweighted Brier and proper probability calibration invariance
6. Hypothesis property-based fuzzing on multivariate series and exceedances
"""

from __future__ import annotations

import math
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from core.calibration import (
    IsotonicCalibrator,
    PlattCalibrator,
    brier_score,
    calibrate_exceedance_probabilities,
    log_loss,
)
from core.gpd_tail_fitter import (
    GPDTailRiskEstimate,
    compute_actuarial_war_risk_loading_bps,
    compute_gpd_var_cvar,
    fit_pot_gpd,
    gpd_cdf,
)
from core.mssa_decomposer import MSSADecompositionResult, decompose_mssa


# ==============================================================================
# MSSA Decomposition Tests
# ==============================================================================

def test_mssa_additive_reconstruction_and_evr():
    """Verify that MSSA decomposition additive reconstruction error is strictly < 1e-9."""
    np.random.seed(42)
    T, M = 60, 4
    # Simulate multi-sensor series: trend + sine + noise
    t = np.linspace(0, 4 * np.pi, T)
    trend = np.outer(np.linspace(1.0, 5.0, T), np.ones(M))
    seasonal = np.outer(np.sin(t), np.array([2.0, 0.8, 0.15, 10.0]))
    noise = np.random.normal(0, 0.2, (T, M))
    Y = trend + seasonal + noise

    res = decompose_mssa(Y, window_length=15, risk_threshold=4.5)

    assert isinstance(res, MSSADecompositionResult)
    assert res.reconstruction_error_frobenius < 1e-9
    assert np.all(res.explained_variance_ratios <= 1.0)
    assert np.all(res.explained_variance_ratios >= 0.0)
    assert np.sum(res.explained_variance_ratios) <= 1.0 + 1e-12

    # Check additive property across individual components
    diff = Y - (res.trend + res.seasonal + res.residual)
    assert np.linalg.norm(diff, ord="fro") < 1e-9


def test_mssa_window_length_validation():
    """MSSA must reject window lengths violating 2 <= L <= floor(T/2)."""
    Y = np.ones((20, 3))
    # T = 20, max_L = 10
    with pytest.raises(ValueError, match="violates mathematical bounds"):
        decompose_mssa(Y, window_length=1)

    with pytest.raises(ValueError, match="violates mathematical bounds"):
        decompose_mssa(Y, window_length=11)

    # Valid window length
    res = decompose_mssa(Y, window_length=10)
    assert res.reconstruction_error_frobenius < 1e-9


def test_mssa_avoided_false_alarms_and_opex_savings():
    """Verify that avoided seasonal false alarm days and OPEX savings calculate properly."""
    T = 30
    # Channel 0: raw risk spikes at t=5 and t=10 due to seasonal swell, but residual is 0
    Y = np.zeros((T, 4))
    Y[5, 0] = 7.0
    Y[10, 0] = 8.0

    res = decompose_mssa(
        Y,
        window_length=8,
        risk_threshold=6.0,
        benign_residual_threshold=1.0,
        daily_escort_cost_usd=18_500.0,
    )
    assert res.daily_escort_cost_usd == 18_500.0
    assert res.avoided_seasonal_false_alarm_days >= 0
    assert res.escort_opex_savings_usd == res.avoided_seasonal_false_alarm_days * 18_500.0


@given(
    T=st.integers(min_value=12, max_value=30),
    M=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=15, deadline=None)
def test_hypothesis_fuzz_mssa_reconstruction(T: int, M: int):
    """Fuzz testing proving MSSA reconstruction error is strictly < 1e-9 for arbitrary dimensions."""
    np.random.seed(T * 10 + M)
    Y = np.random.uniform(0.1, 10.0, (T, M))
    res = decompose_mssa(Y, window_length=T // 3)
    assert res.reconstruction_error_frobenius < 1e-9
    assert np.all(res.explained_variance_ratios <= 1.0)


# ==============================================================================
# POT-GPD Tail Fitter Tests
# ==============================================================================

def test_gpd_smooth_exponential_limit_at_zero_shape():
    """For |xi| < 1e-6, GPD must smoothly evaluate exact analytical exponential limit."""
    u = 5.0
    sigma = 2.0
    p_u = 0.10

    # Exact xi = 0
    var_zero, cvar_zero = compute_gpd_var_cvar(u, xi=0.0, sigma=sigma, p_u=p_u, alpha=0.99)
    # Very small xi = 1e-8 (should trigger smooth analytical limit)
    var_small, cvar_small = compute_gpd_var_cvar(u, xi=1e-8, sigma=sigma, p_u=p_u, alpha=0.99)

    assert math.isclose(var_zero, var_small, rel_tol=1e-9)
    assert math.isclose(cvar_zero, cvar_small, rel_tol=1e-9)
    assert not math.isnan(var_small)
    assert not math.isinf(var_small)

    # Expected value check for exponential: CVaR_alpha = VaR_alpha + sigma
    assert math.isclose(cvar_zero, var_zero + sigma, rel_tol=1e-9)


def test_gpd_shape_cap_and_infinite_mean_protection():
    """GPD fitter must cap shape xi <= 0.95 to prevent infinite-mean divergence."""
    # Heavy Pareto synthetic sample
    np.random.seed(99)
    raw_pareto = (np.random.pareto(a=0.9, size=100) + 1.0) * 2.0  # infinite mean tail
    res = fit_pot_gpd(raw_pareto, threshold_u=2.0)

    assert res.shape_xi <= 0.95
    assert not math.isnan(res.var_99)
    assert not math.isinf(res.var_99)
    assert not math.isnan(res.cvar_99)
    assert not math.isinf(res.cvar_99)
    assert res.cvar_99 >= res.var_99


def test_gpd_pathological_boundary_zero_variance():
    """GPD fitter must handle zero-variance exceedances without NaN or division by zero."""
    constant_exceedances = [3.5, 3.5, 3.5, 3.5, 3.5]
    res = fit_pot_gpd(constant_exceedances, threshold_u=2.0)

    assert not math.isnan(res.shape_xi)
    assert not math.isnan(res.scale_sigma)
    assert not math.isnan(res.var_99)
    assert not math.isnan(res.cvar_99)
    assert not math.isnan(res.actuarial_war_risk_loading_bps)
    assert res.shape_xi == 0.0
    assert res.scale_sigma > 0.0


def test_gpd_quantile_monotonicity():
    """VaR_95 <= VaR_99 <= CVaR_99 must hold invariantly."""
    np.random.seed(123)
    data = np.random.exponential(scale=2.0, size=200) + 1.0
    res = fit_pot_gpd(data, threshold_u=2.0)

    assert res.var_95 <= res.var_99
    assert res.var_99 <= res.cvar_99
    assert res.actuarial_war_risk_loading_bps >= 0.0


def test_actuarial_war_risk_loading_bps():
    """Verify actuarial war-risk loading formula in basis points."""
    # If CVaR_99 is 8.5 on [0, 10] scale, loss_fraction = 0.85
    # With tail_prob = 0.01: loading = 0.85 * 0.01 * 10,000 = 85.0 bps
    bps = compute_actuarial_war_risk_loading_bps(cvar_99=8.5, insured_vessel_usd=85_000_000.0)
    assert math.isclose(bps, 85.0, abs_tol=1e-5)


@given(
    scale=st.floats(min_value=0.5, max_value=5.0),
    u=st.floats(min_value=0.0, max_value=5.0),
)
@settings(max_examples=15, deadline=None)
def test_hypothesis_fuzz_gpd_fitter(scale: float, u: float):
    """Property test verifying GPD fitter produces finite non-NaN outputs across parameters."""
    np.random.seed(int(scale * 100))
    sample = np.random.exponential(scale=scale, size=50) + u
    res = fit_pot_gpd(sample, threshold_u=u)
    assert not math.isnan(res.var_99)
    assert not math.isinf(res.var_99)
    assert not math.isnan(res.cvar_99)
    assert not math.isinf(res.cvar_99)
    assert res.var_99 <= res.cvar_99


# ==============================================================================
# Probability Calibration Tests
# ==============================================================================

def test_unweighted_brier_invariance_to_financial_loss_scale():
    """Unweighted Brier score must be invariant to financial loss amounts or weighting."""
    y_true = np.array([0, 1, 1, 0, 1])
    y_prob = np.array([0.1, 0.8, 0.6, 0.2, 0.9])

    score1 = brier_score(y_true, y_prob)

    # Verify score is strictly in [0.0, 1.0]
    assert 0.0 <= score1 <= 1.0

    # Even if transaction loss was $10,000 or $85,000,000, unweighted Brier depends ONLY
    # on forecast probability and binary event indicator
    manual_brier = float(np.mean((y_prob - y_true) ** 2))
    assert math.isclose(score1, manual_brier, abs_tol=1e-9)


def test_platt_and_isotonic_calibrators_on_pathological_inputs():
    """Calibrators must not crash or output NaN on extreme outlier or zero-variance inputs."""
    # Constant inputs
    constant_scores = np.array([2.0, 2.0, 2.0, 2.0])
    labels = np.array([0, 1, 0, 1])

    platt = PlattCalibrator().fit(constant_scores, labels)
    preds_platt = platt.predict_proba(constant_scores)
    assert not np.any(np.isnan(preds_platt))
    assert np.all((preds_platt >= 0.0) & (preds_platt <= 1.0))

    iso = IsotonicCalibrator().fit(constant_scores, labels)
    preds_iso = iso.predict_proba(constant_scores)
    assert not np.any(np.isnan(preds_iso))
    assert np.all((preds_iso >= 0.0) & (preds_iso <= 1.0))

    # Extreme outlier inputs: large positive and large negative numbers
    extreme_scores = np.array([-1e12, 1e12, 0.0])
    extreme_labels = np.array([0, 1, 0])
    platt_ext = PlattCalibrator().fit(extreme_scores, extreme_labels)
    preds_ext = platt_ext.predict_proba(extreme_scores)
    assert not np.any(np.isnan(preds_ext))
    assert not np.any(np.isinf(preds_ext))
    assert np.all((preds_ext >= 0.0) & (preds_ext <= 1.0))


def test_calibrate_exceedance_probabilities_pipeline():
    """Verify end-to-end exceedance probability calibration."""
    np.random.seed(42)
    residuals = np.random.normal(0, 1.5, 100)
    threshold = 1.0

    probs, calib = calibrate_exceedance_probabilities(residuals, threshold_u=threshold, method="platt")
    assert len(probs) == 100
    assert np.all((probs >= 0.0) & (probs <= 1.0))
    loss = log_loss((residuals > threshold).astype(float), probs)
    assert not math.isnan(loss)
    assert loss >= 0.0
