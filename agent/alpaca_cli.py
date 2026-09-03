"""Alpaca CLI (alpacahq/cli) as a read path for account and position state.

Alpaca shipped this CLI in 2026 and it is a first-class surface for the Trading API, so the
agent reads its own account through it rather than only through alpaca-py. It is used for
reads only: account and open positions, refreshed into the dashboard export every cycle.
**Order placement stays on the MCP server** -- one order path, one risk gate, no second way
to reach the account.

Every call degrades to None rather than raising. A missing binary, an unauthenticated
profile, a network blip or a schema change must leave the caller free to fall back to
alpaca-py; a dashboard that cannot render because a CLI was not installed would be a worse
system than the one that had no CLI.

Setup (once):
    alpaca profile login --api-key --paper --key "$ALPACA_API_KEY" --secret "$ALPACA_SECRET_KEY"
    alpaca doctor
"""
import json
import os
import shutil
import subprocess

# --profile paper is passed explicitly rather than relying on the active profile: this
# project has no live path, and an ambient profile switch must not be able to point a read
# at a live account.
PROFILE = "paper"
TIMEOUT_SECONDS = 20


def binary_path() -> str:
    """Absolute path to the alpaca binary, or "" when it is not installed.

    ~/.local/bin is checked directly because it is on an interactive PATH but not always on
    the PATH a service or cron job inherits.
    """
    found = shutil.which("alpaca")
    if found:
        return found
    fallback = os.path.expanduser("~/.local/bin/alpaca")
    return fallback if os.path.isfile(fallback) and os.access(fallback, os.X_OK) else ""


def _run(*args):
    """Run one CLI subcommand and parse its JSON. None on any failure at all."""
    exe = binary_path()
    if not exe:
        return None
    try:
        proc = subprocess.run([exe, *args, "--profile", PROFILE, "--quiet"],
                              capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        # The CLI reports some errors as a JSON object on stdout with a non-zero "code"
        # rather than a non-zero exit status, and prints plain text in other cases. Anything
        # that is not parseable JSON is treated as a failed read.
        return None


def version() -> str:
    """CLI version string, or "" when unavailable. Recorded in the export for provenance."""
    exe = binary_path()
    if not exe:
        return ""
    try:
        proc = subprocess.run([exe, "version"], capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return ""
    out = (proc.stdout or "").strip()
    try:
        parsed = json.loads(out)
        if isinstance(parsed, dict):
            return str(parsed.get("version") or parsed.get("Version") or "").strip()
    except ValueError:
        pass
    return out.splitlines()[0].strip() if out else ""


def get_account():
    """Account dict from `alpaca account get`, or None."""
    data = _run("account", "get")
    return data if isinstance(data, dict) and data.get("account_number") else None


def get_positions():
    """List of open positions from `alpaca position list`, or None.

    An empty book is `[]`, which is a successful read and must not be confused with None.
    """
    data = _run("position", "list")
    return data if isinstance(data, list) else None


def demo() -> None:
    """Self-check: reads must either work or degrade cleanly, never raise."""
    exe = binary_path()
    print(f"binary: {exe or '(not installed)'}")
    if not exe:
        assert get_account() is None and get_positions() is None
        print("not installed -> both reads return None, caller falls back to alpaca-py")
        return

    print(f"version: {version() or '(unknown)'}")
    acct = get_account()
    positions = get_positions()

    if acct is None:
        print("account read failed (not authenticated?) -> None, caller falls back")
    else:
        assert acct.get("account_number"), acct
        # This project has no live path; a CLI read must not be pointed at a live account.
        assert acct["account_number"].startswith("PA"), \
            f"expected a paper account number, got {acct['account_number']}"
        print(f"account: {acct['account_number']} equity={acct.get('equity')} "
              f"options_level={acct.get('options_trading_level')}")

    assert positions is None or isinstance(positions, list), positions
    print(f"positions: {'read failed' if positions is None else f'{len(positions)} open'}")
    print("alpaca_cli: all checks pass")


if __name__ == "__main__":
    demo()
