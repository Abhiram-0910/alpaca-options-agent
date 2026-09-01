"""Average True Range, used to fix a stop-loss distance and position size
*before* any strategy backtest runs — never chosen or tuned after looking at
which stop made the equity curve look best. `derive_risk_parameters` is
meant to be called once per symbol on measured historical volatility, and
that same value is then held fixed across every strategy/window tested
against that symbol.
"""
from dataclasses import dataclass
from typing import NamedTuple


class Bar(NamedTuple):
    high: float
    low: float
    close: float


def true_range(bar: Bar, prev_close: float) -> float:
    return max(
        bar.high - bar.low,
        abs(bar.high - prev_close),
        abs(bar.low - prev_close),
    )


def atr_series(bars: list, window: int = 14) -> list:
    """Rolling simple-moving-average ATR, one value per bar (None where undefined)."""
    if len(bars) < 2:
        return [None] * len(bars)
    trs = [None] + [true_range(bars[i], bars[i - 1].close) for i in range(1, len(bars))]
    out = [None] * len(bars)
    for i in range(len(bars)):
        window_trs = [t for t in trs[max(1, i - window + 1): i + 1] if t is not None]
        out[i] = sum(window_trs) / len(window_trs) if window_trs else None
    return out


def atr(bars: list, window: int = 14) -> float:
    """ATR as of the most recent bar in `bars`."""
    series = atr_series(bars, window)
    return series[-1] if series and series[-1] is not None else 0.0


@dataclass(frozen=True)
class RiskParameters:
    atr_value: float
    stop_loss_atr_multiple: float
    stop_loss_price_move: float   # underlying $ move that triggers a stop-out
    max_contracts_by_sizing: int


def derive_risk_parameters(bars: list, account_equity: float, risk_pct_per_trade: float = 0.02,
                            atr_window: int = 14, stop_loss_atr_multiple: float = 1.5) -> RiskParameters:
    """Fixes the stop-loss distance purely from measured historical volatility (ATR) and a
    risk budget, computed once per symbol before any strategy is simulated against it."""
    a = atr(bars, atr_window)
    stop_move = a * stop_loss_atr_multiple
    risk_budget = account_equity * risk_pct_per_trade
    max_contracts = max(int(risk_budget / max(stop_move * 100, 1.0)), 1)
    return RiskParameters(a, stop_loss_atr_multiple, stop_move, max_contracts)
