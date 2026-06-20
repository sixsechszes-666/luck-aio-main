# LuckFlow

> Async, multi-account **browser-automation orchestration platform** for [Luck.io](https://luck.io)
> - an on-chain Web3 gambling platform on Solana - with a bounded-concurrency worker pool,
> on-chain settlement, and a live React dashboard.

[Luck.io](https://luck.io) is a crypto (Solana) gambling/gaming platform where balances and payouts
live on-chain. LuckFlow automates routine activity across many accounts on it: it drives hundreds of
isolated [ixBrowser](https://www.ixbrowser.com/) profiles through
[Playwright/patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright), coordinates them with a
reusable async worker pool, funds and settles wallets on Solana through disposable temp-wallet chains,
and streams progress to a TypeScript/React control panel.

---

## Why it exists (engineering highlights)

This is a portfolio refactor of a working automation suite. The emphasis is on **architecture**:

| Concern | Approach |
| --- | --- |
| **Concurrency** | One generic `WorkerPool` (`core/runner.py`) - semaphore + `gather` + per-item exception isolation + periodic checkpointing. Replaces 8 copy-pasted orchestration blocks. |
| **Extensibility** | Every mode is a `Workflow` subclass (`core/workflow.py`) implementing `load_accounts` / `process_account`; the load→run→checkpoint→summarize control flow lives once in the base. |
| **Layering** | Strict dependency direction: `workflows → platform → {browser, blockchain} → core → config`. No `import *`, no circular imports, no "pass functions as args to dodge cycles". |
| **Config & secrets** | Typed `pydantic-settings` (`config/settings.py`), env-driven, **zero secret defaults**. `.env.example` documents every key. |
| **Observability** | A single logging facade (`core/logging.py`) with a `LogHub` fan-out so the dashboard can stream a clean, ANSI-stripped copy of every line. |
| **Typed domain** | `Account` / `AccountResult` / `WorkflowSummary` dataclasses (`core/models.py`) instead of stringly-typed dicts - while preserving the legacy wire format for Excel/dashboard parity. |
| **Tooling** | `pyproject.toml` with `ruff` + `mypy` + `pytest`; unit tests for the pure logic. |

## Architecture

```
                     ┌────────────────────┐        ┌──────────────────────┐
   CLI (Typer)  ───► │     workflows/     │ ─────► │   React dashboard    │
   luckflow daily    │  daily, withdraw,  │  HTTP  │ (Vite + Tailwind +   │
                     │  renew, warmup …   │ ◄───── │  shadcn/ui)          │
                     └─────────┬──────────┘        └──────────┬───────────┘
                               │                              │
                     ┌─────────▼──────────┐        ┌──────────▼───────────┐
                     │     platform/      │        │       server/        │
                     │ auth · balance ·   │        │  Flask API · tasks · │
                     │ games · chest ·    │        │  tunnels             │
                     │ wallet · withdraw  │        └──────────────────────┘
                     └────┬──────────┬────┘
                          │          │
             ┌────────────▼───┐  ┌───▼─────────────┐
             │   browser/     │  │   blockchain/   │
             │ ixbrowser ·    │  │ solana transfers│
             │ session·captcha│  │ + temp chains   │
             └────────┬───────┘  └───────┬─────────┘
                      │                  │
                      └────────┬─────────┘
                       ┌───────▼────────┐   ┌─────────────┐
                       │     core/      │   │   config/   │
                       │ runner·models· │◄──│  settings   │
                       │ logging·utils  │   │ (pydantic)  │
                       └────────────────┘   └─────────────┘
                              ▲
                       ┌──────┴───────┐
                       │   storage/   │  accounts · stats · state · bonus_tracker
                       └──────────────┘
```

## Layout

```
src/luckflow/
  cli.py            Typer CLI, one subcommand per mode
  config/           pydantic-settings (typed, env-driven, no secrets)
  core/             logging, WorkerPool, Workflow ABC, models, utils, exceptions
  browser/          ixBrowser lifecycle, proxies, extensions, QR/session, captcha
  blockchain/       Solana transfers, wSOL unwrap, forward/reverse temp-wallet chains
  platform/         Luck.io domain: auth, balance, games/, chest, wallet connect, withdraw, renew
  workflows/        one module per operating mode (Workflow subclasses)
  storage/          spreadsheet IO, stats, run-state, bonus tracker
  server/           Flask dashboard API, task manager, tunnels
  notifications/    Telegram bot
dashboard/          React + TypeScript control panel (Vite)
tests/              pytest unit suite
```

## Quick start

```bash
# 1. Backend
python -m venv .venv && . .venv/Scripts/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env          # then fill in your own keys/secrets

luckflow --help               # list all modes
luckflow daily --workers 3    # run the daily routine
luckflow dashboard            # launch the web control panel

# 2. Dashboard (separate terminal)
cd dashboard && npm install && npm run dev
```

Account data lives in `data/*.xlsx` (gitignored). Column templates are in `data/templates/`.

## Configuration

All settings are environment variables prefixed `LUCKFLOW_`, with `__` for nested groups
(e.g. `LUCKFLOW_SOLANA__RPC_URL`, `LUCKFLOW_CONCURRENCY__MAX_WORKERS`). See `.env.example`.
Secrets (wallet keys, captcha keys, Telegram token) default to empty and fail loudly only when a
feature that needs them is used - nothing sensitive is ever committed.

## Tests

```bash
ruff check . && mypy src/luckflow && pytest
```

## Disclaimer

Built as a software-engineering portfolio piece demonstrating async orchestration, layered design
and full-stack integration. Use responsibly and in accordance with the target platform's terms.
