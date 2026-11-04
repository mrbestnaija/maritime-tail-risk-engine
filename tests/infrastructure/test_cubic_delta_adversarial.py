"""Adversarial Stress Test Suite for Cubic Delta Kernel (psi_3) and Wave Height Smoothing.

Challenger T3_1 (Kernel & Gradient Challenger).
Stress-tests:
1. Exact compact support: psi_3(u) == 0.0 for |u| >= 1.0 (boundary exactness, far tails, extreme floats).
2. Continuous derivatives: finite difference first and second derivatives at boundaries (u = +-1.0, u = 0.0).
3. Large step discontinuities: Hs jumping from 0.5m to 4.5m across 1 hour; checks gradient boundedness and C^1/C^2 smoothness.
4. Impulse spikes: rogue wave reading of 12.0m (and up to 1000.0m) amidst 1.5m baseline; checks attenuation and numeric overflow safety.
5. Degenerate boundary conditions: empty sequences, singleton, identical timestamps, irregular spacing, zero/negative bandwidth.
6. Non-negativity and convex hull preservation: smoothed Hs*(t) in [min(Hs), max(Hs)] for all non-negative inputs.
7. Integration with Cox hazard: feeds stressed smoothed Hs into HydroEnvelopeSpec / Phi(Hs) and Cox hazard formula,
   verifying bounded daily hazard and breach probability in (0, 1) with continuous transitions.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from maritime_risk.infrastructure.open_meteo_adapter import (
    cubic_delta_kernel,
    smooth_wave_heights_cubic_delta,
)
from maritime_risk.core.hydro_envelope import (
    skiff_boarding_feasibility,
    evaluate_hydrodynamic_envelope,
)
from maritime_risk.core.jwc_pricer import compute_cox_7day_breach_probability
from maritime_risk.core.specs import CoxHazardSpec, HydroEnvelopeSpec, VesselProfileSpec


# =============================================================================
# 1. Exact Compact Support Tests
# =============================================================================

def test_exact_compact_support_boundaries():
    """Verify psi_3(u) == 0.0 for |u| >= 1.0 strictly, including machine-epsilon boundaries."""
    # Exact boundary points
    assert cubic_delta_kernel(1.0) == 0.0
    assert cubic_delta_kernel(-1.0) == 0.0

    # Points just outside compact support (machine precision boundary)
    eps_values = [1e-15, 1e-12, 1e-9, 1e-6, 1e-3, 0.01, 0.1, 0.5, 1.0]
    for eps in eps_values:
        assert cubic_delta_kernel(1.0 + eps) == 0.0
        assert cubic_delta_kernel(-(1.0 + eps)) == 0.0

    # Far tails
    far_tails = [2.0, 5.0, 10.0, 100.0, 1e6, 1e12]
    for val in far_tails:
        assert cubic_delta_kernel(val) == 0.0
        assert cubic_delta_kernel(-val) == 0.0

    # Infinite inputs
    assert cubic_delta_kernel(float("inf")) == 0.0
    assert cubic_delta_kernel(float("-inf")) == 0.0

    # Inside compact support: strictly positive
    inside_points = [0.0, 0.001, 0.1, 0.5, 0.9, 0.99, 0.999999]
    for pt in inside_points:
        val_pos = cubic_delta_kernel(pt)
        val_neg = cubic_delta_kernel(-pt)
        assert 0.0 < val_pos <= 1.0
        assert val_pos == pytest.approx(val_neg, abs=1e-14)


# =============================================================================
# 2. Smoothness & Vanishing Finite Difference Derivatives at Boundaries
# =============================================================================

def test_finite_difference_first_and_second_derivatives_boundaries():
    """Verify first and second derivatives vanish continuously at u = 1.0, u = -1.0, and u = 0.0 without step jumps."""
    h = 1e-5

    def d1(u: float) -> float:
        """Central difference first derivative."""
        return (cubic_delta_kernel(u + h) - cubic_delta_kernel(u - h)) / (2.0 * h)

    def d2(u: float) -> float:
        """Central difference second derivative."""
        return (cubic_delta_kernel(u + h) - 2.0 * cubic_delta_kernel(u) + cubic_delta_kernel(u - h)) / (h * h)

    # At u = 1.0: psi_3'(1.0) == 0 and psi_3''(1.0) == 0
    d1_right_bound = d1(1.0)
    d2_right_bound = d2(1.0)
    assert abs(d1_right_bound) < 1e-4, f"Non-zero first derivative at u=1.0: {d1_right_bound}"
    assert abs(d2_right_bound) < 1e-2, f"Non-zero second derivative at u=1.0: {d2_right_bound}"

    # At u = -1.0: psi_3'(-1.0) == 0 and psi_3''(-1.0) == 0
    d1_left_bound = d1(-1.0)
    d2_left_bound = d2(-1.0)
    assert abs(d1_left_bound) < 1e-4, f"Non-zero first derivative at u=-1.0: {d1_left_bound}"
    assert abs(d2_left_bound) < 1e-2, f"Non-zero second derivative at u=-1.0: {d2_left_bound}"

    # At u = 0.0: apex point, psi_3'(0.0) == 0 and psi_3''(0.0) == 0 (since psi_3''(u) ~ -18u as u->0)
    d1_origin = d1(0.0)
    d2_origin = d2(0.0)
    assert abs(d1_origin) < 1e-8, f"Non-zero first derivative at u=0.0: {d1_origin}"
    assert abs(d2_origin) < 1e-4, f"Non-zero second derivative at u=0.0: {d2_origin}"

    # Check one-sided convergence of first and second derivatives at u = 1.0, u = -1.0, and u = 0.0
    for h_test in [1e-3, 1e-4, 1e-5]:
        # At u = 1.0
        d1_left_1 = (cubic_delta_kernel(1.0) - cubic_delta_kernel(1.0 - h_test)) / h_test
        d1_right_1 = (cubic_delta_kernel(1.0 + h_test) - cubic_delta_kernel(1.0)) / h_test
        assert abs(d1_left_1 - d1_right_1) < 1e-4, f"First derivative jump at u=1.0: {abs(d1_left_1 - d1_right_1)}"

        d2_left_1 = (cubic_delta_kernel(1.0) - 2.0 * cubic_delta_kernel(1.0 - h_test) + cubic_delta_kernel(1.0 - 2.0 * h_test)) / (h_test * h_test)
        d2_right_1 = (cubic_delta_kernel(1.0 + 2.0 * h_test) - 2.0 * cubic_delta_kernel(1.0 + h_test) + cubic_delta_kernel(1.0)) / (h_test * h_test)
        assert abs(d2_left_1 - d2_right_1) < 0.2, f"Second derivative jump at u=1.0: {abs(d2_left_1 - d2_right_1)}"

        # At u = -1.0
        d1_left_m1 = (cubic_delta_kernel(-1.0) - cubic_delta_kernel(-1.0 - h_test)) / h_test
        d1_right_m1 = (cubic_delta_kernel(-1.0 + h_test) - cubic_delta_kernel(-1.0)) / h_test
        assert abs(d1_left_m1 - d1_right_m1) < 1e-4, f"First derivative jump at u=-1.0: {abs(d1_left_m1 - d1_right_m1)}"

        # At u = 0.0
        d1_left_0 = (cubic_delta_kernel(0.0) - cubic_delta_kernel(0.0 - h_test)) / h_test
        d1_right_0 = (cubic_delta_kernel(0.0 + h_test) - cubic_delta_kernel(0.0)) / h_test
        assert abs(d1_left_0 + d1_right_0) < 1e-5, f"Asymmetry in first derivative at u=0.0: {abs(d1_left_0 + d1_right_0)}"

    # Boundary transition continuity: verify derivative smoothly approaches zero as u -> 1.0 from inside
    for u_near_1 in [0.99, 0.999, 0.9999]:
        d1_near = d1(u_near_1)
        d2_near = d2(u_near_1)
        assert abs(d1_near) < 0.01, f"Derivative not vanishing near u=1.0: {d1_near} at u={u_near_1}"
        assert abs(d2_near) < 2.0, f"Second derivative not bounded near u=1.0: {d2_near} at u={u_near_1}"

    # Smoothness across u in [0.98, 1.02]
    u_grid = np.linspace(0.98, 1.02, 41)
    d1_vals = [d1(float(u)) for u in u_grid]
    for i in range(len(d1_vals) - 1):
        step_d1 = abs(d1_vals[i + 1] - d1_vals[i])
        assert step_d1 < 0.01, f"Discontinuous derivative jump at step {i}: {step_d1}"


# =============================================================================
# 3. Wave Height Smoothing: Step Discontinuity Stress
# =============================================================================

def test_large_step_discontinuity_bounded_gradient():
    """Verify Hs jump from 0.5m to 4.5m yields bounded, continuous gradients without ringing or overshoot."""
    # Discrete jump at t = 3.0h
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    heights = [0.5, 0.5, 0.5, 4.5, 4.5, 4.5, 4.5]

    eval_times = np.linspace(0.0, 6.0, 301)
    smoothed = [
        smooth_wave_heights_cubic_delta(
            timestamps_hours=timestamps,
            wave_heights=heights,
            target_time_hour=float(t),
            bandwidth_hours=3.0,
            delta=1.0,
        )
        for t in eval_times
    ]

    # Invariant 1: Convex hull preservation (no overshoot above 4.5m or undershoot below 0.5m)
    assert min(smoothed) >= 0.5 - 1e-12
    assert max(smoothed) <= 4.5 + 1e-12

    # Invariant 2: Bounded gradient |dH*/dt|
    dt = eval_times[1] - eval_times[0]
    gradients = [abs(smoothed[i + 1] - smoothed[i]) / dt for i in range(len(smoothed) - 1)]
    max_gradient = max(gradients)
    # With bandwidth=3.0h and delta=1.0 (h_eff=3.0), the maximum slope for a 4.0m step is bounded
    assert max_gradient < 2.5, f"Excessive wave gradient detected: {max_gradient:.3f} m/h"

    # Invariant 3: Continuous gradient (second derivative / gradient acceleration bounded)
    grad_diffs = [abs(gradients[i + 1] - gradients[i]) for i in range(len(gradients) - 1)]
    max_grad_diff = max(grad_diffs)
    assert max_grad_diff < 0.2, f"Gradient discontinuity detected: {max_grad_diff}"


# =============================================================================
# 4. Wave Height Smoothing: Impulse Spike Stress & Numerical Stability
# =============================================================================

def test_impulse_spike_attenuation_and_numerical_stability():
    """Verify rogue wave reading of 12.0m (and extreme 1000m) is smoothly attenuated without numeric overflow."""
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    # Rogue wave 12.0m at t = 3.0h amidst 1.5m baseline
    heights_12m = [1.5, 1.5, 1.5, 12.0, 1.5, 1.5, 1.5]

    eval_times = np.linspace(0.0, 6.0, 121)
    smoothed_12m = [
        smooth_wave_heights_cubic_delta(
            timestamps_hours=timestamps,
            wave_heights=heights_12m,
            target_time_hour=float(t),
            bandwidth_hours=3.0,
            delta=1.0,
        )
        for t in eval_times
    ]

    # Peak smoothed wave height at t=3.0 must be significantly attenuated relative to 12.0m spike
    peak_smoothed = max(smoothed_12m)
    assert 3.0 < peak_smoothed < 6.5, f"Spike attenuation out of expected envelope: {peak_smoothed}"

    # Smooth recovery back to baseline at ends
    assert abs(smoothed_12m[0] - 1.5) < 0.1
    assert abs(smoothed_12m[-1] - 1.5) < 0.1

    # Extreme impulse stress: 50m, 100m, 1000m spikes
    for extreme_spike in [50.0, 100.0, 1000.0]:
        heights_extreme = [1.5, 1.5, 1.5, extreme_spike, 1.5, 1.5, 1.5]
        res = smooth_wave_heights_cubic_delta(
            timestamps_hours=timestamps,
            wave_heights=heights_extreme,
            target_time_hour=3.0,
            bandwidth_hours=3.0,
            delta=1.0,
        )
        assert not math.isnan(res), f"NaN produced for extreme spike {extreme_spike}"
        assert not math.isinf(res), f"Inf produced for extreme spike {extreme_spike}"
        assert 1.5 <= res <= extreme_spike


# =============================================================================
# 5. Degenerate Boundary Conditions
# =============================================================================

def test_degenerate_boundary_conditions():
    """Verify empty, singleton, identical timestamps, irregular spacing, and negative parameters."""
    # 1. Empty inputs
    assert smooth_wave_heights_cubic_delta([], []) == 0.0
    assert smooth_wave_heights_cubic_delta([1.0], []) == 0.0

    # 2. Singleton
    assert smooth_wave_heights_cubic_delta([4.0], [3.2]) == 3.2
    assert smooth_wave_heights_cubic_delta([4.0], [3.2], target_time_hour=100.0) == 3.2

    # 3. Identical timestamps (multiple readings at same time coordinate)
    res_identical = smooth_wave_heights_cubic_delta(
        timestamps_hours=[2.0, 2.0, 2.0, 2.0],
        wave_heights=[1.0, 2.0, 3.0, 4.0],
        target_time_hour=2.0,
    )
    assert res_identical == pytest.approx(2.5, abs=1e-12)

    # 4. Irregular / non-uniform time spacing
    irregular_times = [0.0, 0.05, 0.1, 1.5, 5.0, 24.0]
    irregular_heights = [1.2, 1.3, 1.1, 2.2, 3.1, 1.8]
    for t_query in [-10.0, 0.0, 0.075, 1.0, 10.0, 100.0]:
        sm_irr = smooth_wave_heights_cubic_delta(
            timestamps_hours=irregular_times,
            wave_heights=irregular_heights,
            target_time_hour=t_query,
        )
        assert not math.isnan(sm_irr)
        assert not math.isinf(sm_irr)
        assert min(irregular_heights) <= sm_irr <= max(irregular_heights)

    # 5. Target time far outside window: graceful fallback to latest point
    out_of_window = smooth_wave_heights_cubic_delta(
        timestamps_hours=[0.0, 1.0, 2.0],
        wave_heights=[1.5, 1.6, 1.7],
        target_time_hour=500.0,
        bandwidth_hours=3.0,
    )
    assert out_of_window == 1.7

    # 6. Zero or negative bandwidth / delta: clamp prevents division by zero
    res_zero_bw = smooth_wave_heights_cubic_delta(
        timestamps_hours=[0.0, 1.0, 2.0],
        wave_heights=[1.5, 1.6, 1.7],
        target_time_hour=2.0,
        bandwidth_hours=0.0,
        delta=0.0,
    )
    assert 1.5 <= res_zero_bw <= 1.7
    assert not math.isnan(res_zero_bw)

    res_neg = smooth_wave_heights_cubic_delta(
        timestamps_hours=[0.0, 1.0, 2.0],
        wave_heights=[1.5, 1.6, 1.7],
        target_time_hour=2.0,
        bandwidth_hours=-5.0,
        delta=-1.0,
    )
    assert 1.5 <= res_neg <= 1.7
    assert not math.isnan(res_neg)


# =============================================================================
# 6. Non-Negativity & Convex Hull Invariant
# =============================================================================

def test_non_negativity_and_convex_hull_invariants():
    """Verify smoothed wave heights never produce negative values from non-negative inputs and strictly obey convex hull bounds."""
    np.random.seed(42)
    for _ in range(50):
        n = np.random.randint(2, 50)
        times = sorted(np.random.uniform(0.0, 24.0, size=n).tolist())
        heights = np.random.uniform(0.0, 15.0, size=n).tolist()
        t_target = float(np.random.uniform(-5.0, 30.0))
        bw = float(np.random.uniform(0.5, 10.0))
        delta = float(np.random.uniform(0.1, 5.0))

        smoothed_val = smooth_wave_heights_cubic_delta(
            timestamps_hours=times,
            wave_heights=heights,
            target_time_hour=t_target,
            bandwidth_hours=bw,
            delta=delta,
        )

        # Invariant 1: Strictly non-negative
        assert smoothed_val >= 0.0, f"Negative smoothed wave height: {smoothed_val}"

        # Invariant 2: Convex hull property
        min_h = min(heights)
        max_h = max(heights)
        assert min_h - 1e-12 <= smoothed_val <= max_h + 1e-12, (
            f"Smoothed wave height {smoothed_val} outside convex hull [{min_h}, {max_h}]"
        )


# =============================================================================
# 7. Integration with Cox Hazard & Skiff Boarding Feasibility Phi(Hs)
# =============================================================================

def test_cox_hazard_integration_under_stressed_wave_heights():
    """Verify feeding stressed smoothed Hs into HydroEnvelopeSpec / Phi(Hs) and Cox hazard maintains bounded hazard in (0, 1)."""
    h_spec = HydroEnvelopeSpec()
    c_spec = CoxHazardSpec()
    v_spec = VesselProfileSpec()

    # Step stress wave height profile from 0.5m to 4.5m
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    heights = [0.5, 0.5, 0.5, 4.5, 4.5, 4.5, 4.5]

    eval_times = np.linspace(0.0, 6.0, 61)
    feasibilities = []
    daily_hazards = []
    p_breach_7ds = []

    for t in eval_times:
        hs_smooth = smooth_wave_heights_cubic_delta(
            timestamps_hours=timestamps,
            wave_heights=heights,
            target_time_hour=float(t),
            bandwidth_hours=3.0,
            delta=1.0,
        )

        # 1. Feasibility Phi(Hs)
        phi = skiff_boarding_feasibility(wave_height_m=hs_smooth, spec=h_spec)
        assert 0.0 <= phi <= 1.0, f"Phi(Hs) out of bounds: {phi}"
        feasibilities.append(phi)

        # 2. Cox hazard evaluation
        p_7d, daily_h, ohi = compute_cox_7day_breach_probability(
            mothership_loitering_idx=0.3,
            distance_pmsc_km=150.0,
            wave_height_m=hs_smooth,
            vessel_spec=v_spec,
            cox_spec=c_spec,
            hydro_spec=h_spec,
        )

        assert 0.0 < p_7d < 1.0, f"P_breach_7d out of (0, 1): {p_7d}"
        assert 0.0 < daily_h < 1.0, f"Daily hazard rate out of (0, 1): {daily_h}"
        daily_hazards.append(daily_h)
        p_breach_7ds.append(p_7d)

    # Monotonic transition across the step: as wave height increases from 0.5m to 4.5m,
    # skiff boarding feasibility must decrease, causing daily hazard and p_breach_7d to decrease.
    assert feasibilities[0] > feasibilities[-1]
    assert daily_hazards[0] > daily_hazards[-1]
    assert p_breach_7ds[0] > p_breach_7ds[-1]

    # Verify continuity of p_breach_7d across step transition (no discrete step jumps)
    for i in range(len(p_breach_7ds) - 1):
        delta_p = abs(p_breach_7ds[i + 1] - p_breach_7ds[i])
        assert delta_p < 0.05, f"Discontinuous hazard step detected: {delta_p} at step {i}"


def test_cox_hazard_under_extreme_impulse_spike():
    """Verify 12.0m rogue wave attenuates boarding feasibility and suppresses hazard safely without underflow/overflow."""
    h_spec = HydroEnvelopeSpec()
    c_spec = CoxHazardSpec()
    v_spec = VesselProfileSpec()

    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    heights = [1.5, 1.5, 1.5, 12.0, 1.5, 1.5, 1.5]

    for t in [0.0, 2.0, 3.0, 4.0, 6.0]:
        hs_smooth = smooth_wave_heights_cubic_delta(
            timestamps_hours=timestamps,
            wave_heights=heights,
            target_time_hour=float(t),
            bandwidth_hours=3.0,
            delta=1.0,
        )
        p_7d, daily_h, _ = compute_cox_7day_breach_probability(
            mothership_loitering_idx=0.25,
            distance_pmsc_km=180.0,
            wave_height_m=hs_smooth,
            vessel_spec=v_spec,
            cox_spec=c_spec,
            hydro_spec=h_spec,
        )
        assert 0.0 < p_7d < 1.0
        assert 0.0 < daily_h < 1.0
        assert not math.isnan(p_7d)
        assert not math.isnan(daily_h)
