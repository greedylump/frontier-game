"""A finite-horizon game with simultaneous fixed allocations and shared safety."""
from dataclasses import dataclass, asdict
import math
import numpy as np


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


@dataclass(frozen=True)
class FixedPolicy:
    """Fraction of one unit of effort devoted to capability every period."""
    allocation: float

    def __post_init__(self):
        if not math.isfinite(self.allocation) or not 0 <= self.allocation <= 1:
            raise ValueError("allocation must be in [0, 1]")


def simulate(config: Config, policy_a: FixedPolicy, policy_b: FixedPolicy,
             rng: np.random.Generator, *, trace: bool = False) -> dict:
    """Run one episode. Randomness belongs to the caller, never global state.

    A trace records post-transition states, including a fatal transition.
    A winner is paid only if the episode survives the entire horizon.
    """
    capability = np.zeros(2)
    safety = 0.0
    allocation = np.array([policy_a.allocation, policy_b.allocation])
    history = []
    catastrophe = False
    for step in range(1, config.horizon + 1):
        # Mean-one lognormal multipliers keep progress nonnegative.
        shock = rng.lognormal(-0.5 * config.noise**2, config.noise, size=2)
        capability += config.capability_rate * allocation * shock
        safety += config.safety_rate * float((1 - allocation).sum())
        gap = max(0.0, float(capability.max()) - safety)
        hazard = float(-np.expm1(-config.hazard_scale * gap))
        catastrophe = bool(rng.random() < hazard)
        if trace:
            history.append(dict(step=step, capability_a=float(capability[0]),
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
    if trace:
        result["history"] = history
    return result
