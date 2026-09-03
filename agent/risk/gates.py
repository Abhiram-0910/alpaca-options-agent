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
from agent.session_window import entries_blocked
from agent.demonstration import demonstration_status, DEMONSTRATION_STATUS

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


def mleg_capital_at_risk(legs: list, qty: float, limit_price) -> tuple:
    """Capital at risk for a paired, defined-risk multi-leg order: (dollars, explanation).

    Returns (None, reason) when the structure cannot be shown to be defined-risk from the
    payload alone, in which case the caller must reject rather than guess.

    The per-leg estimator below is what deadlocked this account. It prices a short put at
    strike * 100 -- the cash-secured requirement -- because a lone short leg really does carry
    that exposure. But the legs of an mleg order fill together or not at all, so a bull put
    spread's real worst case is the distance between its strikes less the credit taken in,
    which for a 5-wide SPY spread is a few hundred dollars against the ~$75,000 the per-leg
    model was charging it. Charging notional for defined risk didn't make the account safer;
    it made every defined-risk structure unplaceable and left cash-secured puts -- which carry
    that exposure for real -- as the only thing the gate would pass.

    Width and credit both come from the order payload (strikes off the OCC symbols, net price
    off limit_price), not from a caller's assertion, so there is nothing here for a model to
    overstate.
    """
    parsed = []
    ratios = set()
    for leg in legs:
        p = parse_occ_symbol((leg.get("symbol") or "").strip())
        if p is None:
            return None, f"leg symbol {leg.get('symbol')!r} is not a recognizable OCC option symbol"
        p["side"] = (leg.get("side") or "").lower()
        if p["side"] not in ("buy", "sell"):
            return None, f"leg {leg.get('symbol')} has side {leg.get('side')!r}; expected buy or sell"
        # ratio_qty was read by nothing here until the adversarial harness submitted a
        # buy-1/sell-2 payload and the gate approved it: the width-times-qty model below
        # priced it as a 1:1 vertical, so the second short contract was naked and charged
        # nothing. Ratio spreads are out of scope for this agent, and refusing them is both
        # safe and honest -- pricing one correctly is a different structure model, and a gate
        # that silently mis-prices is worse than one that declines.
        raw_ratio = leg.get("ratio_qty", 1)
        if raw_ratio is None or raw_ratio == "":
            raw_ratio = 1
        try:
            ratio = float(raw_ratio)
        except (TypeError, ValueError):
            return None, f"leg {leg.get('symbol')} has ratio_qty {leg.get('ratio_qty')!r}; expected a number"
        if ratio <= 0:
            return None, f"leg {leg.get('symbol')} has ratio_qty {ratio:g}; must be positive"
        ratios.add(ratio)
        parsed.append(p)

    if len(ratios) != 1:
        return None, ("legs carry unequal ratio_qty "
                      f"({', '.join(f'{r:g}' for r in sorted(ratios))}); this gate prices 1:1 "
                      "defined-risk structures only, and an unmatched short leg is naked")

    if len({p["expiration"] for p in parsed}) != 1:
        return None, ("legs span more than one expiration; this gate only prices single-expiry "
                      "defined-risk structures")

    # Widest short-to-long distance within each option type is the structure's exposure.
    widths = []
    for option_type in ("put", "call"):
        shorts = [p for p in parsed if p["option_type"] == option_type and p["side"] == "sell"]
        longs = [p for p in parsed if p["option_type"] == option_type and p["side"] == "buy"]
        if not shorts:
            continue
        if not longs:
            return None, (f"short {option_type} leg has no long {option_type} leg in the same "
                          f"order; this is an undefined-risk structure")
        for short in shorts:
            if option_type == "put":
                cover = [l for l in longs if l["strike"] < short["strike"]]
            else:
                cover = [l for l in longs if l["strike"] > short["strike"]]
            if not cover:
                return None, (f"short {option_type} at {short['strike']} has no further-OTM long "
                              f"{option_type} covering it; undefined risk")
            nearest = min(cover, key=lambda l: abs(l["strike"] - short["strike"]))
            widths.append(abs(short["strike"] - nearest["strike"]))

    if limit_price in (None, ""):
        return None, "multi-leg order has no limit_price; cannot price its worst case"
    try:
        net = float(limit_price)
    except (TypeError, ValueError):
        return None, f"limit_price {limit_price!r} is not a number"

    # Alpaca's mleg convention (server docstring): positive limit_price = net debit paid,
    # negative = net credit received.
    if not widths:
        # All long legs: the most that can be lost is what was paid for them.
        if net <= 0:
            return None, "all-long structure priced as a credit; refusing to price its risk"
        return net * 100 * qty, f"debit paid {net:.2f} x 100 x {qty:g}"

    width = max(widths)
    credit = -net
    if credit <= 0:
        # A debit spread: worst case is the debit, already bounded.
        return net * 100 * qty, f"debit paid {net:.2f} x 100 x {qty:g}"
    if credit >= width:
        return None, (f"net credit {credit:.2f} is not below the {width:.2f} spread width; "
                      f"refusing an implausibly priced structure")
    return (width - credit) * 100 * qty, f"({width:.2f} width - {credit:.2f} credit) x 100 x {qty:g}"


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
    # OCC symbols a caller has confirmed exist on a real chain it just fetched. Empty by
    # default and then inert: the gate is synchronous and does no network I/O, so it cannot
    # establish on its own whether a contract is listed. A caller that HAS a chain in hand
    # (the demonstration path builds its legs from one) passes it here, and the gate then
    # refuses any leg outside it.
    #
    # Found by the adversarial harness: with this empty, an order for a strike $250 above
    # every listed SPY strike was approved and would have been sent to Alpaca to be rejected,
    # having first consumed this cycle's capital budget for a contract that cannot fill.
    known_contracts: set = field(default_factory=set)
    _existing_capital_seeded: bool = False

    def _unknown_contract(self, symbol: str) -> str:
        """Rejection reason if `symbol` is outside a supplied chain, else ""."""
        if self.known_contracts and symbol not in self.known_contracts:
            return (f"{symbol} is not on the option chain this cycle fetched "
                    f"({len(self.known_contracts)} contracts); refusing to submit an order for "
                    f"a contract that does not exist")
        return ""

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

    def _reject(self, reason: str, capital_at_risk=None, capital_basis: str = None) -> dict:
        """A rejection carries the capital figure whenever the gate got far enough to compute
        one -- which is every cap breach, the rejections that actually matter.

        The figure is returned as a real number rather than left to be scraped back out of
        `reason`: the prose is rounded for humans ("$75,500"), is free to be reworded, and a
        dashboard parsing money out of an error string will eventually parse the wrong number.
        Rejections thrown before capital is computed (bad OCC symbol, DTE out of window,
        kill switch) pass None, and None means "never computed" -- never zero.
        """
        self.rejections.append(reason)
        return {"approved": False, "reason": reason,
                "estimated_capital_at_risk": None if capital_at_risk is None else round(capital_at_risk, 2),
                "capital_basis": capital_basis}

    def release_commitment(self, amount: float) -> None:
        """Rolls back capital that check() committed for a leg whose multi-leg batch was then
        abandoned before every leg could be approved (e.g. an iron condor's first two legs pass
        before its short call is rejected). Without this, an abandoned batch's capital stays
        "committed" for the rest of the cycle even though no order for it ever reached Alpaca,
        permanently shrinking the real budget available to later, legitimate trades this cycle."""
        self.committed_this_cycle = max(0.0, self.committed_this_cycle - (amount or 0.0))

    def _check_mleg(self, tool_input: dict) -> dict:
        """Gate a multi-leg order as one structure rather than as loose legs.

        The per-leg checks (OCC parse, DTE, validated symbol) still run on every leg -- a
        spread built from one in-window leg and one four-month leg is not defined risk in any
        useful sense. What changes is capital: it is computed once, from the structure, by
        mleg_capital_at_risk.

        Naked-call cover is read from the legs themselves here, which is exactly what
        `covered_by_paired_long` forbids on the single-leg path -- and the difference is real,
        not a relaxation. On the single-leg path the legs are separate orders that can fill
        independently, so a claimed hedge may never exist; in an mleg order the legs fill
        together or not at all, so a further-OTM long call in the same payload is structural
        cover, verifiable from the payload without trusting anyone's assertion.
        """
        legs = tool_input.get("legs") or []
        if not isinstance(legs, list) or not 2 <= len(legs) <= 4:
            return self._reject(f"Multi-leg order must carry 2-4 legs; got {len(legs) if isinstance(legs, list) else legs!r}.")

        raw_qty = tool_input.get("qty", 1)
        if raw_qty is None or raw_qty == "":
            raw_qty = 1
        try:
            qty = float(raw_qty)
        except (TypeError, ValueError):
            return self._reject(f"qty {tool_input.get('qty')!r} is not a number; refusing to submit.")
        if qty <= 0:
            return self._reject(f"qty must be positive (got {qty}); refusing to submit.")

        roots = set()
        for leg in legs:
            if not isinstance(leg, dict):
                return self._reject(f"Multi-leg leg {leg!r} is not an object; refusing to submit.")
            leg_symbol = (leg.get("symbol") or "").strip()
            parsed = parse_occ_symbol(leg_symbol)
            if not parsed:
                return self._reject(f"'{leg_symbol}' is not a recognizable OCC option symbol; refusing to submit.")
            unknown = self._unknown_contract(leg_symbol)
            if unknown:
                return self._reject(unknown)
            dte = (parsed["expiration"] - date.today()).days
            if dte < CONFIG.min_days_to_expiration or dte > CONFIG.max_days_to_expiration:
                return self._reject(
                    f"{leg_symbol} has {dte} days to expiration; agent is restricted to "
                    f"{CONFIG.min_days_to_expiration}-{CONFIG.max_days_to_expiration} DTE."
                )
            roots.add(parsed["root"])

        if len(roots) != 1:
            return self._reject(f"Multi-leg order spans several underlyings ({', '.join(sorted(roots))}); "
                                 f"refusing to price a cross-underlying structure.")
        root = roots.pop()

        demo = demonstration_status(root, legs, qty)
        if demo["blocked"]:
            return self._reject(demo["blocked"])
        if not demo["armed"] and CONFIG.require_backtest_validation and root not in load_cleared_symbols():
            return self._reject(
                f"{root} has no strategy that passed the backtest validation gate "
                f"(see logs/backtest_report.json / docs/strategy_graveyard.md) — refusing to open "
                f"a new position on an unproven symbol. Run run_backtest.py to check for updates, "
                f"or pick a symbol that has cleared validation."
            )

        capital_at_risk, detail = mleg_capital_at_risk(legs, qty, tool_input.get("limit_price"))
        if capital_at_risk is None:
            return self._reject(f"Cannot establish defined risk for this multi-leg order: {detail}.")

        held_this_cycle = self.held_option_roots | set(self.open_positions.keys()) | self.symbols_committed_this_cycle
        if len({root} | held_this_cycle) > CONFIG.max_positions_open and root not in held_this_cycle:
            return self._reject(f"Opening {root} would exceed the {CONFIG.max_positions_open}-position limit.")

        max_per_trade = CONFIG.max_allocation_pct_per_trade * self.equity
        if CONFIG.max_allocation_usd_per_trade > 0:
            max_per_trade = min(max_per_trade, CONFIG.max_allocation_usd_per_trade)
        if demo["armed"]:
            max_per_trade = min(max_per_trade, demo["max_loss_cap"])
        if capital_at_risk > max_per_trade:
            return self._reject(
                f"Estimated capital at risk ${capital_at_risk:,.0f} [{detail}] exceeds the per-trade "
                f"cap ${max_per_trade:,.0f}.",
                capital_at_risk, detail,
            )

        max_total = CONFIG.max_total_options_allocation_pct * self.equity
        if CONFIG.max_total_options_allocation_usd > 0:
            max_total = min(max_total, CONFIG.max_total_options_allocation_usd)
        if self.committed_this_cycle + capital_at_risk > max_total:
            return self._reject(
                f"This trade would push total options capital-at-risk this cycle to "
                f"${self.committed_this_cycle + capital_at_risk:,.0f}, above the "
                f"{CONFIG.max_total_options_allocation_pct:.0%} portfolio cap (${max_total:,.0f}).",
                capital_at_risk, detail,
            )

        self.committed_this_cycle += capital_at_risk
        self.symbols_committed_this_cycle.add(root)
        approved = {"approved": True, "estimated_capital_at_risk": round(capital_at_risk, 2),
                    "capital_basis": detail}
        if demo["armed"]:
            approved["validation_status"] = DEMONSTRATION_STATUS
        return approved

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

        # Dated NFP window rule (agent/session_window.py). Sits here rather than in one agent
        # path so all three -- deterministic, single-agent, multi-agent -- inherit it, and so
        # the refusal is recorded as a decision in the rejection list rather than showing up
        # as an empty book.
        blocked = entries_blocked()
        if blocked:
            return self._reject(f"No new positions: {blocked}.")

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
        if tool_input.get("legs"):
            return self._check_mleg(tool_input)

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

        unknown = self._unknown_contract(symbol)
        if unknown:
            return self._reject(unknown)
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
                + ").",
                capital_at_risk,
            )

        max_total = CONFIG.max_total_options_allocation_pct * self.equity
        if CONFIG.max_total_options_allocation_usd > 0:
            max_total = min(max_total, CONFIG.max_total_options_allocation_usd)
        if self.committed_this_cycle + capital_at_risk > max_total:
            return self._reject(
                f"This trade would push total options capital-at-risk this cycle to "
                f"${self.committed_this_cycle + capital_at_risk:,.0f}, above the "
                f"{CONFIG.max_total_options_allocation_pct:.0%} portfolio cap (${max_total:,.0f}).",
                capital_at_risk,
            )

        self.committed_this_cycle += capital_at_risk
        self.symbols_committed_this_cycle.add(parsed["root"])
        return {"approved": True, "estimated_capital_at_risk": round(capital_at_risk, 2)}
