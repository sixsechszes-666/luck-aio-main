# LuckFlow architecture

## Goals

LuckFlow automates many isolated browser profiles against Luck.io and settles
funds on Solana. The design optimises for three things:

1. **Bounded concurrency** — run N profiles at once without melting the host or
   the upstream APIs.
2. **Isolation** — one account's failure must never abort the batch.
3. **Separation of concerns** — page mechanics, blockchain, domain logic,
   orchestration, persistence and presentation are independent layers.

## Layered dependency graph

Dependencies point **downward only** (no cycles):

```
cli / server  →  workflows  →  platform  →  browser, blockchain  →  core  →  config
                                  │                                   ▲
                                  └──────────  storage  ─────────────┘
```

- **config** — `pydantic-settings`. Pure data; depends on nothing.
- **core** — logging facade, `WorkerPool`, `Workflow` ABC, typed models, utils,
  exceptions. Depends only on config.
- **browser** — ixBrowser lifecycle, proxies, extensions, QR/session, captcha.
- **blockchain** — Solana transfers + temp-wallet chains.
- **platform** — Luck.io domain built on browser+blockchain (auth, balance,
  games, chest, wallet flows, withdraw, renew).
- **workflows** — one `Workflow` subclass per mode; composes platform actions.
- **storage** — spreadsheet IO, stats, run-state, bonus tracker (leaf utility).
- **server / cli** — entry points; never imported by lower layers.

## The two abstractions that carry the design

### `WorkerPool` (`core/runner.py`)

The legacy code re-implemented `Semaphore` + `gather` + checkpoint **eight
times**. `WorkerPool.run(items, handler)` does it once:

- a single semaphore bounds concurrency,
- each item is wrapped so an exception becomes the *result value* (à la
  `gather(return_exceptions=True)`) and is logged, never propagated,
- results preserve input order,
- a `checkpoint` callback persists partial results every N completions.

### `Workflow` (`core/workflow.py`)

A template method: `run()` = `load_accounts()` → `WorkerPool.run(process_account)`
→ `save_results()` → `summarize()`. A concrete mode implements only
`load_accounts` and `process_account`; everything else is inherited. Adding a new
mode is a small subclass, not another 150-line orchestrator.

## Data flow for one account (daily)

```
spreadsheet row ──► Account (validated, typed)
       │
       ▼ process_account
 launch ixBrowser profile (browser)
       ▼
 authenticate + read balance (platform.auth / platform.balance)
       ▼
 renew play timer if needed (platform.renew → blockchain chains)
       ▼
 claim chest (platform.chest) ──► bonus tracker (storage)
       ▼
 play a game (platform.games)
       ▼
 read final balance, compute delta ──► AccountResult
       ▼
 cleanup browser (always, in finally)
       ▼
 WorkerPool checkpoints results ──► Excel (storage.stats) ──► dashboard (server)
```

## Configuration & secrets

Everything is environment-driven via `LUCKFLOW_*` variables (nested with `__`).
No secret has a real default; required secrets raise a clear error at the point
of use. `.env` is gitignored; `.env.example` documents every key.

## Logging & the dashboard

`core/logging` is the only place that writes to the console. Its `LogHub` lets
the Flask backend subscribe to an ANSI-stripped copy of every line, so the React
dashboard streams live logs while a workflow runs. The `TaskManager`
(`server/tasks.py`) runs one workflow at a time in a background thread with its
own event loop and exposes status the dashboard polls.

## Testing

Pure logic (proxy parsing, balance math, the `WorkerPool`, cooldown state, the
models' wire-format) is unit-tested without a browser. Browser/blockchain calls
are integration concerns exercised against the live stack.
