"""Flask backend for the LuckFlow dashboard.

Implements the JSON API consumed by ``dashboard/src/services/api.ts``: task
control, settings, per-mode result tables with summaries, the daily timeline,
and the bonus tracker. Result spreadsheets are read on demand with pandas.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from luckflow.config import settings
from luckflow.core import logging as log
from luckflow.server.tasks import task_manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_results(path: Path) -> list[dict[str, Any]]:
    """Read an ``.xlsx`` result file into JSON-safe rows ([] if missing)."""
    if not path.exists():
        return []
    try:
        frame = pd.read_excel(path, dtype=str).where(lambda d: d.notna(), None)
        return frame.to_dict(orient="records")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Could not read {path.name}", str(exc))
        return []


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    match = re.search(r"-?[\d.,]+", str(value).replace("$", ""))
    if not match:
        return 0.0
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return 0.0


def _count(rows: list[dict], key: str, predicate) -> int:
    return sum(1 for r in rows if predicate(r.get(key)))


def _daily_summary(rows: list[dict]) -> dict:
    success = _count(rows, "RESULT", lambda v: v == "SUCCESS")
    total_profit = sum(_to_float(r.get("BALANCE_DIFFERENCE")) for r in rows)
    total_sol_profit = sum(_to_float(r.get("SOL_BALANCE_DIFFERENCE")) for r in rows)
    total_balance_usd = sum(_to_float(r.get("END_BALANCE")) for r in rows)
    total_balance_sol = sum(_to_float(r.get("END_SOL_BALANCE")) for r in rows)
    total_chest = sum(_to_float(r.get("CHEST_AMOUNT")) for r in rows)
    drops = [_to_float(r.get("BALANCE_DIFFERENCE")) for r in rows if _to_float(r.get("BALANCE_DIFFERENCE")) < 0]
    sol_rate = (total_balance_usd / total_balance_sol) if total_balance_sol else 0.0
    return {
        "total_accounts": len(rows),
        "success_count": success,
        "error_count": len(rows) - success,
        "chest_unavailable": _count(rows, "RESULT", lambda v: v == "CHEST_UNAVAILABLE"),
        "total_profit": round(total_profit, 2),
        "total_sol_profit": round(total_sol_profit, 6),
        "sol_rate": round(sol_rate, 2),
        "total_balance_usd": round(total_balance_usd, 2),
        "total_balance_sol": round(total_balance_sol, 6),
        "avg_drop": round(sum(drops) / len(drops), 2) if drops else 0.0,
        "total_chest_amount": round(total_chest, 2),
        "planned_tomorrow": len(rows),
    }


def _chain_summary(rows: list[dict]) -> dict:
    success = _count(rows, "RESULT", lambda v: v == "SUCCESS")
    return {
        "total_accounts": len(rows),
        "success_count": success,
        "forward_success": _count(rows, "FORWARD_TRANSACTION_STATUS", lambda v: v == "success"),
        "reverse_success": _count(rows, "REVERSE_TRANSACTION_STATUS", lambda v: v == "success"),
    }


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> Flask:
    dashboard_dist = Path(__file__).resolve().parents[3] / "dashboard" / "dist"
    app = Flask(__name__, static_folder=str(dashboard_dist) if dashboard_dist.exists() else None)

    @app.after_request
    def _cors(response):
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.route("/robots.txt")
    def robots():
        return "User-agent: *\nDisallow: /", 200, {"Content-Type": "text/plain"}

    # ---- Task control ----------------------------------------------------
    @app.post("/api/task/start")
    def task_start():
        body = request.get_json(force=True, silent=True) or {}
        result = task_manager.start(body.get("type", ""), int(body.get("workers", 1)))
        return jsonify(result), (200 if result["ok"] else 400)

    @app.post("/api/task/wait-and-start")
    def task_wait_and_start():
        body = request.get_json(force=True, silent=True) or {}
        result = task_manager.start(
            body.get("type", ""), int(body.get("workers", 1)), float(body.get("wait_seconds", 0))
        )
        return jsonify(result), (200 if result["ok"] else 400)

    @app.post("/api/task/stop")
    def task_stop():
        return jsonify(task_manager.stop())

    @app.get("/api/task/status")
    def task_status():
        return jsonify(task_manager.status())

    # ---- Settings (.env read/write) -------------------------------------
    @app.get("/api/settings")
    def get_settings_route():
        return jsonify(_load_env_groups())

    @app.post("/api/settings/save")
    def save_settings_route():
        body = request.get_json(force=True, silent=True) or {}
        _save_env(body)
        return jsonify({"ok": True})

    # ---- Data endpoints --------------------------------------------------
    @app.get("/api/daily")
    def daily():
        rows = _read_results(settings.result_dir / "daily_data" / "result.xlsx")
        return jsonify({"data": rows, "summary": _daily_summary(rows)})

    @app.get("/api/warmup_volume_bonuses")
    def warmup_volume_bonuses():
        rows = _read_results(settings.result_dir / "result_warmup_volume_bonuses.xlsx")
        return jsonify({"data": rows, "summary": _daily_summary(rows)})

    @app.get("/api/withdraw")
    def withdraw():
        rows = _read_results(settings.result_dir / "result_withdraw.xlsx")
        success = _count(rows, "RESULT", lambda v: v == "SUCCESS")
        return jsonify({
            "data": rows,
            "summary": {
                "total_accounts": len(rows),
                "success_count": success,
                "error_count": len(rows) - success,
                "total_withdrawn": round(sum(_to_float(r.get("WITHDRAW_AMOUNT")) for r in rows), 2),
                "total_sol_withdrawn": round(sum(_to_float(r.get("SOL_BALANCE_DIFFERENCE")) for r in rows), 6),
            },
        })

    @app.get("/api/registration")
    def registration():
        rows = _read_results(settings.result_dir / "registration_result.xlsx")
        return jsonify({"data": rows, "summary": _chain_summary(rows)})

    @app.get("/api/renew")
    def renew():
        rows = _read_results(settings.result_dir / "result_renew.xlsx")
        return jsonify({"data": rows, "summary": _chain_summary(rows)})

    @app.get("/api/warmup")
    def warmup():
        rows = _read_results(settings.result_dir / "warmup_registration" / "result_warmup_registration.xlsx")
        success = _count(rows, "RESULT", lambda v: v == "SUCCESS")
        return jsonify({"data": rows, "summary": {"total_accounts": len(rows), "success_count": success}})

    @app.get("/api/daily/timeline")
    def daily_timeline():
        return jsonify(_build_timeline())

    @app.get("/api/bonus_tracker")
    def bonus_tracker():
        from luckflow.storage.bonus_tracker import get_all_bonus_statuses

        statuses = get_all_bonus_statuses()
        data = [{"ud_dir": ud, **info} for ud, info in statuses.items()]
        return jsonify({
            "data": data,
            "summary": {
                "total_accounts": len(data),
                "weekly_available": sum(1 for d in data if d["weekly_countdown"] == "available now!"),
                "monthly_available": sum(1 for d in data if d["monthly_countdown"] == "available now!"),
                "no_data": sum(1 for d in data if d["weekly_countdown"] == "no data"),
            },
        })

    @app.post("/api/restart")
    def restart():
        return jsonify({"ok": True, "message": "Restart is managed by the process supervisor"})

    # ---- Static dashboard (if built) ------------------------------------
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_dashboard(path: str):
        if app.static_folder and (Path(app.static_folder) / path).is_file():
            return send_from_directory(app.static_folder, path)
        if app.static_folder and (Path(app.static_folder) / "index.html").is_file():
            return send_from_directory(app.static_folder, "index.html")
        return jsonify({"service": "luckflow", "dashboard": "run `npm run dev` in dashboard/"})

    return app


def _build_timeline() -> list[dict]:
    """Aggregate dated daily result files into timeline points."""
    daily_dir = settings.result_dir / "daily_data"
    if not daily_dir.exists():
        return []
    timeline = []
    for file in sorted(daily_dir.glob("result_*.xlsx")):
        date = file.stem.replace("result_", "")
        rows = _read_results(file)
        summary = _daily_summary(rows)
        timeline.append({
            "date": date,
            "file": file.name,
            "profit_usd": summary["total_profit"],
            "profit_sol": summary["total_sol_profit"],
            "balance_usd": summary["total_balance_usd"],
            "balance_sol": summary["total_balance_sol"],
            "avg_drop": summary["avg_drop"],
            "total_chest": summary["total_chest_amount"],
        })
    return timeline


def _env_path() -> Path:
    from luckflow.config.settings import PROJECT_ROOT

    return PROJECT_ROOT / ".env"


def _load_env_groups() -> list[dict]:
    """Parse the current ``.env`` into UI setting groups."""
    path = _env_path()
    if not path.exists():
        return []
    groups: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        group = key.replace("LUCKFLOW_", "").split("__", 1)[0] if "__" in key else "GENERAL"
        if value.lower() in ("true", "false"):
            typ = "checkbox"
            value = value.lower() == "true"
        elif re.fullmatch(r"-?\d+", value):
            typ = "number"
            value = int(value)
        elif re.fullmatch(r"-?\d*\.\d+", value):
            typ = "float"
            value = float(value)
        else:
            typ = "text"
        groups.setdefault(group, []).append({"key": key, "value": value, "type": typ})
    return [{"name": name, "settings_list": items} for name, items in groups.items()]


def _save_env(updates: dict[str, Any]) -> None:
    """Write updated key/values back into ``.env`` (creating it from values)."""
    path = _env_path()
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
    for key, value in updates.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        existing[key] = str(value)
    path.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n", encoding="utf-8")


def run() -> None:
    """Run the dashboard server (used by ``luckflow dashboard``)."""
    app = create_app()
    log.success("🎯 Dashboard ready", f"http://{settings.server.host}:{settings.server.port}")
    app.run(host=settings.server.host, port=settings.server.port, debug=settings.server.debug)
