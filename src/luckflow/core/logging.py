"""Coloured, worker-aware console logging with an optional web sink.

This is a thin, dependency-free logging facade. It keeps the friendly emoji UX
of the original project but lives in a single module instead of being scattered
through business logic. The :class:`LogHub` lets the web dashboard subscribe to a
clean (ANSI-stripped) copy of every line.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


class LogHub:
    """Fan-out sink: business code logs once, subscribers (e.g. the dashboard) receive a clean copy."""

    _subscribers: list[Callable[[str], None]] = []

    @classmethod
    def subscribe(cls, callback: Callable[[str], None]) -> None:
        if callback not in cls._subscribers:
            cls._subscribers.append(callback)

    @classmethod
    def emit(cls, message: str) -> None:
        clean = _ANSI_RE.sub("", message)
        for cb in cls._subscribers:
            try:
                cb(clean)
            except Exception:  # subscribers must never break logging
                pass


def configure_stdout() -> None:
    """Force UTF-8 stdout/stderr so emoji never crash a legacy Windows console."""
    import sys

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def _safe_print(message: str = "") -> None:
    """Print that survives Windows console quirks (OSError, non-UTF-8 codecs)."""
    try:
        print(message)
    except OSError:
        pass
    except UnicodeEncodeError:
        import sys

        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        try:
            print(message.encode(encoding, errors="replace").decode(encoding))
        except Exception:
            pass


def _ts() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


def _render(message: str, value: str | None) -> str:
    if value:
        return f"{Colors.GRAY}{_ts()}{Colors.RESET} {message}: {Colors.WHITE}{Colors.BOLD}{value}{Colors.RESET}"
    return f"{Colors.GRAY}{_ts()}{Colors.RESET} {message}"


def _publish(message: str) -> None:
    _safe_print(message)
    LogHub.emit(message)


# --- Public logging API -----------------------------------------------------
def info(message: str, value: str | None = None) -> None:
    _publish(_render(message, value))


def success(message: str, value: str | None = None) -> None:
    body = (
        f"{Colors.GRAY}{_ts()}{Colors.RESET} {Colors.GREEN}{message}{Colors.RESET}"
        + (f": {Colors.WHITE}{value}{Colors.RESET}" if value else "")
    )
    _publish(body)


def warning(message: str, value: str | None = None) -> None:
    body = (
        f"{Colors.GRAY}{_ts()}{Colors.RESET} {Colors.YELLOW}{message}{Colors.RESET}"
        + (f": {Colors.GRAY}{value}{Colors.RESET}" if value else "")
    )
    _publish(body)


def error(message: str, detail: str | None = None) -> None:
    import sys
    import traceback

    body = (
        f"{Colors.GRAY}{_ts()}{Colors.RESET} {Colors.RED}{message}{Colors.RESET}"
        + (f": {Colors.GRAY}{detail}{Colors.RESET}" if detail else "")
    )
    exc_type, exc_value, exc_tb = sys.exc_info()
    if exc_value is not None:
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).strip()
        body += f"\n{Colors.GRAY}{tb}{Colors.RESET}"
    _publish(body)


def step(worker_id: str, emoji: str, message: str, value: str | None = None) -> None:
    """Log a line tagged with the worker/profile that produced it."""
    prefix = f"{Colors.CYAN}[{worker_id}]{Colors.RESET}"
    body = f"{Colors.GRAY}{_ts()}{Colors.RESET} {emoji} {prefix} {message}"
    if value:
        body += f": {Colors.WHITE}{Colors.BOLD}{value}{Colors.RESET}"
    _publish(body)


def detail(label: str, value: str = "") -> None:
    body = f"               {Colors.GRAY}•{Colors.RESET} {label}"
    if value:
        body += f": {Colors.WHITE}{value}{Colors.RESET}"
    _publish(body)


def separator(char: str = "─", length: int = 80) -> None:
    _publish(f"{Colors.GRAY}{char * length}{Colors.RESET}")


def header(title: str) -> None:
    _safe_print()
    separator("═")
    _publish(f"{Colors.WHITE}{Colors.BOLD}{title.center(80)}{Colors.RESET}")
    separator("═")
    _safe_print()


def progress(current: int, total: int, label: str = "", status: str = "") -> None:
    pct = (current / total * 100) if total else 0
    filled = int(20 * current / total) if total else 0
    bar = f"{Colors.GREEN}{'█' * filled}{Colors.GRAY}{'░' * (20 - filled)}{Colors.RESET}"
    status_text = f" {Colors.GRAY}{status}{Colors.RESET}" if status else ""
    _publish(
        f"{Colors.GRAY}{_ts()}{Colors.RESET} {bar} {Colors.WHITE}{current}/{total}{Colors.RESET} "
        f"({pct:.0f}%) {Colors.CYAN}{label}{Colors.RESET}{status_text}"
    )


def transaction(tx_type: str, from_addr: str, to_addr: str, amount: float, signature: str) -> None:
    """Log a Solana transfer with a Solscan link."""

    def short(addr: str) -> str:
        s = str(addr or "Unknown")
        return f"{s[:8]}...{s[-4:]}" if len(s) > 12 else s

    line1 = (
        f"{Colors.GRAY}{_ts()}{Colors.RESET} {Colors.CYAN}{tx_type}{Colors.RESET} "
        f"{Colors.GRAY}{short(from_addr)}{Colors.RESET} → {Colors.GRAY}{short(to_addr)}{Colors.RESET} "
        f"{Colors.WHITE}{Colors.BOLD}{amount:.9f} SOL{Colors.RESET}"
    )
    line2 = f"{Colors.GRAY}          TX: {Colors.BLUE}{Colors.BOLD}https://solscan.io/tx/{signature}{Colors.RESET}"
    _publish(line1)
    _publish(line2)
