"""Transaction cost / friction model.

Applied per leg, round-trip (entry + exit) — not a single blanket haircut on
the whole trade — so a 4-leg iron condor pays 4x the friction a 1-leg cash
secured put does, which is realistic and keeps multi-leg strategies from
looking artificially cheap in the backtest.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    half_spread_bps: float = 50.0   # bid/ask half-spread, in basis points of the option's price
    flat_hurdle_pct: float = 0.0    # extra flat % of price per fill, e.g. commission/slippage buffer

    def _per_fill_cost(self, price: float) -> float:
        return price * (self.half_spread_bps / 10_000.0) + price * self.flat_hurdle_pct

    def round_trip_cost(self, entry_price: float, exit_price: float) -> float:
        """Total dollars of friction for one leg's entry + exit, per contract (x100 multiplier)."""
        return (self._per_fill_cost(entry_price) + self._per_fill_cost(exit_price)) * 100


# Defaults: a 50bp half-spread plus a 10bp flat hurdle per fill is a conservative
# but not punitive assumption for liquid single-name/ETF options.
DEFAULT_COST_MODEL = CostModel(half_spread_bps=50.0, flat_hurdle_pct=0.001)
