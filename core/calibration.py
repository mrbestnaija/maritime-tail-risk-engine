"""Proper Unweighted Probability Calibration Engine.

Implements:
1. Unweighted Brier Score and Log-Loss proper scoring evaluators
2. Unweighted Platt (logistic) calibrator with stable sigmoid (anti-overflow)
3. Unweighted Isotonic calibrator via pure NumPy Pool Adjacent Violators Algorithm (PAVA)
4. Exceedance probability calibrator: p_hat_t = Pr(R_{t+1} > u)

Hard Mathematical Invariants:
- Never weight probability calibration by financial loss magnitude (abs(loss)),
  preserving strictly proper probability scoring.
- Numerical stability on pathological boundaries (zero-variance, extreme outliers, xi -> 0).
- Pure domain math: ZERO I/O, ZERO PRINT, pure NumPy/SciPy.
"""

from __future__ import annotations

from typing import Literal, Optional, Sequence
import numpy as np
from scipy.optimize import minimize


def brier_score(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
) -> float:
    """Compute strictly unweighted Brier Score.

    Brier = (1 / N) * sum((y_prob - y_true)^2)

    Strictly invariant to financial loss magnitudes or transaction scales.
    """
    yt = np.asarray(y_true, dtype=np.float64).ravel()
    yp = np.asarray(y_prob, dtype=np.float64).ravel()

    if len(yt) == 0 or len(yp) == 0:
        return 0.0

    if len(yt) != len(yp):
        raise ValueError(
            f"Dimension mismatch in brier_score: y_true len={len(yt)} != y_prob len={len(yp)}"
        )

    # Invariant: y_prob clamped to [0.0, 1.0]
    yp_clipped = np.clip(yp, 0.0, 1.0)
    return float(np.mean((yp_clipped - yt) ** 2))


def log_loss(
    y_true: Sequence[float] | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    eps: float = 1e-15,
) -> float:
    """Compute strictly unweighted Binary Cross-Entropy / Log-Loss.

    Loss = -(1 / N) * sum(y * ln(p) + (1 - y) * ln(1 - p))

    Probabilities clipped to [eps, 1 - eps] to prevent log(0) without 1e-9 explosions.
    """
    yt = np.asarray(y_true, dtype=np.float64).ravel()
    yp = np.asarray(y_prob, dtype=np.float64).ravel()

    if len(yt) == 0 or len(yp) == 0:
        return 0.0

    if len(yt) != len(yp):
        raise ValueError(
            f"Dimension mismatch in log_loss: y_true len={len(yt)} != y_prob len={len(yp)}"
        )

    p = np.clip(yp, eps, 1.0 - eps)
    return float(-np.mean(yt * np.log(p) + (1.0 - yt) * np.log(1.0 - p)))


def _stable_sigmoid(z: np.ndarray) -> np.ndarray:
    """Numerically stable logistic sigmoid preventing overflow for extreme values."""
    z_arr = np.asarray(z, dtype=np.float64)
    # For z >= 0: 1 / (1 + exp(-z))
    # For z < 0:  exp(z) / (1 + exp(z))
    out = np.empty_like(z_arr)
    pos_mask = z_arr >= 0
    neg_mask = ~pos_mask

    out[pos_mask] = 1.0 / (1.0 + np.exp(-z_arr[pos_mask]))
    exp_neg = np.exp(z_arr[neg_mask])
    out[neg_mask] = exp_neg / (1.0 + exp_neg)
    return out


class PlattCalibrator:
    """Unweighted Platt Calibrator (logistic scaling for probability calibration)."""

    def __init__(self, slope_a: float = 1.0, intercept_b: float = 0.0) -> None:
        self.slope_a = float(slope_a)
        self.intercept_b = float(intercept_b)
        self.is_fitted = False

    def fit(
        self,
        scores: Sequence[float] | np.ndarray,
        y_true: Sequence[float] | np.ndarray,
    ) -> PlattCalibrator:
        """Fit unweighted Platt calibrator parameters A and B via Maximum Likelihood."""
        s = np.asarray(scores, dtype=np.float64).ravel()
        y = np.asarray(y_true, dtype=np.float64).ravel()

        if len(s) == 0 or len(y) == 0:
            self.is_fitted = True
            return self

        # Pathological Guards
        unique_y = np.unique(y)
        if len(unique_y) == 1:
            if unique_y[0] <= 0.0:
                self.slope_a, self.intercept_b = 0.0, -15.0
            else:
                self.slope_a, self.intercept_b = 0.0, 15.0
            self.is_fitted = True
            return self

        var_s = float(np.var(s))
        if var_s <= 1e-12:
            # Constant scores: fit intercept only based on base rate
            mean_y = float(np.mean(y))
            mean_y = max(1e-6, min(mean_y, 1.0 - 1e-6))
            self.slope_a = 0.0
            self.intercept_b = float(np.log(mean_y / (1.0 - mean_y)))
            self.is_fitted = True
            return self

        def objective(params: list[float]) -> float:
            a, b = params[0], params[1]
            z = a * s + b
            p = _stable_sigmoid(z)
            p_safe = np.clip(p, 1e-15, 1.0 - 1e-15)
            return float(-np.sum(y * np.log(p_safe) + (1.0 - y) * np.log(1.0 - p_safe)))

        init_params = [1.0, 0.0]
        try:
            res = minimize(objective, init_params, method="L-BFGS-B")
            if res.success and np.isfinite(res.x[0]) and np.isfinite(res.x[1]):
                self.slope_a = float(res.x[0])
                self.intercept_b = float(res.x[1])
            else:
                self.slope_a = 1.0
                self.intercept_b = 0.0
        except Exception:
            self.slope_a = 1.0
            self.intercept_b = 0.0

        self.is_fitted = True
        return self

    def predict_proba(self, scores: Sequence[float] | np.ndarray) -> np.ndarray:
        """Predict calibrated probabilities in [0.0, 1.0]."""
        s = np.asarray(scores, dtype=np.float64)
        z = self.slope_a * s + self.intercept_b
        return _stable_sigmoid(z)


class IsotonicCalibrator:
    """Unweighted Isotonic Calibrator via pure NumPy Pool Adjacent Violators Algorithm (PAVA)."""

    def __init__(self) -> None:
        self.threshold_x: np.ndarray = np.array([])
        self.calibrated_y: np.ndarray = np.array([])
        self.is_fitted = False

    def fit(
        self,
        scores: Sequence[float] | np.ndarray,
        y_true: Sequence[float] | np.ndarray,
    ) -> IsotonicCalibrator:
        """Fit monotonic non-decreasing step function via unweighted PAVA."""
        s = np.asarray(scores, dtype=np.float64).ravel()
        y = np.asarray(y_true, dtype=np.float64).ravel()

        if len(s) == 0 or len(y) == 0:
            self.is_fitted = True
            return self

        # Sort by scores
        order = np.argsort(s)
        s_sorted = s[order]
        y_sorted = y[order]

        # PAVA implementation in pure NumPy
        n = len(y_sorted)
        val = np.copy(y_sorted)
        weight = np.ones(n, dtype=np.float64)

        i = 0
        while i < len(val) - 1:
            if val[i] > val[i + 1]:
                # Pool adjacent violators
                w_new = weight[i] + weight[i + 1]
                v_new = (val[i] * weight[i] + val[i + 1] * weight[i + 1]) / w_new
                val[i] = v_new
                weight[i] = w_new

                # Delete i+1
                val = np.delete(val, i + 1)
                weight = np.delete(weight, i + 1)
                s_sorted = np.delete(s_sorted, i + 1)

                # Step backward to resolve any created violations
                if i > 0:
                    i -= 1
            else:
                i += 1

        self.threshold_x = s_sorted
        self.calibrated_y = np.clip(val, 0.0, 1.0)
        self.is_fitted = True
        return self

    def predict_proba(self, scores: Sequence[float] | np.ndarray) -> np.ndarray:
        """Evaluate monotonic calibrated probabilities."""
        s = np.asarray(scores, dtype=np.float64)
        if len(self.threshold_x) == 0:
            return np.full_like(s, 0.5)

        # Monotonic piecewise-constant interpolation
        idx = np.searchsorted(self.threshold_x, s, side="right") - 1
        idx = np.clip(idx, 0, len(self.calibrated_y) - 1)
        return self.calibrated_y[idx]


def calibrate_exceedance_probabilities(
    shock_residuals: Sequence[float] | np.ndarray,
    threshold_u: float,
    method: Literal["platt", "isotonic"] = "platt",
) -> tuple[np.ndarray, PlattCalibrator | IsotonicCalibrator]:
    """Fit unweighted probability calibrator to forecast exceedance probability p_hat = Pr(R > u)."""
    r = np.asarray(shock_residuals, dtype=np.float64).ravel()
    y_true = (r > float(threshold_u)).astype(np.float64)

    if method == "isotonic":
        calibrator: PlattCalibrator | IsotonicCalibrator = IsotonicCalibrator().fit(r, y_true)
    else:
        calibrator = PlattCalibrator().fit(r, y_true)

    calibrated_probs = calibrator.predict_proba(r)
    return calibrated_probs, calibrator
