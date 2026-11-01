"""Multivariate Singular Spectrum Analysis (MSSA) Decomposer.

Decomposes an M-channel multivariate time series into:
1. Secular drift trend (T_t)
2. Seasonal / sea-state harmonics (S_t)
3. Structural shock residual (R_t)

Enforces:
- Hard Mathematical Invariant: ||Y - (T + S + R)||_F < 1e-9
- Explained variance ratios <= 1.0
- Avoided seasonal false alarm OPEX savings ($ USD)
- Pure domain math: ZERO I/O, ZERO PRINT, pure NumPy/SciPy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
import numpy as np

from .specs import MSSASpec, VesselProfileSpec


@dataclass(frozen=True)
class MSSADecompositionResult:
    """Immutable domain container for MSSA decomposition results."""

    trend: np.ndarray
    seasonal: np.ndarray
    residual: np.ndarray
    singular_values: np.ndarray
    explained_variance_ratios: np.ndarray
    reconstruction_error_frobenius: float
    avoided_seasonal_false_alarm_days: int
    escort_opex_savings_usd: float
    daily_escort_cost_usd: float


def hankel_diagonal_averaging(
    trajectory_block: np.ndarray, T: int, L: int, M: int
) -> np.ndarray:
    """Reconstruct an (T, M) time series matrix via diagonal averaging (Hankelization).
    
    trajectory_block has shape (M * L, K), where K = T - L + 1.
    """
    K = T - L + 1
    reconstructed = np.zeros((T, M), dtype=np.float64)

    # Precompute anti-diagonal hit counts
    counts = np.zeros(T, dtype=np.float64)
    for i in range(L):
        for j in range(K):
            counts[i + j] += 1.0

    for m in range(M):
        block = trajectory_block[m * L : (m + 1) * L, :]
        diag_sums = np.zeros(T, dtype=np.float64)
        for i in range(L):
            for j in range(K):
                diag_sums[i + j] += block[i, j]
        reconstructed[:, m] = diag_sums / counts

    return reconstructed


def decompose_mssa(
    series_matrix: np.ndarray,
    window_length: Optional[int] = None,
    trend_components: Optional[Sequence[int]] = None,
    seasonal_components: Optional[Sequence[int]] = None,
    risk_threshold: Optional[float] = None,
    benign_residual_threshold: Optional[float] = None,
    daily_escort_cost_usd: Optional[float] = None,
    spec: Optional[MSSASpec] = None,
    vessel_spec: Optional[VesselProfileSpec] = None,
) -> MSSADecompositionResult:
    """Perform Multivariate Singular Spectrum Analysis (MSSA) decomposition.

    Parameters
    ----------
    series_matrix : np.ndarray
        Multivariate series of shape (T, M).
        Channel 0: Incident Severity
        Channel 1: Significant Wave Height (Hs)
        Channel 2: Sentinel-1 Dark Vessel Ratio
        Channel 3: Anchorage Waiting Hours
    window_length : Optional[int]
        Window length L satisfying 2 <= L <= floor(T / 2).
    trend_components : Optional[Sequence[int]]
        Singular triplet indices assigned to secular trend.
    seasonal_components : Optional[Sequence[int]]
        Singular triplet indices assigned to seasonal harmonics.
    risk_threshold : Optional[float]
        Threshold above which raw incident severity is flagged as high-risk.
    benign_residual_threshold : Optional[float]
        Upper bound for structural residual to be considered benign.
    daily_escort_cost_usd : Optional[float]
        Commercial daily private maritime escort vessel cost ($ USD).
    spec : Optional[MSSASpec]
        MSSA hyperparameter specification. Defaults to MSSASpec().
    vessel_spec : Optional[VesselProfileSpec]
        Vessel profile specification. Defaults to VesselProfileSpec().

    Returns
    -------
    MSSADecompositionResult
    """
    m_spec = spec or MSSASpec()
    v_spec = vessel_spec or VesselProfileSpec()

    risk_thresh = m_spec.risk_threshold if risk_threshold is None else float(risk_threshold)
    benign_thresh = (
        m_spec.benign_residual_threshold
        if benign_residual_threshold is None
        else float(benign_residual_threshold)
    )
    escort_cost = (
        v_spec.daily_escort_cost_usd
        if daily_escort_cost_usd is None
        else float(daily_escort_cost_usd)
    )

    Y = np.asarray(series_matrix, dtype=np.float64)
    if Y.ndim == 1:
        Y = Y[:, np.newaxis]

    T, M = Y.shape
    if T < 4:
        raise ValueError(f"Series length T={T} must be >= 4 for MSSA decomposition")

    # Select and validate window length L
    max_L = T // 2
    target_l = window_length if window_length is not None else m_spec.window_length
    if target_l is None:
        divisor = m_spec.window_length_divisor
        L = max(2, min(T // divisor, max_L))
    else:
        L = int(target_l)

    if L < 2 or L > max_L:
        raise ValueError(
            f"Window length L={L} violates mathematical bounds 2 <= L <= floor(T/2)={max_L}"
        )

    K = T - L + 1

    # 1. Construct block-trajectory (Hankel) matrix X in R^(ML x K)
    X = np.zeros((M * L, K), dtype=np.float64)
    for m in range(M):
        for i in range(L):
            X[m * L + i, :] = Y[i : i + K, m]

    # 2. Singular Value Decomposition (SVD): X = U * Sigma * V^T
    U, Sigma, Vt = np.linalg.svd(X, full_matrices=False)
    D = len(Sigma)

    total_var = float(np.sum(Sigma**2))
    if total_var > 0:
        evr = np.clip(Sigma**2 / total_var, 0.0, 1.0)
    else:
        evr = np.zeros(D, dtype=np.float64)

    # Invariant: individual EVR and cumulative EVR must never exceed 1.0
    evr = np.minimum(evr, 1.0)

    # 3. Component Grouping
    effective_trend_comps = m_spec.trend_components if trend_components is None else trend_components
    trend_idx = [i for i in effective_trend_comps if 0 <= i < D]

    effective_seasonal_comps = (
        m_spec.seasonal_components if seasonal_components is None else seasonal_components
    )
    seasonal_idx = [i for i in effective_seasonal_comps if 0 <= i < D and i not in trend_idx]

    used_idx = set(trend_idx) | set(seasonal_idx)
    residual_idx = [i for i in range(D) if i not in used_idx]

    # 4. Reconstruction via Diagonal Averaging (Hankelization)
    def reconstruct_group(indices: Sequence[int]) -> np.ndarray:
        if not indices:
            return np.zeros((T, M), dtype=np.float64)
        X_group = np.zeros_like(X)
        for i in indices:
            X_group += Sigma[i] * np.outer(U[:, i], Vt[i, :])
        return hankel_diagonal_averaging(X_group, T, L, M)

    trend = reconstruct_group(trend_idx)
    seasonal = reconstruct_group(seasonal_idx)
    residual = reconstruct_group(residual_idx)

    # 5. Hard Mathematical Invariant: ||Y - (T + S + R)||_F < 1e-9
    reconstructed_total = trend + seasonal + residual
    frobenius_error = float(np.linalg.norm(Y - reconstructed_total, ord="fro"))
    assert frobenius_error < 1e-9, (
        f"MSSA Additive Reconstruction Invariant Violated: "
        f"||Y - (T + S + R)||_F = {frobenius_error:.2e} >= 1e-9"
    )

    # 6. Commercial OPEX Metrics: Avoided seasonal false alarms on Channel 0
    raw_severity = Y[:, 0]
    residual_severity = residual[:, 0]

    false_alarm_mask = (raw_severity >= risk_thresh) & (
        residual_severity <= benign_thresh
    )
    avoided_days = int(np.sum(false_alarm_mask))
    escort_savings = float(avoided_days * escort_cost)

    return MSSADecompositionResult(
        trend=trend,
        seasonal=seasonal,
        residual=residual,
        singular_values=Sigma,
        explained_variance_ratios=evr,
        reconstruction_error_frobenius=frobenius_error,
        avoided_seasonal_false_alarm_days=avoided_days,
        escort_opex_savings_usd=escort_savings,
        daily_escort_cost_usd=float(escort_cost),
    )


__all__ = [
    "MSSADecompositionResult",
    "hankel_diagonal_averaging",
    "decompose_mssa",
]
