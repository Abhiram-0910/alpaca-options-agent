"""Risk gates that stand between Claude's tool calls and the real Alpaca account.

Every order-placing MCP tool call the agent wants to make is passed through
`RiskGate.check()` first. A rejection is returned to Claude as a tool result
(not an exception) so it can adapt its plan — the loop never lets an
order-placing call reach Alpaca without passing every gate below.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from agent.config import CONFIG
from agent.kill_switch import is_active as kill_switch_active, reason as kill_switch_reason
from agent.backtest_evidence import load_cleared_symbols

ORDER_TOOLS = {"place_stock_order", "place_option_order", "place_crypto_order"}
_OCC_RE = re.compile(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$")


def parse_occ_symbol(symbol: str):
    m = _OCC_RE.match(symbol)
    if not m:
        return None
    root, yymmdd, cp, strike_raw = m.groups()
    expiration = date(2000 + int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6]))
    return {
        "root": root,
        "expiration": expiration,
        "option_type": "call" if cp == "C" else "put",
        "strike": int(strike_raw) / 1000.0,
    }


@dataclass
class RiskGate:
    equity: float = 0.0
    day_start_equity: float = 0.0
    open_positions: dict = field(default_factory=dict)  # symbol -> qty
    # capital already committed by tool calls approved earlier *this cycle*,
    # since get_all_positions won't reflect them until the next MCP round-trip
    committed_this_cycle: float = 0.0
    rejections: list = field(default_factory=list)

    def refresh(self, account_info: dict, positions: list):
        self.equity = float(account_info.get("equity", 0) or 0)
        if self.day_start_equity == 0.0:
            last_equity = account_info.get("last_equity")
            self.day_start_equity = float(last_equity) if last_equity else self.equity
        self.open_positions = {p["symbol"]: float(p.get("qty", 0)) for p in positions}
        # NOTE: committed_this_cycle deliberately persists across refresh() calls within
        # a cycle — it tracks capital approved by the risk gate that Alpaca's position
        # endpoint hasn't caught up to yet, and must only reset when a new cycle starts.

    def _reject(self, reason: str) -> dict:
        self.rejections.append(reason)
        return {"approved": False, "reason": reason}

    def check(self, tool_name: str, tool_input: dict) -> dict:
        if tool_name not in ORDER_TOOLS:
            return {"approved": True}

        if kill_switch_active():
            return self._reject(f"Kill switch is active: {kill_switch_reason()}. "
                                 f"No orders until `python kill_switch.py off`.")

        if self.equity <= 0:
            return self._reject("Risk gate has no account snapshot yet; refusing to trade blind.")

        # Circuit breaker: stop opening new risk once the daily loss limit is breached.
        daily_pnl_pct = (self.equity - self.day_start_equity) / self.day_start_equity if self.day_start_equity else 0
        if daily_pnl_pct <= -CONFIG.daily_loss_limit_pct:
            return self._reject(
                f"Daily loss circuit breaker tripped ({daily_pnl_pct:.1%} <= "
                f"-{CONFIG.daily_loss_limit_pct:.0%}). No new positions until tomorrow."
            )

        if tool_name == "place_stock_order":
            return self._reject(
                "Directional equity orders are out of scope for this agent — it only trades options "
                "premium strategies (cash-secured puts, covered calls, long calls/puts, credit spreads)."
            )

        if tool_name == "place_crypto_order":
            return self._reject("Crypto orders are out of scope; this agent trades equity options only.")

        # tool_name == "place_option_order"
        symbol = tool_input.get("symbol", "")
        side = (tool_input.get("side") or "").lower()
        qty = float(tool_input.get("qty", 1) or 1)
        parsed = parse_occ_symbol(symbol)
        if not parsed:
            return self._reject(f"'{symbol}' is not a recognizable OCC option symbol; refusing to submit.")

        dte = (parsed["expiration"] - date.today()).days
        if dte < CONFIG.min_days_to_expiration or dte > CONFIG.max_days_to_expiration:
            return self._reject(
                f"{symbol} has {dte} days to expiration; agent is restricted to "
                f"{CONFIG.min_days_to_expiration}-{CONFIG.max_days_to_expiration} DTE."
            )

        if CONFIG.require_backtest_validation and parsed["root"] not in load_cleared_symbols():
            return self._reject(
                f"{parsed['root']} has no strategy that passed the backtest validation gate "
                f"(see logs/backtest_report.json / docs/strategy_graveyard.md) — refusing to open "
                f"a new position on an unproven symbol. Run run_backtest.py to check for updates, "
                f"or pick a symbol that has cleared validation."
            )

        if side == "sell" and parsed["option_type"] == "call":
            shares_owned = self.open_positions.get(parsed["root"], 0)
            if shares_owned < 100 * qty:
                return self._reject(
                    f"Selling {qty} {symbol} call(s) requires {int(100 * qty)} shares of {parsed['root']} "
                    f"owned as cover; account only holds {shares_owned}. Naked calls are not permitted."
                )

        # Position count gate.
        distinct_symbols = {parsed["root"]} | set(self.open_positions.keys())
        if len(distinct_symbols) > CONFIG.max_positions_open and parsed["root"] not in self.open_positions:
            return self._reject(
                f"Opening {parsed['root']} would exceed the {CONFIG.max_positions_open}-position limit."
            )

        # Per-trade capital-at-risk gate.
        limit_price = tool_input.get("limit_price")
        est_premium = float(limit_price) if limit_price else parsed["strike"] * 0.03  # rough fallback estimate
        if side == "sell" and parsed["option_type"] == "put":
            capital_at_risk = parsed["strike"] * 100 * qty  # cash-secured put capital requirement
        elif side == "buy":
            capital_at_risk = est_premium * 100 * qty
        else:
            capital_at_risk = parsed["strike"] * 100 * qty * 0.20  # covered call / spread short leg, approx

        # Per-trade cap: percentage-of-equity and an optional absolute-dollar ceiling both
        # apply when the dollar cap is set (>0) — whichever is more restrictive wins, so the
        # cap can't quietly get more permissive in dollar terms as the account grows.
        max_per_trade = CONFIG.max_allocation_pct_per_trade * self.equity
        if CONFIG.max_allocation_usd_per_trade > 0:
            max_per_trade = min(max_per_trade, CONFIG.max_allocation_usd_per_trade)
        if capital_at_risk > max_per_trade:
            return self._reject(
                f"Estimated capital at risk ${capital_at_risk:,.0f} exceeds the per-trade cap "
                f"${max_per_trade:,.0f} ({CONFIG.max_allocation_pct_per_trade:.0%} of equity"
                + (f", capped at ${CONFIG.max_allocation_usd_per_trade:,.0f}" if CONFIG.max_allocation_usd_per_trade > 0 else "")
                + ")."
            )

        max_total = CONFIG.max_total_options_allocation_pct * self.equity
        if CONFIG.max_total_options_allocation_usd > 0:
            max_total = min(max_total, CONFIG.max_total_options_allocation_usd)
        if self.committed_this_cycle + capital_at_risk > max_total:
            return self._reject(
                f"This trade would push total options capital-at-risk this cycle to "
                f"${self.committed_this_cycle + capital_at_risk:,.0f}, above the "
                f"{CONFIG.max_total_options_allocation_pct:.0%} portfolio cap (${max_total:,.0f})."
            )

        self.committed_this_cycle += capital_at_risk
        return {"approved": True, "estimated_capital_at_risk": round(capital_at_risk, 2)}
