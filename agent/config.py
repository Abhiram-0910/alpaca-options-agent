"""Central configuration loaded from environment / .env."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# override=True: without it, load_dotenv() silently keeps whatever is already in the OS
# environment instead of this project's own .env — verified live: a pre-existing system
# OPENAI_API_KEY=ollama (unrelated to this project) shadowed the real key in .env and sent
# every OpenAI call to the wrong credential with no error until the API call itself failed.
load_dotenv(override=True)


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    alpaca_api_key: str = os.getenv("ALPACA_API_KEY", "")
    alpaca_secret_key: str = os.getenv("ALPACA_SECRET_KEY", "")
    alpaca_paper: bool = _bool("ALPACA_PAPER_TRADE", True)

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Universe of underlyings the agent is allowed to trade options on. Kept liquid so
    # backtests and live option chain lookups stay fast. Widened from the original 8 after
    # the sub-period stability gate (agent/backtest/metrics.py) demoted the only strategy
    # that had cleared — a stricter bar needs more candidates to have a fair chance of
    # finding a genuinely temporally-stable edge, not just a stronger requirement on the
    # same narrow set. Spans sectors deliberately (financials, healthcare, staples, energy,
    # broad-market ETFs) rather than adding more mega-cap tech names correlated with what's
    # already here.
    watchlist: tuple = field(default_factory=lambda: (
        "AAPL", "MSFT", "NVDA", "SPY", "QQQ", "AMD", "TSLA", "AMZN",
        "GOOGL", "META", "JPM", "BAC", "WMT", "UNH", "V", "XOM", "IWM", "DIA",
    ))

    # --- Risk gates (see agent/risk/gates.py for enforcement) ---
    # Hard-blocks place_option_order on any symbol with no strategy that passed the backtest
    # validation gate — not just a system-prompt preference. Verified necessary live: a
    # cheaper model traded an unvalidated symbol on its first real run without this.
    require_backtest_validation: bool = _bool("REQUIRE_BACKTEST_VALIDATION", True)
    max_positions_open: int = int(os.getenv("MAX_POSITIONS_OPEN", "5"))
    max_allocation_pct_per_trade: float = float(os.getenv("MAX_ALLOCATION_PCT_PER_TRADE", "0.08"))
    max_total_options_allocation_pct: float = float(os.getenv("MAX_TOTAL_OPTIONS_ALLOCATION_PCT", "0.40"))
    # Absolute-dollar caps alongside the percentage caps above — a percentage cap alone gets
    # more permissive in dollar terms as the account grows, which is the wrong direction for a
    # risk ceiling. 0 disables the corresponding dollar cap (percentage-only, the original
    # behavior); when both are set, whichever is more restrictive wins.
    max_allocation_usd_per_trade: float = float(os.getenv("MAX_ALLOCATION_USD_PER_TRADE", "0"))
    max_total_options_allocation_usd: float = float(os.getenv("MAX_TOTAL_OPTIONS_ALLOCATION_USD", "0"))
    daily_loss_limit_pct: float = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "0.05"))
    min_days_to_expiration: int = int(os.getenv("MIN_DTE", "7"))
    max_days_to_expiration: int = int(os.getenv("MAX_DTE", "45"))
    max_tool_calls_per_cycle: int = int(os.getenv("MAX_TOOL_CALLS_PER_CYCLE", "25"))

    # Hard ceiling on cumulative Anthropic API spend for one `main.py --loop` session
    # (not per-cycle) — the loop stops itself once actual measured cost reaches this,
    # independent of any cost estimate. $0 or negative disables the cap.
    max_session_spend_usd: float = float(os.getenv("MAX_SESSION_SPEND_USD", "5.00"))

    # --- Position/order management (agent/order_manager.py) — universal, strategy-agnostic
    # rules applied to whatever is already open, regardless of which agent opened it. ---
    force_close_dte: int = int(os.getenv("FORCE_CLOSE_DTE", "2"))            # 0 disables
    position_profit_take_pct: float = float(os.getenv("POSITION_PROFIT_TAKE_PCT", "0.50"))  # 0 disables
    position_stop_loss_pct: float = float(os.getenv("POSITION_STOP_LOSS_PCT", "0.75"))       # 0 disables
    stale_order_minutes: int = int(os.getenv("STALE_ORDER_MINUTES", "60"))   # 0 disables

    logs_dir: str = os.getenv("LOGS_DIR", "logs")


class LiveTradingBlocked(RuntimeError):
    """Raised when something tried to trade with ALPACA_PAPER_TRADE not set to true.

    This project is built and risk-validated exclusively against Alpaca's paper
    environment — the statistical validation gate, the risk caps, all of it assumes
    paper money. There is no supported live-trading path, so this is a hard block,
    not a warning: every order-placing entry point checks this before doing anything
    else, not just the CLI layer, so a caller that imports and calls run_cycle()
    directly (bypassing main.py) is still protected.
    """


CONFIG = Config()


def assert_paper_trading() -> None:
    if not CONFIG.alpaca_paper:
        raise LiveTradingBlocked(
            "ALPACA_PAPER_TRADE is not true. This project is built and risk-validated "
            "for Alpaca's PAPER trading environment only — refusing to place any order "
            "against what would be a live account."
        )
