"""Uniform strategy lifecycle: backtest -> paper -> live, each stage gated
and switchable independently. A strategy is never auto-promoted past paper —
`promote_to_live` requires an explicit human approval, recorded on the spot.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StrategyStage:
    enabled_for_backtest: bool = True
    enabled_for_paper: bool = False
    enabled_for_live: bool = False
    validation: Optional[object] = None  # agent.backtest.metrics.ValidationResult
    notes: str = ""


@dataclass
class StrategyAdapter:
    """Wraps one strategy's own entry/exit/state logic behind a uniform interface.

    `build_legs_fn(S, T, sigma, **kwargs)` must return an object exposing `.legs`
    (option legs), `.net_credit` and either `.max_loss_per_contract` or `.max_loss` —
    i.e. anything shaped like agent.strategies.StrategyPlan or
    agent.backtest.iron_condor.IronCondorLegs.
    """
    name: str
    build_legs_fn: callable
    stage: StrategyStage = field(default_factory=StrategyStage)

    def promote_to_paper(self, validation) -> bool:
        """Gate: only reachable if the backtest validation gate passed."""
        self.stage.validation = validation
        self.stage.enabled_for_paper = bool(validation.passed)
        return self.stage.enabled_for_paper

    def promote_to_live(self, approved_by: str, reason: str) -> None:
        if not self.stage.enabled_for_paper:
            raise RuntimeError(f"{self.name} has not cleared the paper stage; cannot go live.")
        self.stage.enabled_for_live = True
        self.stage.notes += f"\n[live approved by {approved_by}]: {reason}"

    def demote(self, reason: str) -> None:
        """Pull a strategy back out of paper/live — e.g. after a live drawdown breach."""
        self.stage.enabled_for_paper = False
        self.stage.enabled_for_live = False
        self.stage.notes += f"\n[demoted]: {reason}"


class StrategyRegistry:
    def __init__(self):
        self._adapters: dict = {}

    def register(self, adapter: StrategyAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> StrategyAdapter:
        return self._adapters[name]

    def all(self) -> list:
        return list(self._adapters.values())

    def enabled_for_paper(self) -> list:
        return [a for a in self._adapters.values() if a.stage.enabled_for_paper]

    def enabled_for_live(self) -> list:
        return [a for a in self._adapters.values() if a.stage.enabled_for_live]
