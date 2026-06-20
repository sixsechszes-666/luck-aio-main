"""Luck.io games: Mines, Dice, Limbo, Hell Spin, plus selection/volume logic."""

from luckflow.platform.games.base import click_random_in_area, place_random_bet
from luckflow.platform.games.dice import dice_play, dice_setup
from luckflow.platform.games.dispatch import (
    execute_game_logic,
    execute_game_logic_volumes,
    perform_dodep,
)
from luckflow.platform.games.hellspin import hell_play, hell_setup
from luckflow.platform.games.limbo import limbo_play, limbo_setup
from luckflow.platform.games.mines import mines_play, mines_setup

__all__ = [
    "mines_setup",
    "mines_play",
    "dice_setup",
    "dice_play",
    "limbo_setup",
    "limbo_play",
    "hell_setup",
    "hell_play",
    "execute_game_logic",
    "execute_game_logic_volumes",
    "perform_dodep",
    "place_random_bet",
    "click_random_in_area",
]
