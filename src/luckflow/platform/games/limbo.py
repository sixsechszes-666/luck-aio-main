"""Limbo game — a multiplier game over the shared engine in :mod:`base`."""

from __future__ import annotations

import random
from typing import Any

from luckflow.config import settings
from luckflow.platform.games.base import (
    LIMBO_INTER_ROUND_DELAY,
    play_multiplier_game,
    setup_multiplier_game,
)


async def limbo_setup(page, multiplier: float | None = None, timeout: int = 30000) -> bool:
    if multiplier is None:
        multiplier = round(
            random.uniform(settings.game.limbo_multiplier_min, settings.game.limbo_multiplier_max), 2
        )
    return await setup_multiplier_game(page, "https://luck.io/limbo", "Limbo", multiplier, timeout)


async def limbo_play(
    page,
    min_rounds: int | None = None,
    max_rounds: int | None = None,
    balance_check_delay: float | None = None,
    balance_timeout: int = 30000,
    enable_balance_check: bool | None = None,
) -> dict[str, Any]:
    game = settings.game
    return await play_multiplier_game(
        page,
        "Limbo",
        min_rounds if min_rounds is not None else game.limbo_min_rounds,
        max_rounds if max_rounds is not None else game.limbo_max_rounds,
        balance_check_delay=balance_check_delay
        if balance_check_delay is not None
        else game.limbo_balance_check_delay,
        inter_round_delay=LIMBO_INTER_ROUND_DELAY,
        balance_timeout=balance_timeout,
        enable_balance_check=enable_balance_check
        if enable_balance_check is not None
        else game.enable_balance_check,
    )
