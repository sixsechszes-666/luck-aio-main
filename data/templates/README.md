# Account data templates

Operator data is **not** committed (see `.gitignore`). Create the spreadsheets
your chosen modes need in `data/` (one row per profile).

| File | Used by | Required columns |
| --- | --- | --- |
| `data_daily.xlsx` | daily, warmup-volume, manual-withdraw, worker-sweep | `UD_DIR`, `LINK` (+ `PRIVATE_KEY_MAIN/MASTER/WORKER`, `WALLET_ADDRESS` for on-chain) |
| `data_for_reg.xlsx` | registration, renew | `UD_DIR`, `LINK`, `WALLET_ADDRESS`, `PRIVATE_KEY_MASTER`, `PRIVATE_KEY_WORKER` (+ `PRIVATE_KEY_MAIN`) |
| `data_for_reg_warmup.xlsx` | warmup-registration | `UD_DIR`, `LINK`, `WALLET_ADDRESS` |
| `data_withdraw.xlsx` | withdraw | `UD_DIR`, `LINK`, `WALLET_ADDRESS`, `PRIVATE_KEY_*` |
| `data_hardware.xlsx` | hardware-login | `UD_DIR`, `LINK` |
| `data_for_fix.xlsx` | extension-fix | `UD_DIR`, `LINK`, `SEED_PHRASE` |
| `data.xlsx` | browser-setup | `UD_DIR`, `LINK`, `SEED_PHRASE` |

Common columns:

- `UD_DIR` — ixBrowser profile id (integer).
- `LINK` — the account's Luck.io mobile-login URL.
- `WALLET_ADDRESS` — the account's on-chain wallet (target for funding).
- `PRIVATE_KEY_MAIN` / `PRIVATE_KEY_MASTER` / `PRIVATE_KEY_WORKER` — base58 keys
  for the funding chain (optional; omit to disable on-chain steps).
- `SEED_PHRASE` — Solflare recovery phrase (wallet import modes only).
