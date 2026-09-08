"""Frontier Game: explicit assumptions, small experiments."""
from .model import Config, FixedPolicy, simulate
from .monte_carlo import run_trials, summarize

__all__ = ["Config", "FixedPolicy", "simulate", "run_trials", "summarize"]
