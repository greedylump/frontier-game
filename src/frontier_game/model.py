"""A finite-horizon game with simultaneous per-period allocations and shared safety."""
from dataclasses import dataclass, asdict, fields
from collections.abc import Mapping
import math
from numbers import Real
from typing import Protocol
import numpy as np


# Output schema is separate from scientific model classification.
OUTPUT_SCHEMA_VERSION = 3
DIAGNOSTIC_DEFINITIONS = {
    'mean_allocation_a': 'Sum of A allocations divided by executed periods.',
    'mean_allocation_b': 'Sum of B allocations divided by executed periods.',
    'allocation_zero_periods_a': 'Executed periods with A allocation exactly 0.',
    'allocation_zero_periods_b': 'Executed periods with B allocation exactly 0.',
    'allocation_one_periods_a': 'Executed periods with A allocation exactly 1.',
    'allocation_one_periods_b': 'Executed periods with B allocation exactly 1.',
    'max_post_gap': 'Maximum post-update shared safety gap over executed periods.',
    'cumulative_hazard_exposure': 'Sum of hazard_scale * post_gap over executed periods; neither a catastrophe count nor a probability.',
    'pending_capability_a': 'Realized unfinished capability produced by lab A, after current investment and arrivals, before catastrophe; episode value is from the last executed period. No current risk, protection, or terminal prize credit.',
    'pending_capability_b': 'Realized unfinished capability produced by lab B, after current investment and arrivals, before catastrophe; episode value is from the last executed period. No current risk, protection, or terminal prize credit.',
    'pending_safety_a': 'Realized unfinished safety produced by lab A, after current investment and arrivals, before catastrophe; episode value is from the last executed period. No current risk, protection, or terminal prize credit.',
    'pending_safety_b': 'Realized unfinished safety produced by lab B, after current investment and arrivals, before catastrophe; episode value is from the last executed period. No current risk, protection, or terminal prize credit.',
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
    capability_delay_a: int = 0
    safety_delay_a: int = 0
    capability_delay_b: int = 0
    safety_delay_b: int = 0

    def __post_init__(self):
        if type(self.horizon) is not int or self.horizon < 1:
            raise ValueError("horizon must be a positive integer")
        for name in ('capability_delay_a','safety_delay_a','capability_delay_b','safety_delay_b'):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        for name, value in asdict(self).items():
            if name in ('capability_delay_a','safety_delay_a','capability_delay_b','safety_delay_b'):
                continue
            if name != "horizon" and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class PendingArrival:
    """Realized production scheduled for an absolute, 1-based arrival period."""
    amount: float
    arrival_period: int

    def __post_init__(self):
        if isinstance(self.amount, (bool, np.bool_)) or not isinstance(self.amount, Real):
            raise TypeError('arrival amount must be a real number')
        if type(self.arrival_period) is not int or self.arrival_period < 1:
            raise ValueError('arrival_period must be a positive integer')
        # Copy the realized engine value without adding numerical transition rules.
        object.__setattr__(self, 'amount', float(self.amount))


@dataclass(frozen=True, slots=True)
class Observation:
    """Pre-decision snapshot; omitted schedules/delays mean unavailable, not zero.

    Empty tuples mean known empty schedules. The simulator supplies every field.
    Five-argument construction remains supported for stock-only policy callers.
    """
    period: int
    horizon: int
    own_capability: float
    opponent_capability: float
    shared_safety: float
    own_pending_capability: tuple[PendingArrival, ...] | None = None
    opponent_pending_capability: tuple[PendingArrival, ...] | None = None
    own_pending_safety: tuple[PendingArrival, ...] | None = None
    opponent_pending_safety: tuple[PendingArrival, ...] | None = None
    own_capability_delay: int | None = None
    opponent_capability_delay: int | None = None
    own_safety_delay: int | None = None
    opponent_safety_delay: int | None = None

    def __post_init__(self):
        # Also isolate schedules supplied manually as lists; never retain a container
        # that its caller can mutate. No projection or horizon filtering occurs.
        for name in ('own_pending_capability', 'opponent_pending_capability',
                     'own_pending_safety', 'opponent_pending_safety'):
            schedule = getattr(self, name)
            if schedule is not None:
                schedule = tuple(schedule)
                if any(not isinstance(item, PendingArrival) for item in schedule):
                    raise TypeError(f'{name} must contain PendingArrival records')
                object.__setattr__(self, name, tuple(sorted(schedule, key=lambda item: item.arrival_period)))
        for name in ('own_capability_delay', 'opponent_capability_delay',
                     'own_safety_delay', 'opponent_safety_delay'):
            delay = getattr(self, name)
            if delay is not None and (type(delay) is not int or delay < 0):
                raise ValueError(f'{name} must be a nonnegative integer or None')


class Policy(Protocol):
    """Deterministic, memoryless decision rule; do not retain episode state.

    run_trials reuses policy instances. Built-in policies are immutable.
    """
    def choose_allocation(self, observation: Observation) -> float: ...


def make_observations(period: int, horizon: int, capability_a: float,
                      capability_b: float, safety: float, *,
                      pending_capability: tuple[Mapping[int, float], Mapping[int, float]] | None = None,
                      pending_safety: tuple[Mapping[int, float], Mapping[int, float]] | None = None,
                      config: Config | None = None) -> tuple[Observation, Observation]:
    """Copy true engine state into both player views before either decision.

    Current perfect information includes due-now and beyond-horizon work. Omitted
    inputs remain unavailable for legacy callers. Simulation always supplies them.
    Future reporting rules belong here, separately from physical transitions;
    stochastic observations should use a separate RNG stream.
    """
    def snapshot(queues, lab):
        if queues is None:
            return None
        return tuple(PendingArrival(float(amount), arrival)
                     for arrival, amount in sorted(queues[lab].items()))

    def view(lab):
        other = 1 - lab
        own, opponent = ('a', 'b') if lab == 0 else ('b', 'a')
        def delay(side, kind):
            return None if config is None else getattr(config, f'{kind}_delay_{side}')
        return Observation(period, horizon, (capability_a, capability_b)[lab],
                           (capability_a, capability_b)[other], safety,
                           own_pending_capability=snapshot(pending_capability, lab),
                           opponent_pending_capability=snapshot(pending_capability, other),
                           own_pending_safety=snapshot(pending_safety, lab),
                           opponent_pending_safety=snapshot(pending_safety, other),
                           own_capability_delay=delay(own, 'capability'),
                           opponent_capability_delay=delay(opponent, 'capability'),
                           own_safety_delay=delay(own, 'safety'),
                           opponent_safety_delay=delay(opponent, 'safety'))
    return view(0), view(1)


def observation_metadata() -> dict:
    """Description shared by runners; no schedules are serialized into results."""
    return dict(model_id='exact-pending-pre-decision-v1', exact=True, delay_periods=0,
                fields=[field.name for field in fields(Observation)],
                period_indexing='1 through horizon, inclusive', simultaneous=True,
                stocks_at='end of previous completed period', pending_work_visible=True,
                configured_delays_visible=True,
                schedule=dict(record_fields=['amount', 'arrival_period'],
                    ordering='absolute arrival period ascending',
                    timing='Before both decisions and current investment/arrivals; due-now work is pending.',
                    amounts='Exact realized production from earlier investments; safety attributed to producing lab.',
                    beyond_horizon_visible=True, empty='Known no pending work',
                    unavailable=None, simulator_information='All schedules and configured delays are known.'),
                current_opponent_action_visible=False, current_investment_visible=False,
                future_shocks_visible=False, policy_internals_visible=False,
                mutable_queues_visible=False, rng_state_visible=False,
                fixed_policies_ignore_observations=True,
                legacy_policies_ignore_pending_and_delays=True,
                diagnostics='Output pending totals are post-update diagnostics, not pre-decision schedules; schedules are not serialized.')


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
class PendingAwareGraduatedPolicy(GraduatedPolicy):
    """Prescribed gap measure using independent inclusive pending-work windows.

    None ignores a category; 0 includes due-now work. Cutoffs are not capped at
    the horizon. This measure can offset early capability with later safety;
    it is not a forecast of physical hazard or a maximum over future gaps.
    """
    capability_lookahead: int | None = None
    safety_lookahead: int | None = None

    def __post_init__(self):
        super().__post_init__()
        for name in ('capability_lookahead', 'safety_lookahead'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f'{name} must be a nonnegative integer or None')

    def choose_allocation(self, observation: Observation) -> float:
        if self.capability_lookahead is None and self.safety_lookahead is None:
            return super().choose_allocation(observation)

        def selected(name, lookahead):
            if lookahead is None:
                return 0.0
            schedule = getattr(observation, name)
            if schedule is None:
                raise ValueError(f'{name} is unavailable but its lookahead is enabled')
            return sum((item.amount for item in schedule
                        if observation.period <= item.arrival_period <= observation.period + lookahead), 0.0)

        own = selected('own_pending_capability', self.capability_lookahead)
        opponent = selected('opponent_pending_capability', self.capability_lookahead)
        safety = (selected('own_pending_safety', self.safety_lookahead)
                  + selected('opponent_pending_safety', self.safety_lookahead))
        anticipated_gap = max(0.0, max(observation.own_capability + own,
                                     observation.opponent_capability + opponent)
                              - (observation.shared_safety + safety))
        deficit = observation.opponent_capability - observation.own_capability
        allocation = (self.base_allocation + self.deficit_response * deficit
                      - self.safety_response * anticipated_gap)
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

    Work invested in t arrives during update t+d, after decisions and before risk.
    Pending queues exist for every episode, including those with zero delays.
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
    steps = 0

    # Each lab owns a map from arrival period to realized production amount.
    # Entries beyond the horizon remain unfinished at termination.
    pending_capability = [{}, {}]
    pending_safety = [{}, {}]

    def schedule_work(step, allocation):
        nonlocal safety
        shock = rng.lognormal(-0.5 * config.noise**2, config.noise, size=2)
        produced = config.capability_rate * allocation * shock
        for lab, delay in enumerate((config.capability_delay_a, config.capability_delay_b)):
            if delay:
                due = step + delay
                pending_capability[lab][due] = pending_capability[lab].get(due, 0.0) + float(produced[lab])
                produced[lab] = 0.0
        capability[:] += produced
        # Preserve the original shared-safety arithmetic when both are immediate.
        if config.safety_delay_a == config.safety_delay_b == 0:
            safety += config.safety_rate * float((1 - allocation).sum())
        else:
            for lab, delay in enumerate((config.safety_delay_a, config.safety_delay_b)):
                amount = config.safety_rate * float(1 - allocation[lab])
                if delay:
                    due = step + delay
                    pending_safety[lab][due] = pending_safety[lab].get(due, 0.0) + amount
                else:
                    safety += amount
        # Always drain due work, independently of delays for new investments.
        for lab in (0, 1):
            if step in pending_capability[lab]:
                capability[lab] += pending_capability[lab].pop(step)
            if step in pending_safety[lab]:
                safety += pending_safety[lab].pop(step)

    for step in range(1, config.horizon + 1):
        observations = make_observations(step, config.horizon,
                                          float(capability[0]), float(capability[1]), safety,
                                          pending_capability=tuple(pending_capability),
                                          pending_safety=tuple(pending_safety), config=config)
        chosen_a = policy_a.choose_allocation(observations[0])
        chosen_b = policy_b.choose_allocation(observations[1])
        allocation = np.array([validate_allocation(chosen_a), validate_allocation(chosen_b)])

        schedule_work(step, allocation)
        gap = max(0.0, float(capability.max()) - safety)
        hazard = float(-np.expm1(-config.hazard_scale * gap))
        catastrophe = bool(rng.random() < hazard)

        allocation_sum += allocation
        allocation_zero_periods += allocation == 0
        allocation_one_periods += allocation == 1
        max_post_gap = max(max_post_gap, gap)
        cumulative_hazard_exposure += config.hazard_scale * gap
        steps = step

        pending_capability_a = sum(pending_capability[0].values(), 0.0)
        pending_capability_b = sum(pending_capability[1].values(), 0.0)
        pending_safety_a = sum(pending_safety[0].values(), 0.0)
        pending_safety_b = sum(pending_safety[1].values(), 0.0)

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
                                gap=gap, hazard=hazard, catastrophe=catastrophe,
                                pending_capability_a=pending_capability_a,
                                pending_capability_b=pending_capability_b,
                                pending_safety_a=pending_safety_a,
                                pending_safety_b=pending_safety_b))
        if catastrophe:
            break

    if catastrophe:
        payoff = np.full(2, -config.catastrophe_cost)
    elif capability[0] == capability[1]:
        payoff = np.full(2, config.first_mover_value / 2)
    else:
        payoff = np.zeros(2)
        payoff[int(np.argmax(capability))] = config.first_mover_value

    result = dict(steps=steps, catastrophe=catastrophe,
                  capability_a=float(capability[0]), capability_b=float(capability[1]),
                  safety=safety, payoff_a=float(payoff[0]), payoff_b=float(payoff[1]))
    result.update(mean_allocation_a=float(allocation_sum[0] / steps),
                  mean_allocation_b=float(allocation_sum[1] / steps),
                  allocation_zero_periods_a=int(allocation_zero_periods[0]),
                  allocation_zero_periods_b=int(allocation_zero_periods[1]),
                  allocation_one_periods_a=int(allocation_one_periods[0]),
                  allocation_one_periods_b=int(allocation_one_periods[1]),
                  max_post_gap=max_post_gap,
                  cumulative_hazard_exposure=cumulative_hazard_exposure,
                  pending_capability_a=sum(pending_capability[0].values(), 0.0),
                  pending_capability_b=sum(pending_capability[1].values(), 0.0),
                  pending_safety_a=sum(pending_safety[0].values(), 0.0),
                  pending_safety_b=sum(pending_safety[1].values(), 0.0))
    if trace:
        result['history'] = history
    return result
