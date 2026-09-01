"""Risk gates that stand between Claude's tool calls and the real Alpaca account.

Every order-placing MCP tool call the agent wants to make is passed through
`RiskGate.check()` first. A rejection is returned to Claude as a tool result
(not an exception) so it can adapt its plan — the loop never lets an
order-placing call reach Alpaca without passing every gate below.
"""
import re
from dataclasses import dataclass, field
from datetime import date

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


def _estimate_capital_at_risk(option_type: str, side: str, strike: float, qty: float,
                               premium: float = None) -> float:
    """Rough capital-at-risk estimate for one option leg, shared by check() (a *prospective*
    order) and refresh() (an *existing* position, so the total-allocation cap has a real
    baseline instead of only ever tracking capital committed since this RiskGate was built)."""
    if side == "sell" and option_type == "put":
        return strike * 100 * qty  # cash-secured put capital requirement
    if side == "buy":
        return (premium if premium is not None else strike * 0.03) * 100 * qty
    return strike * 100 * qty * 0.20  # covered call / spread short leg, approx


@dataclass
class RiskGate:
    equity: float = 0.0
    day_start_equity: float = 0.0
    open_positions: dict = field(default_factory=dict)  # underlying ticker -> shares held (stock only)
    held_option_roots: set = field(default_factory=set)  # underlyings with an existing *option* leg open
    # Capital committed this cycle: seeded once (see refresh()) from a rough estimate of capital
    # already at risk in positions that existed *before* this RiskGate was built, then increased
    # by check() as it approves new orders this cycle. Must only reset when a new cycle starts
    # (a fresh RiskGate is built per cycle) — get_all_positions won't reflect a same-cycle
    # approval until the next MCP round-trip, so this is the only record of it in the meantime.
    committed_this_cycle: float = 0.0
    # Underlying roots check() has approved a *new* position for earlier this same cycle --
    # refresh() only reflects Alpaca's confirmed positions, which lag same-cycle approvals by a
    # full MCP round-trip, so the position-count gate needs its own cycle-local memory of what
    # it has already said yes to, exactly like committed_this_cycle does for capital.
    symbols_committed_this_cycle: set = field(default_factory=set)
    rejections: list = field(default_factory=list)
    _existing_capital_seeded: bool = False

    def refresh(self, account_info: dict, positions: list) -> None:
        """Convenience wrapper for the common case of updating both at once (e.g. at the top of
        a cycle, when get_account_info and get_all_positions were just fetched together). A
        caller that re-fetches only ONE of the two mid-cycle should call the matching update_*
        method directly instead of reconstructing a fake stand-in for the other argument here."""
        self.update_account(account_info)
        self.update_positions(positions)

    def update_account(self, account_info: dict) -> None:
        self.equity = float(account_info.get("equity", 0) or 0)
        if self.day_start_equity == 0.0:
            last_equity = account_info.get("last_equity")
            self.day_start_equity = float(last_equity) if last_equity else self.equity

    def update_positions(self, positions: list) -> None:
        # get_all_positions returns stock positions keyed by their plain ticker and option
        # positions keyed by their full OCC symbol -- keep the two separate rather than one dict
        # (previously both landed in open_positions together, which let a single underlying's
        # multi-leg spread count as several "distinct symbols" below, and meant the OCC key could
        # never match parsed["root"] for the "already held" carve-out). open_positions (share
        # counts) backs the covered-call check; held_option_roots backs the position-count gate.
        self.open_positions = {}
        self.held_option_roots = set()
        existing_capital = 0.0
        for p in positions:
            sym = p.get("symbol", "")
            qty = abs(float(p.get("qty", 0) or 0))
            parsed = parse_occ_symbol(sym)
            if parsed is None:
                self.open_positions[sym] = float(p.get("qty", 0) or 0)
                continue
            self.held_option_roots.add(parsed["root"])
            if not self._existing_capital_seeded:
                pos_side = (p.get("side") or "").lower()  # Alpaca position side: "long" or "short"
                existing_capital += _estimate_capital_at_risk(
                    parsed["option_type"], "sell" if pos_side == "short" else "buy", parsed["strike"], qty,
                )
        if not self._existing_capital_seeded:
            # Seed only once, from the first refresh() this instance ever sees -- not on every
            # mid-cycle refresh, or a position this cycle already committed capital for (via
            # check(), below) would get double-counted once Alpaca's own snapshot catches up to
            # it later in the same cycle.
            self.committed_this_cycle += existing_capital
            self._existing_capital_seeded = True

    def _reject(self, reason: str) -> dict:
        self.rejections.append(reason)
        return {"approved": False, "reason": reason}

    def release_commitment(self, amount: float) -> None:
        """Rolls back capital that check() committed for a leg whose multi-leg batch was then
        abandoned before every leg could be approved (e.g. an iron condor's first two legs pass
        before its short call is rejected). Without this, an abandoned batch's capital stays
        "committed" for the rest of the cycle even though no order for it ever reached Alpaca,
        permanently shrinking the real budget available to later, legitimate trades this cycle."""
        self.committed_this_cycle = max(0.0, self.committed_this_cycle - (amount or 0.0))

    def check(self, tool_name: str, tool_input: dict, covered_by_paired_long: bool = False) -> dict:
        """`covered_by_paired_long` must only be set by a caller that has already verified, from
        its own multi-leg strategy plan, that this specific short call is hedged by a
        further-OTM long call in the *same* order batch (e.g. an iron condor's short_call vs.
        its own long_call) -- never derived from tool_input, so an LLM calling place_option_order
        directly can't set it. It skips the share-ownership requirement for *that one leg only*;
        every other gate below (DTE, backtest validation, capital caps, position count) still
        applies in full."""
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
        # Only a genuinely missing/None/empty qty defaults to 1 -- unlike the old `x or 1`, an
        # *explicit* qty of 0 must NOT be silently rewritten to 1, or it would dodge the qty<=0
        # check just below the same way a negative qty otherwise would.
        raw_qty = tool_input.get("qty", 1)
        if raw_qty is None or raw_qty == "":
            raw_qty = 1
        try:
            qty = float(raw_qty)
        except (TypeError, ValueError):
            return self._reject(f"qty {tool_input.get('qty')!r} is not a number; refusing to submit.")
        if qty <= 0:
            # `or 1` above only rescues falsy qtys (0/None/"") -- a *negative* qty is truthy and
            # would otherwise sail through, flip every capital-at-risk sign, trivially clear the
            # naked-call and per-trade caps, and *subtract* from committed_this_cycle below,
            # manufacturing headroom for a later trade in the same cycle. Reject outright instead.
            return self._reject(f"qty must be positive (got {qty}); refusing to submit.")
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

        if side == "sell" and parsed["option_type"] == "call" and not covered_by_paired_long:
            shares_owned = self.open_positions.get(parsed["root"], 0)
            if shares_owned < 100 * qty:
                return self._reject(
                    f"Selling {qty} {symbol} call(s) requires {int(100 * qty)} shares of {parsed['root']} "
                    f"owned as cover; account only holds {shares_owned}. Naked calls are not permitted."
                )

        # Position count gate. held_this_cycle folds in roots already held (stock ticker or an
        # existing option leg, reduced to its root so a multi-leg spread counts once) plus roots
        # check() has already approved a *new* position for earlier this same cycle.
        held_this_cycle = self.held_option_roots | set(self.open_positions.keys()) | self.symbols_committed_this_cycle
        distinct_symbols = {parsed["root"]} | held_this_cycle
        if len(distinct_symbols) > CONFIG.max_positions_open and parsed["root"] not in held_this_cycle:
            return self._reject(
                f"Opening {parsed['root']} would exceed the {CONFIG.max_positions_open}-position limit."
            )

        # Per-trade capital-at-risk gate.
        limit_price = tool_input.get("limit_price")
        est_premium = float(limit_price) if limit_price else parsed["strike"] * 0.03  # rough fallback estimate
        capital_at_risk = _estimate_capital_at_risk(parsed["option_type"], side, parsed["strike"], qty,
                                                      premium=est_premium)

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
        self.symbols_committed_this_cycle.add(parsed["root"])
        return {"approved": True, "estimated_capital_at_risk": round(capital_at_risk, 2)}
