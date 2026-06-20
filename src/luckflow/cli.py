"""LuckFlow command-line interface.

Replaces the 900-line interactive menu in the legacy ``main.py`` with a Typer
app: one subcommand per operating mode. Each command lazily imports its workflow
so the CLI loads instantly and a single heavy dependency never blocks the rest.

    luckflow daily --workers 3
    luckflow warmup-volume --workers 2
    luckflow dashboard
"""

from __future__ import annotations

import asyncio

import typer

from luckflow.core import logging as log

app = typer.Typer(
    name="luckflow",
    help="Async multi-account browser-automation orchestration for Luck.io.",
    no_args_is_help=True,
    add_completion=False,
)


def _run(coro) -> None:
    """Run an async workflow under the right Windows event-loop policy."""
    import sys

    log.configure_stdout()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(coro)


@app.command()
def daily(workers: int = typer.Option(None, "--workers", "-w", help="Concurrent workers (default from config).")):
    """Run daily tasks: play a game and claim the daily chest."""
    from luckflow.workflows.daily import run_daily

    _run(run_daily(workers))


@app.command("warmup-volume")
def warmup_volume(workers: int = typer.Option(None, "--workers", "-w")):
    """Warm up trading volume across all game modes (with on-chain top-ups)."""
    from luckflow.workflows.warmup_volume import run_warmup_volume

    _run(run_warmup_volume(workers))


@app.command("extension-fix")
def extension_fix(workers: int = typer.Option(None, "--workers", "-w")):
    """Daily-style routine over the data_for_fix.xlsx account set."""
    from luckflow.workflows.extension_fix import run_extension_fix

    _run(run_extension_fix(workers))


@app.command()
def registration():
    """Register new accounts (connect wallet, activate, fund)."""
    from luckflow.workflows.registration import run_registration

    _run(run_registration())


@app.command("warmup-registration")
def warmup_registration(workers: int = typer.Option(None, "--workers", "-w")):
    """Registration plus daily-reward pre-activation."""
    from luckflow.workflows.warmup_registration import run_warmup_registration

    _run(run_warmup_registration(workers))


@app.command()
def withdraw(workers: int = typer.Option(None, "--workers", "-w")):
    """Automatically withdraw balances to the configured wallets."""
    from luckflow.workflows.withdraw import run_withdraw

    _run(run_withdraw(workers))


@app.command()
def renew(workers: int = typer.Option(None, "--workers", "-w")):
    """Find and click the Renew Play Timer button, funding it on-chain."""
    from luckflow.workflows.renew import run_renew

    _run(run_renew(workers))


@app.command("browser-setup")
def browser_setup(workers: int = typer.Option(None, "--workers", "-w")):
    """Set up browsers: import wallets and configure captcha."""
    from luckflow.workflows.browser_setup import run_browser_setup

    _run(run_browser_setup(workers))


@app.command("hardware-login")
def hardware_login(workers: int = typer.Option(None, "--workers", "-w")):
    """Open browsers prepared for manual hardware-wallet login."""
    from luckflow.workflows.hardware_login import run_hardware_login

    _run(run_hardware_login(workers))


@app.command("manual-withdraw")
def manual_withdraw(workers: int = typer.Option(None, "--workers", "-w")):
    """Open browsers and fetch login links for manual withdrawal."""
    from luckflow.workflows.manual_withdraw import run_manual_withdraw

    _run(run_manual_withdraw(workers))


@app.command("profile-list")
def profile_list():
    """Collect all ixBrowser profiles into an Excel sheet (no browser launch)."""
    from luckflow.workflows.profile_list import collect_profile_list

    _run(collect_profile_list())


@app.command("worker-sweep")
def worker_sweep(workers: int = typer.Option(None, "--workers", "-w")):
    """Sweep leftover SOL from worker wallets back to Main."""
    from luckflow.workflows.worker_sweep import run_worker_sweep

    _run(run_worker_sweep(workers))


@app.command()
def dashboard():
    """Launch the web dashboard (Flask backend + optional tunnel)."""
    from luckflow.server.app import run as run_server

    log.configure_stdout()
    run_server()


if __name__ == "__main__":
    app()
