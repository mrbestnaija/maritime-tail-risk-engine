"""Wald's Sequential Probability Ratio Test (SPRT) Surveillance Gates.

Provides statistically optimal, minimal-sample surveillance gates for corridor risk escalation:
- H_0: Fairway risk remains at benign baseline (p_0 = 0.05).
- H_1: Fairway risk has surged into an active attack wave (p_1 = 0.20).
- Error boundaries (alpha = 0.05, beta = 0.10):
    A = ln(beta / (1 - alpha))  [Accept H_0 -> GREEN_BASELINE]
    B = ln((1 - beta) / alpha)  [Accept H_1 -> RED_ESCALATION_BREACH]
    Intermediate -> AMBER_CORRIDOR_WATCH

Pure domain math: ZERO I/O, ZERO PRINT, pure Python/math.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Sequence

SPRTState = Literal["GREEN_BASELINE", "AMBER_CORRIDOR_WATCH", "RED_ESCALATION_BREACH"]


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
    p0: float = 0.05,
    p1: float = 0.20,
    alpha: float = 0.05,
    beta: float = 0.10,
) -> SPRTGateResult:
    """Evaluate sequential probability ratio test over chronological breach observations.

    Parameters
    ----------
    breach_observations : Sequence[int | float | bool]
        Chronological sequence of binary corridor breach flags (1 for breach/spike, 0 otherwise).
    p0 : float
        Baseline probability under H_0 (default: 0.05).
    p1 : float
        Escalated probability under H_1 (default: 0.20).
    alpha : float
        Type I false alarm error probability (default: 0.05).
    beta : float
        Type II missed detection error probability (default: 0.10).

    Returns
    -------
    SPRTGateResult
    """
    obs = [1 if bool(x) else 0 for x in breach_observations]
    n = len(obs)
    k = sum(obs)

    # Wald bounds
    a_bound = math.log(beta / (1.0 - alpha))
    b_bound = math.log((1.0 - beta) / alpha)

    if n == 0:
        return SPRTGateResult(
            cumulative_llr=0.0,
            lower_bound_a=a_bound,
            upper_bound_b=b_bound,
            state="GREEN_BASELINE",
            sample_size=0,
            breach_count=0,
            p0=p0,
            p1=p1,
            alpha=alpha,
            beta=beta,
        )

    # Increments:
    # y = 1 -> log(p1 / p0)
    # y = 0 -> log((1 - p1) / (1 - p0))
    log_ratio_1 = math.log(p1 / p0)
    log_ratio_0 = math.log((1.0 - p1) / (1.0 - p0))

    llr = 0.0
    for y in obs:
        llr += log_ratio_1 if y == 1 else log_ratio_0

    if llr <= a_bound:
        state: SPRTState = "GREEN_BASELINE"
    elif llr >= b_bound:
        state = "RED_ESCALATION_BREACH"
    else:
        state = "AMBER_CORRIDOR_WATCH"

    return SPRTGateResult(
        cumulative_llr=llr,
        lower_bound_a=a_bound,
        upper_bound_b=b_bound,
        state=state,
        sample_size=n,
        breach_count=k,
        p0=p0,
        p1=p1,
        alpha=alpha,
        beta=beta,
    )
