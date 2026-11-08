"""Wald's Sequential Probability Ratio Test (SPRT) Surveillance Gates.

Provides statistically optimal, minimal-sample surveillance gates for corridor risk escalation:
- H_0: Fairway risk remains at benign baseline (p_0).
- H_1: Fairway risk has surged into an active attack wave (p_1).
- Error boundaries (alpha, beta):
    A = ln(beta / (1 - alpha))  [Accept H_0 -> H0_NOT_REJECTED]
    B = ln((1 - beta) / alpha)  [Accept H_1 -> H1_ACCEPTED]
    Intermediate -> CONTINUE_SAMPLING

Pure domain math: ZERO I/O, ZERO PRINT, pure Python/math.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Optional, Sequence

from .specs import SPRTSpec

SPRTState = Literal["H0_NOT_REJECTED", "CONTINUE_SAMPLING", "H1_ACCEPTED"]


@dataclass(frozen=True)
class SPRTGateResult:
    """Immutable domain container for Wald's SPRT gate output."""

    cumulative_llr: float
    lower_bound_a: float
    upper_bound_b: float
    state: SPRTState
    sample_size: int
    breach_count: int
    p0: float
    p1: float
    alpha: float
    beta: float


def evaluate_sprt_surveillance_gate(
    breach_observations: Sequence[int | float | bool],
    p0: Optional[float] = None,
    p1: Optional[float] = None,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    spec: Optional[SPRTSpec] = None,
) -> SPRTGateResult:
    """Evaluate sequential probability ratio test over chronological breach observations.

    Parameters
    ----------
    breach_observations : Sequence[int | float | bool]
        Chronological sequence of binary corridor breach flags (1 for breach/spike, 0 otherwise).
    p0 : Optional[float]
        Baseline probability under H_0.
    p1 : Optional[float]
        Escalated probability under H_1.
    alpha : Optional[float]
        Type I false alarm error probability.
    beta : Optional[float]
        Type II missed detection error probability.
    spec : Optional[SPRTSpec]
        SPRT specification. Defaults to SPRTSpec().

    Returns
    -------
    SPRTGateResult
    """
    s_spec = spec or SPRTSpec()
    p0_val = s_spec.p0 if p0 is None else float(p0)
    p1_val = s_spec.p1 if p1 is None else float(p1)
    alpha_val = s_spec.alpha if alpha is None else float(alpha)
    beta_val = s_spec.beta if beta is None else float(beta)

    obs = [1 if bool(x) else 0 for x in breach_observations]
    n = len(obs)
    k = sum(obs)

    # Wald bounds
    a_bound = math.log(beta_val / (1.0 - alpha_val))
    b_bound = math.log((1.0 - beta_val) / alpha_val)

    if n == 0:
        return SPRTGateResult(
            cumulative_llr=0.0,
            lower_bound_a=a_bound,
            upper_bound_b=b_bound,
            state="H0_NOT_REJECTED",
            sample_size=0,
            breach_count=0,
            p0=p0_val,
            p1=p1_val,
            alpha=alpha_val,
            beta=beta_val,
        )

    # Increments:
    # y = 1 -> log(p1 / p0)
    # y = 0 -> log((1 - p1) / (1 - p0))
    log_ratio_1 = math.log(p1_val / p0_val)
    log_ratio_0 = math.log((1.0 - p1_val) / (1.0 - p0_val))

    llr = 0.0
    for y in obs:
        llr += log_ratio_1 if y == 1 else log_ratio_0

    if llr <= a_bound:
        state: SPRTState = "H0_NOT_REJECTED"
    elif llr >= b_bound:
        state = "H1_ACCEPTED"
    else:
        state = "CONTINUE_SAMPLING"

    return SPRTGateResult(
        cumulative_llr=float(llr),
        lower_bound_a=float(a_bound),
        upper_bound_b=float(b_bound),
        state=state,
        sample_size=n,
        breach_count=k,
        p0=p0_val,
        p1=p1_val,
        alpha=alpha_val,
        beta=beta_val,
    )


# Alias for backward-compatible naming
evaluate_sprt_gate = evaluate_sprt_surveillance_gate

__all__ = [
    "SPRTState",
    "SPRTGateResult",
    "evaluate_sprt_surveillance_gate",
    "evaluate_sprt_gate",
]
