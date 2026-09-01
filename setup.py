"""One-command setup wizard. Run this first — it's the only manual step this
project asks for. Everything else (installing the MCP server, running the
backtest, checking connectivity) happens automatically.

Usage:
    python setup.py
"""
import getpass
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENV_PATH = ".env"
ENV_EXAMPLE_PATH = ".env.example"


def _read_env() -> dict:
    values = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip()
    return values


def _write_env(values: dict) -> None:
    # Preserve the .env.example structure/comments where possible; otherwise write plain.
    template = ""
    if os.path.exists(ENV_EXAMPLE_PATH):
        with open(ENV_EXAMPLE_PATH, encoding="utf-8") as f:
            template = f.read()

    def replace_or_keep(match):
        key = match.group(1)
        if key in values:
            # Write explicitly, even if blank — leaving it blank must produce KEY=, not
            # silently fall back to the .env.example placeholder text (which would then
            # read back as a truthy-but-invalid "key").
            return f"{key}={values[key]}"
        return match.group(0)

    if template:
        out = re.sub(r"^([A-Z_]+)=.*$", replace_or_keep, template, flags=re.MULTILINE)
    else:
        out = "\n".join(f"{k}={v}" for k, v in values.items())

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(out)


def _prompt(label: str, current: str, secret: bool = False, required: bool = True) -> str:
    shown = (current[:4] + "..." + current[-4:]) if secret and len(current) > 10 else current
    suffix = f" [{shown}]" if current else ""
    while True:
        reader = getpass.getpass if secret else input
        value = reader(f"{label}{suffix}: ").strip()
        if not value:
            if current:
                return current
            if not required:
                return ""
            print("  This is required.")
            continue
        return value


def check_uv() -> bool:
    return shutil.which("uv") is not None and shutil.which("uvx") is not None


def main():
    print("=" * 60)
    print("Alpaca Options Trading Agent — Setup Wizard")
    print("=" * 60)

    # 1. Python/deps sanity check
    try:
        import mcp  # noqa: F401
        import anthropic  # noqa: F401
        import openai  # noqa: F401
        import alpaca  # noqa: F401
        import dotenv  # noqa: F401
    except ImportError:
        print("\nMissing dependencies. Installing from requirements.txt...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

    # 2. uv/uvx check (needed to launch Alpaca's MCP server)
    print("\nChecking for uv/uvx (runs Alpaca's MCP server)...")
    if check_uv():
        print("  Found.")
    else:
        print("  NOT FOUND. Install it first: https://docs.astral.sh/uv/getting-started/installation/")
        print("  Setup can continue, but nothing will run until uv/uvx is on PATH.")

    # 3. Credentials
    print("\n--- Alpaca (required) ---")
    print("Use a paper trading account. IMPORTANT: for final hackathon submission, this must")
    print("be a brand-new account dedicated to the event — an existing/reused one won't be")
    print("eligible for judging. It's fine to set up with any paper account for now, though.")
    existing = _read_env()
    alpaca_key = _prompt("Alpaca API key", existing.get("ALPACA_API_KEY", ""))
    alpaca_secret = _prompt("Alpaca secret key", existing.get("ALPACA_SECRET_KEY", ""), secret=True)

    print("\n--- Anthropic (optional — only needed for the Claude-driven agent) ---")
    print("Leave blank to skip: `python main.py --deterministic` works with zero Anthropic cost.")
    anthropic_key = _prompt("Anthropic API key", existing.get("ANTHROPIC_API_KEY", ""), secret=True, required=False)

    values = {
        "ALPACA_API_KEY": alpaca_key,
        "ALPACA_SECRET_KEY": alpaca_secret,
        "ALPACA_PAPER_TRADE": "true",  # always — this project has no supported live-trading path
        "ANTHROPIC_API_KEY": anthropic_key,
    }
    _write_env(values)
    print(f"\nSaved to {ENV_PATH}.")

    # 4. Connectivity check
    print("\nVerifying Alpaca connectivity...")
    os.environ["ALPACA_API_KEY"] = alpaca_key
    os.environ["ALPACA_SECRET_KEY"] = alpaca_secret
    os.environ["ALPACA_PAPER_TRADE"] = "true"
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(alpaca_key, alpaca_secret, paper=True)
        account = client.get_account()
        print(f"  Connected. Account status: {account.status}, equity: ${float(account.equity):,.2f}")
    except Exception as exc:
        print(f"  Could not connect: {exc}")
        print("  Double-check the keys above and re-run `python setup.py`.")
        raise SystemExit(1)

    # 5. Backtest — nothing else is useful without this
    print("\nRunning the strategy backtest (this is what everything else reads)...")
    subprocess.run([sys.executable, "run_backtest.py"], check=False)

    print("\n" + "=" * 60)
    print("Setup complete. Try it now:")
    print("  python main.py --deterministic     (free — no Anthropic key needed)")
    if anthropic_key:
        print("  python main.py --once              (Claude-driven, one cycle)")
    print("  python kill_switch.py status       (check the manual kill switch)")
    print("=" * 60)


if __name__ == "__main__":
    main()
