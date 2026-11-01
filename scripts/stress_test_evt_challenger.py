"""Adversarial Empirical Stress Harness: EVT, Empirical Bayes, and CVaR Dynamics.

Empirical Challenger verification harness probing:
1. shrink_gpd_parameters and fit_pot_gpd:
   - Raw xi > 0.95 (capping at xi_max = 0.95 without NaN/inf/exceptions)
   - Negative raw xi (shrinkage toward corridor priors)
   - Heavy tails (xi in [0.30, 0.50]) allowing authentic heavy tails without 0.25 clamp
2. CVaR calculation with heavy-tail parameters:
   - compute_gpd_var_cvar and composite CVaR unclamping without explosion
   - Demurrage calculation scaling in JWC pricer with unclamped CVaR
3. Edge cases and pathological stability:
   - Zero-variance, single observation, extreme magnitude, NaN/inf inputs, boundary xi values.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import numpy as np

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from maritime_risk.core.empirical_bayes import shrink_gpd_parameters
from maritime_risk.core.gpd_tail_fitter import (
    compute_gpd_var_cvar,
    compute_actuarial_war_risk_loading_bps,
    fit_pot_gpd,
    gpd_cdf,
)
from maritime_risk.core.jwc_pricer import (
    compute_jwc_7day_war_risk_ap,
    price_cox_7day_war_risk_ap,
)
from maritime_risk.core.specs import (
    CorridorSpec,
    CoxHazardSpec,
    EmpiricalBayesSpec,
    GPDFitterSpec,
    MacroRegimeSpec,
    VesselProfileSpec,
)


def run_test_1_raw_xi_super_critical():
    """Test 1: What happens when raw xi > 0.95? Does it strictly cap at xi_max = 0.95?"""
    print("=" * 80)
    print("TEST 1: RAW XI > 0.95 CAP ENFORCEMENT & STABILITY")
    print("=" * 80)

    spec_default = GPDFitterSpec(xi_max=0.95)
    eb_spec = EmpiricalBayesSpec(prior_xi=0.18, xi_max=0.95)

    test_shapes = [0.90, 0.95, 0.96, 1.0, 1.1, 1.5, 2.0, 5.0, 10.0]
    results = []

    for true_xi in test_shapes:
        # Generate heavy-tailed samples from GPD using inversion: y = ( (1-U)^(-xi) - 1 ) * sigma / xi
        np.random.seed(42)
        u_rand = np.random.uniform(0.001, 0.999, size=20)
        exceedances = (np.power(1.0 - u_rand, -true_xi) - 1.0) * (2.0 / true_xi)
        exceedances = exceedances[np.isfinite(exceedances) & (exceedances > 0.0)]

        # 1. shrink_gpd_parameters directly
        xi_shrunk, sigma_shrunk, w = shrink_gpd_parameters(exceedances, spec=eb_spec)

        # 2. fit_pot_gpd
        data = np.concatenate([np.ones(80) * 0.5, exceedances + 2.0])
        fit_res = fit_pot_gpd(data, threshold_u=2.0, spec=spec_default, bayes_spec=eb_spec)

        has_nan = any(math.isnan(v) for v in [xi_shrunk, sigma_shrunk, fit_res.shape_xi, fit_res.cvar_99])
        has_inf = any(math.isinf(v) for v in [xi_shrunk, sigma_shrunk, fit_res.shape_xi, fit_res.cvar_99])
        capped_eb = xi_shrunk <= 0.95 + 1e-9
        capped_fit = fit_res.shape_xi <= 0.95 + 1e-9

        passed = (not has_nan) and (not has_inf) and capped_eb and capped_fit
        results.append({
            "true_xi": true_xi,
            "xi_shrunk": xi_shrunk,
            "fit_shape_xi": fit_res.shape_xi,
            "raw_xi": fit_res.raw_xi,
            "cvar_99": fit_res.cvar_99,
            "composite_cvar_99": fit_res.composite_corridor_cvar_99,
            "passed": passed,
        })
        status = "PASS" if passed else "FAIL"
        print(f"True xi: {true_xi:5.2f} | EB xi_shrunk: {xi_shrunk:.4f} | Fit shape_xi: {fit_res.shape_xi:.4f} | "
              f"Raw xi: {fit_res.raw_xi:.4f} | CVaR_99: {fit_res.cvar_99:8.2f} | Status: {status}")

    # Explicit test: prior_xi itself > 0.95
    spec_hyper_prior = EmpiricalBayesSpec(prior_xi=1.50, xi_max=0.95)
    xi_hyper, _, _ = shrink_gpd_parameters([1.0, 2.0, 3.0], spec=spec_hyper_prior)
    assert xi_hyper <= 0.95, f"Hyper prior xi failed to cap: {xi_hyper}"
    print(f"Hyper prior_xi=1.50 -> Shrunk xi: {xi_hyper:.4f} <= 0.95 [PASS]")

    all_passed = all(r["passed"] for r in results)
    print(f"Test 1 Overall Verdict: {'PASS' if all_passed else 'FAIL'}\n")
    return all_passed, results


def run_test_2_negative_raw_xi():
    """Test 2: What happens with negative raw xi? Does it shrink appropriately towards corridor priors?"""
    print("=" * 80)
    print("TEST 2: NEGATIVE RAW XI & EMPIRICAL BAYES SHRINKAGE")
    print("=" * 80)

    priors = [0.12, 0.16, 0.18]
    test_negative_xis = [-0.10, -0.25, -0.40, -0.49, -0.80]
    results = []

    for prior in priors:
        eb_spec = EmpiricalBayesSpec(prior_xi=prior, kappa=12.0)
        for true_xi in test_negative_xis:
            # GPD with negative xi has upper endpoint: y in [0, -sigma/xi]
            sigma = 2.0
            np.random.seed(42)
            u_rand = np.random.uniform(0.01, 0.99, size=15)  # small sample to activate shrinkage
            exceedances = (np.power(1.0 - u_rand, -true_xi) - 1.0) * (sigma / true_xi)

            xi_shrunk, sigma_shrunk, w = shrink_gpd_parameters(exceedances, spec=eb_spec)

            # Fit POT GPD
            data = np.concatenate([np.ones(60) * 0.5, exceedances + 2.0])
            fit_res = fit_pot_gpd(data, threshold_u=2.0, bayes_spec=eb_spec)

            # Shrinkage should pull negative xi toward the positive prior xi
            pulled_toward_prior = xi_shrunk > true_xi
            no_nan_inf = not any(math.isnan(v) or math.isinf(v) for v in [xi_shrunk, fit_res.cvar_99])
            passed = pulled_toward_prior and no_nan_inf

            results.append({
                "prior": prior,
                "true_xi": true_xi,
                "xi_shrunk": xi_shrunk,
                "fit_shape_xi": fit_res.shape_xi,
                "weight_w": w,
                "passed": passed,
            })
            status = "PASS" if passed else "FAIL"
            print(f"Prior: {prior:.2f} | True xi: {true_xi:5.2f} | Shrunk xi: {xi_shrunk:+.4f} (w={w:.2f}) | "
                  f"Fit shape_xi: {fit_res.shape_xi:+.4f} | Status: {status}")

    all_passed = all(r["passed"] for r in results)
    print(f"Test 2 Overall Verdict: {'PASS' if all_passed else 'FAIL'}\n")
    return all_passed, results


def run_test_3_heavy_tails_authentic_unclamped():
    """Test 3: What happens when samples have heavy tails (xi in [0.3, 0.5])?
    Does it allow authentic heavy tails rather than being clamped to 0.25?"""
    print("=" * 80)
    print("TEST 3: HEAVY TAILS (XI in [0.30, 0.50]) AUTHENTIC UNCLAMPED ESTIMATION")
    print("=" * 80)

    target_heavy_xis = [0.28, 0.32, 0.38, 0.42, 0.48, 0.55]
    results = []

    eb_spec = EmpiricalBayesSpec(prior_xi=0.18, kappa=5.0)

    for target_xi in target_heavy_xis:
        np.random.seed(123)
        u_rand = np.random.uniform(0.01, 0.99, size=40)
        sigma = 2.5
        exceedances = (np.power(1.0 - u_rand, -target_xi) - 1.0) * (sigma / target_xi)

        xi_shrunk, sigma_shrunk, w = shrink_gpd_parameters(exceedances, spec=eb_spec)

        data = np.concatenate([np.ones(100) * 1.0, exceedances + 3.0])
        fit_res = fit_pot_gpd(data, threshold_u=3.0, bayes_spec=eb_spec)

        # In the old code, xi_shrunk was clamped to 0.25!
        # Here, for target_xi > 0.30, xi_shrunk and fit_res.shape_xi MUST exceed 0.25!
        exceeds_old_clamp = xi_shrunk > 0.25
        passed = exceeds_old_clamp and (xi_shrunk <= 0.95)

        results.append({
            "target_xi": target_xi,
            "xi_shrunk": xi_shrunk,
            "fit_shape_xi": fit_res.shape_xi,
            "exceeds_0_25": exceeds_old_clamp,
            "passed": passed,
        })
        status = "PASS" if passed else "FAIL"
        print(f"Target xi: {target_xi:.2f} | Shrunk xi: {xi_shrunk:.4f} | Fit shape_xi: {fit_res.shape_xi:.4f} | "
              f"> 0.25: {exceeds_old_clamp} | Status: {status}")

    all_passed = all(r["passed"] for r in results)
    print(f"Test 3 Overall Verdict: {'PASS' if all_passed else 'FAIL'}\n")
    return all_passed, results


def run_test_4_cvar_heavy_tail_unclamped_scaling():
    """Test 4: Test CVaR calculation with heavy-tail parameters:
    - Does composite CVaR produce unclamped values without exploding or failing?
    - Does demurrage calculation in JWC pricer scale smoothly with unclamped CVaR?
    """
    print("=" * 80)
    print("TEST 4: CVAR UNCLAMPED COMPUTATION & JWC DEMURRAGE SCALING")
    print("=" * 80)

    # 4A. CVaR values across shape xi from 0.0 to 0.95
    u, sigma, p_u = 3.0, 1.5, 0.05
    xis = [0.0, 0.10, 0.25, 0.33, 0.40, 0.50, 0.65, 0.80, 0.90, 0.94, 0.95]
    cvar_results = []

    prev_cvar = 0.0
    for xi in xis:
        var_99, cvar_99 = compute_gpd_var_cvar(u, xi=xi, sigma=sigma, p_u=p_u, alpha=0.99)
        composite_cvar = 5.0 + cvar_99  # anchored baseline 5.0

        # Monotonicity with xi: as xi increases, tail heaviness increases => CVaR strictly increases
        monotonic = cvar_99 >= prev_cvar
        prev_cvar = cvar_99
        no_nan_inf = np.isfinite(cvar_99) and np.isfinite(var_99)

        cvar_results.append({
            "xi": xi,
            "var_99": var_99,
            "cvar_99": cvar_99,
            "composite_cvar": composite_cvar,
            "monotonic": monotonic,
            "finite": no_nan_inf,
        })
        print(f"xi: {xi:4.2f} | VaR_99: {var_99:8.3f} | CVaR_99: {cvar_99:10.3f} | "
              f"Comp CVaR: {composite_cvar:10.3f} | Monotonic: {monotonic} | Finite: {no_nan_inf}")

    # 4B. JWC Demurrage and AP scaling with unclamped CVaR
    vessel = VesselProfileSpec(
        insured_vessel_usd=85_000_000.0,
        daily_demurrage_usd=45_000.0,
        catastrophic_boarding_loss_usd=3_500_000.0,
        delay_days_per_cvar_unit=0.85,
    )
    corridor = CorridorSpec(jwc_market_benchmark_bps=10.0, operational_state="AT_ANCHOR")

    test_cvars = [1.0, 5.0, 10.0, 20.0, 25.83, 36.97, 50.0, 100.0]
    pricer_results = []
    prev_ap = 0.0

    print("-" * 80)
    print("Demurrage and AP Scaling Across Unclamped Composite CVaR_99:")
    for cvar in test_cvars:
        res = compute_jwc_7day_war_risk_ap(
            calibrated_7d_breach_prob=0.08,
            composite_cvar_99=cvar,
            vessel_spec=vessel,
            corridor_spec=corridor,
            regime_multiplier=1.2,
        )

        # Check smooth linear scaling
        # demurrage = cvar * delay_factor * daily_rate
        expected_demurrage = cvar * 0.85 * 45_000.0
        demurrage_matches = math.isclose(res.cvar_99_demurrage_usd, expected_demurrage, rel_tol=1e-5)
        ap_increases = res.actuarial_7d_war_risk_ap_bps > prev_ap
        prev_ap = res.actuarial_7d_war_risk_ap_bps

        passed = demurrage_matches and ap_increases and np.isfinite(res.actuarial_7d_war_risk_ap_bps)
        pricer_results.append({
            "cvar": cvar,
            "delay_days": res.delay_days,
            "demurrage_usd": res.cvar_99_demurrage_usd,
            "catastrophic_usd": res.catastrophic_tail_loss_usd,
            "ap_bps": res.actuarial_7d_war_risk_ap_bps,
            "passed": passed,
        })
        status = "PASS" if passed else "FAIL"
        print(f"CVaR: {cvar:6.2f} | Delay: {res.delay_days:6.2f}d | Demurrage: ${res.cvar_99_demurrage_usd:11,.2f} | "
              f"AP: {res.actuarial_7d_war_risk_ap_bps:8.2f} bps | Status: {status}")

    all_passed_cvar = all(r["finite"] and r["monotonic"] for r in cvar_results)
    all_passed_pricer = all(r["passed"] for r in pricer_results)
    passed_overall = all_passed_cvar and all_passed_pricer
    print(f"Test 4 Overall Verdict: {'PASS' if passed_overall else 'FAIL'}\n")
    return passed_overall, (cvar_results, pricer_results)


def run_test_5_pathological_boundary_matrix():
    """Test 5: Pathological and adversarial input edge cases:
    - Empty, single, two observations
    - Zero variance
    - Pathological negative and extreme numbers
    - Inf / NaN in data
    - xi boundary exact limits
    """
    print("=" * 80)
    print("TEST 5: PATHOLOGICAL BOUNDARY MATRIX")
    print("=" * 80)

    cases = [
        ("Empty array", []),
        ("Single observation", [5.0]),
        ("Two identical values", [4.0, 4.0]),
        ("Three identical values (zero variance)", [7.0, 7.0, 7.0]),
        ("Negative exceedances (should be filtered)", [-10.0, -5.0, -1.0]),
        ("Mixed NaN/Inf/valid", [np.nan, 2.0, np.inf, 4.0, -np.inf, 6.0]),
        ("Huge outlier (1e9)", [1.0, 2.0, 3.0, 1e9]),
        ("Tiny scale (1e-6)", [1e-6, 2e-6, 3e-6]),
    ]

    results = []
    eb_spec = EmpiricalBayesSpec(prior_xi=0.18, prior_sigma=1.50, kappa=12.0)
    gpd_spec = GPDFitterSpec(xi_max=0.95)

    for name, data in cases:
        try:
            # Test EB
            xi_s, sig_s, w = shrink_gpd_parameters(data, spec=eb_spec)
            eb_finite = np.isfinite(xi_s) and np.isfinite(sig_s) and np.isfinite(w)

            # Test GPD Fitter
            fit_res = fit_pot_gpd(data, threshold_u=1.0, spec=gpd_spec, bayes_spec=eb_spec)
            fit_finite = (
                np.isfinite(fit_res.shape_xi)
                and np.isfinite(fit_res.scale_sigma)
                and np.isfinite(fit_res.var_99)
                and np.isfinite(fit_res.cvar_99)
                and np.isfinite(fit_res.composite_corridor_cvar_99)
            )
            capped = fit_res.shape_xi <= 0.95 + 1e-9

            passed = eb_finite and fit_finite and capped
            results.append({"name": name, "passed": passed, "error": None})
            status = "PASS" if passed else "FAIL"
            print(f"{name:45s} -> EB xi: {xi_s:.4f}, Fit xi: {fit_res.shape_xi:.4f}, CVaR: {fit_res.cvar_99:.2f} | {status}")
        except Exception as e:
            results.append({"name": name, "passed": False, "error": str(e)})
            print(f"{name:45s} -> EXCEPTION: {e} | FAIL")

    all_passed = all(r["passed"] for r in results)
    print(f"Test 5 Overall Verdict: {'PASS' if all_passed else 'FAIL'}\n")
    return all_passed, results


def main():
    print("=" * 80)
    print("STARTING MARITIME RISK EVT & EMPIRICAL BAYES EMPIRICAL CHALLENGER SUITE")
    print("=" * 80)

    t1_pass, t1_res = run_test_1_raw_xi_super_critical()
    t2_pass, t2_res = run_test_2_negative_raw_xi()
    t3_pass, t3_res = run_test_3_heavy_tails_authentic_unclamped()
    t4_pass, t4_res = run_test_4_cvar_heavy_tail_unclamped_scaling()
    t5_pass, t5_res = run_test_5_pathological_boundary_matrix()

    all_passed = t1_pass and t2_pass and t3_pass and t4_pass and t5_pass
    print("=" * 80)
    print(f"FINAL ADVERSARIAL STRESS SUITE STATUS: {'ALL TESTS PASSED (APPROVE)' if all_passed else 'FAILURES DETECTED (REQUEST_CHANGES)'}")
    print("=" * 80)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
