"""A finite-horizon game with simultaneous per-period allocations and shared safety."""
from dataclasses import dataclass, asdict
import math
from numbers import Real
from typing import Protocol
import numpy as np


# Instrumentation schema only; mathematical model IDs are unchanged.
OUTPUT_SCHEMA_VERSION = 2
DIAGNOSTIC_DEFINITIONS = {
    'mean_allocation_a': 'Sum of A allocations divided by executed periods.',
    'mean_allocation_b': 'Sum of B allocations divided by executed periods.',
    'allocation_zero_periods_a': 'Executed periods with A allocation exactly 0.',
    'allocation_zero_periods_b': 'Executed periods with B allocation exactly 0.',
    'allocation_one_periods_a': 'Executed periods with A allocation exactly 1.',
    'allocation_one_periods_b': 'Executed periods with B allocation exactly 1.',
    'max_post_gap': 'Maximum post-update shared safety gap over executed periods.',
    'cumulative_hazard_exposure': 'Sum of hazard_scale * post_gap over executed periods; neither a catastrophe count nor a probability.',
}


@dataclass(frozen=True)
class Config:
    horizon: int = 30
    capability_rate: float = 1.0
    safety_rate: float = 0.6
    noise: float = 0.25
    hazard_scale: float = 0.01
    first_mover_value: float = 10.0
    catastrophe_cost: float = 50.0

    def __post_init__(self):
        if type(self.horizon) is not int or self.horizon < 1:
            raise ValueError("horizon must be a positive integer")
        for name, value in asdict(self).items():
            if name != "horizon" and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class Observation:
    """Exact pre-transition values; period is 1-based, from 1 through horizon."""
    period: int
    horizon: int
    own_capability: float
    opponent_capability: float
    shared_safety: float


class Policy(Protocol):
    """Deterministic, memoryless decision rule; do not retain episode state.

    run_trials reuses policy instances. Built-in policies are immutable.
    """
    def choose_allocation(self, observation: Observation) -> float: ...


def make_observations(period: int, horizon: int, capability_a: float,
                      capability_b: float, safety: float) -> tuple[Observation, Observation]:
    """Build both player views before either policy is evaluated."""
    return (Observation(period, horizon, capability_a, capability_b, safety),
            Observation(period, horizon, capability_b, capability_a, safety))


def validate_allocation(value: float) -> float:
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("allocation must be a finite real number in [0, 1]")
    return float(value)


@dataclass(frozen=True)
class FixedPolicy:
    """Return the same capability allocation each period, ignoring observation."""
    allocation: float

    def __post_init__(self):
        validate_allocation(self.allocation)

    def choose_allocation(self, observation: Observation) -> float:
        return self.allocation


@dataclass(frozen=True)
class SafetyGapPolicy:
    """Identical configurations choose identical actions from the shared gap."""
    normal_allocation: float = 0.50
    cautious_allocation: float = 0.30
    gap_threshold: float = 0.0

    def __post_init__(self):
        validate_allocation(self.normal_allocation)
        validate_allocation(self.cautious_allocation)
        if (isinstance(self.gap_threshold, (bool, np.bool_))
                or not isinstance(self.gap_threshold, Real)
                or not math.isfinite(self.gap_threshold) or self.gap_threshold < 0):
            raise ValueError("gap_threshold must be finite and nonnegative")

    def choose_allocation(self, observation: Observation) -> float:
        gap = max(0.0, max(observation.own_capability, observation.opponent_capability)
                  - observation.shared_safety)
        return self.cautious_allocation if gap > self.gap_threshold else self.normal_allocation


@dataclass(frozen=True)
class GraduatedPolicy:
    """Prescribed, memoryless response to relative capability and the shared gap.

    Defaults are illustrative parameters, not optimized coefficients.
    """
    base_allocation: float = 0.60
    deficit_response: float = 0.10
    safety_response: float = 0.20

    def __post_init__(self):
        validate_allocation(self.base_allocation)
        for name in ('deficit_response', 'safety_response'):
            value = getattr(self, name)
            if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f'{name} must be finite and nonnegative')

    def choose_allocation(self, observation: Observation) -> float:
        deficit = observation.opponent_capability - observation.own_capability
        gap = max(0.0, max(observation.own_capability, observation.opponent_capability)
                  - observation.shared_safety)
        allocation = (self.base_allocation + self.deficit_response * deficit
                      - self.safety_response * gap)
        return float(np.clip(allocation, 0.0, 1.0))


@dataclass(frozen=True)
class ThresholdInterventionPolicy:
    """Memoryless intervention rule: protect shared safety by forcing zero when gap exceeds threshold.

    Otherwise it falls back to a graduated-like normal branch where the same
    deficit term is retained, but the safety-gap response is intentionally not
    applied. The proposal is designed for a minimal pluggable experiment.
    """
    base_allocation: float = 0.60
    deficit_response: float = 0.10
    threshold: float = 0.05

    def __post_init__(self):
        validate_allocation(self.base_allocation)
        if (isinstance(self.deficit_response, (bool, np.bool_)) or not isinstance(self.deficit_response, Real)
                or not math.isfinite(self.deficit_response) or self.deficit_response < 0):
            raise ValueError('deficit_response must be finite and nonnegative')
        if (isinstance(self.threshold, (bool, np.bool_)) or not isinstance(self.threshold, Real)
                or not math.isfinite(self.threshold) or self.threshold < 0):
            raise ValueError('threshold must be finite and nonnegative')

    def choose_allocation(self, observation: Observation) -> float:
        gap = max(0.0, max(observation.own_capability, observation.opponent_capability)
                  - observation.shared_safety)
        if gap > self.threshold:
            return 0.0
        deficit = observation.opponent_capability - observation.own_capability
        allocation = self.base_allocation + self.deficit_response * deficit
        return float(np.clip(allocation, 0.0, 1.0))


def simulate(config: Config, policy_a: Policy, policy_b: Policy,
             rng: np.random.Generator, *, trace: bool = False) -> dict:
    """Run one episode. Randomness belongs to the caller, never global state.

    A trace records pre-transition decisions and post-transition outcomes.
    Legacy unprefixed state fields remain aliases for post-transition values.
    A winner is paid only if the episode survives the entire horizon.
    """
    capability = np.zeros(2)
    safety = 0.0
    history = []
    allocation_sum = np.zeros(2)
    allocation_zero_periods = np.zeros(2, dtype=int)
    allocation_one_periods = np.zeros(2, dtype=int)
    max_post_gap = 0.0
    cumulative_hazard_exposure = 0.0
    catastrophe = False
    for step in range(1, config.horizon + 1):
        observations = make_observations(step, config.horizon, float(capability[0]),
                                         float(capability[1]), safety)
        # Both observations already exist; neither decision sees the other's action.
        chosen_a = policy_a.choose_allocation(observations[0])
        chosen_b = policy_b.choose_allocation(observations[1])
        allocation = np.array([validate_allocation(chosen_a), validate_allocation(chosen_b)])
        # Validation precedes state changes and all random draws.
        # Mean-one lognormal multipliers keep progress nonnegative.
        shock = rng.lognormal(-0.5 * config.noise**2, config.noise, size=2)
        capability += config.capability_rate * allocation * shock
        safety += config.safety_rate * float((1 - allocation).sum())
        gap = max(0.0, float(capability.max()) - safety)
        hazard = float(-np.expm1(-config.hazard_scale * gap))
        catastrophe = bool(rng.random() < hazard)
        # Observe the executed transition, including a terminal catastrophe period.
        allocation_sum += allocation
        allocation_zero_periods += allocation == 0
        allocation_one_periods += allocation == 1
        max_post_gap = max(max_post_gap, gap)
        cumulative_hazard_exposure += config.hazard_scale * gap
        if trace:
            history.append(dict(step=step, horizon=config.horizon,
                                pre_capability_a=observations[0].own_capability,
                                pre_capability_b=observations[1].own_capability,
                                pre_safety=observations[0].shared_safety,
                                pre_gap=max(0.0, max(observations[0].own_capability,
                                                    observations[1].own_capability)
                                            - observations[0].shared_safety),
                                allocation_a=float(allocation[0]), allocation_b=float(allocation[1]),
                                post_capability_a=float(capability[0]), post_capability_b=float(capability[1]),
                                post_safety=safety, post_gap=gap, post_hazard=hazard,
                                post_catastrophe=catastrophe, capability_a=float(capability[0]),
                                capability_b=float(capability[1]), safety=safety,
                                gap=gap, hazard=hazard, catastrophe=catastrophe))
        if catastrophe:
            break
    if catastrophe:
        payoff = np.full(2, -config.catastrophe_cost)
    elif capability[0] == capability[1]:
        payoff = np.full(2, config.first_mover_value / 2)
    else:
        payoff = np.zeros(2)
        payoff[int(np.argmax(capability))] = config.first_mover_value
    result = dict(steps=step, catastrophe=catastrophe,
                  capability_a=float(capability[0]), capability_b=float(capability[1]),
                  safety=safety, payoff_a=float(payoff[0]), payoff_b=float(payoff[1]))
    result.update(mean_allocation_a=float(allocation_sum[0] / step),
                  mean_allocation_b=float(allocation_sum[1] / step),
                  allocation_zero_periods_a=int(allocation_zero_periods[0]),
                  allocation_zero_periods_b=int(allocation_zero_periods[1]),
                  allocation_one_periods_a=int(allocation_one_periods[0]),
                  allocation_one_periods_b=int(allocation_one_periods[1]),
                  max_post_gap=max_post_gap,
                  cumulative_hazard_exposure=cumulative_hazard_exposure)
    if trace:
        result["history"] = history
    return result
