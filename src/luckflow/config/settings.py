"""Typed application settings.

All configuration is loaded from environment variables (and an optional ``.env``
file) using ``pydantic-settings``. Nested groups are addressed with the ``__``
delimiter, e.g. ``LUCKFLOW_SOLANA__RPC_URL``.

Unlike the original ``config.py``, **no secret has a real default value**.
Secrets default to empty and are validated lazily by the code paths that need
them, so the project is safe to publish.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class SolanaSettings(BaseModel):
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    helius_rpc_url: str = ""
    transaction_timeout: int = 300
    balance_check_timeout: int = 300
    balance_check_interval: float = 1.0
    transaction_delay: float = 0.0
    num_temp_wallets: int = 3
    use_master_wallet: bool = False
    onchain_balance_check_interval: float = 0.1
    onchain_balance_check_timeout: int = 300
    onchain_max_retries: int = 5
    onchain_speed_mode: str = "FAST"


class FundingSettings(BaseModel):
    """SOL amounts used to fund worker wallets."""

    min_amount: float = 0.013
    max_amount: float = 0.02
    registration_min: float = 0.012
    registration_max: float = 0.0222
    max_attempts: int = 5
    enabled: bool = True


class CaptchaSettings(BaseModel):
    sonic_api_key: str = ""
    fox_api_key: str = ""


class SolflareSettings(BaseModel):
    password: str = ""
    return_wallet_address: str = ""


class BrowserSettings(BaseModel):
    max_retries: int = 3
    retry_delay: int = 20
    timeout: int = 30_000
    load_timeout: int = 40_000


class GameSettings(BaseModel):
    # Mines
    mines_divide_clicks: int = 5
    mines_count: int = 64
    mines_safe_cells: int = 63
    mines_min_rounds: int = 4
    mines_max_rounds: int = 8
    mines_min_clicks: int = 1
    mines_max_clicks: int = 2
    # Dice
    dice_divide_clicks: int = 5
    dice_multiplier_min: float = 1.02
    dice_multiplier_max: float = 1.08
    dice_min_rounds: int = 4
    dice_max_rounds: int = 6
    dice_balance_check_delay: float = 5.0
    # Limbo
    limbo_multiplier_min: float = 1.02
    limbo_multiplier_max: float = 1.08
    limbo_min_rounds: int = 4
    limbo_max_rounds: int = 6
    limbo_balance_check_delay: float = 5.0
    # Hell Spin
    hell_multiplier_min: float = 1.02
    hell_multiplier_max: float = 1.08
    hell_min_rounds: int = 4
    hell_max_rounds: int = 6
    hell_balance_check_delay: float = 5.0
    # Shared
    enable_balance_check: bool = True
    min_balance: float = 0.11


class ConcurrencySettings(BaseModel):
    max_workers: int = 3
    max_withdraw: int = 3
    max_timer_check: int = 3
    max_onchain: int = 3


class DailySettings(BaseModel):
    interval_hours: int = 24
    cooldown_enabled: bool = False


class WithdrawSettings(BaseModel):
    min_balance_to_start: float = 0.35
    keep_min: float = 0.15
    keep_max: float = 0.25
    in_daily_enabled: bool = False
    daily_min_balance: float = 1.0
    dice_sides: int = 6
    dice_increment: str = "random"
    daily_trigger: str = "random"


class ServerSettings(BaseModel):
    host: str = "localhost"
    port: int = 5000
    debug: bool = False
    tunnel_enabled: bool = False
    dashboard_secret_token: str = ""


class TelegramSettings(BaseModel):
    bot_token: str = ""
    user_id: str = ""


class Settings(BaseSettings):
    """Root settings object. Access via :func:`get_settings` / ``settings``."""

    model_config = SettingsConfigDict(
        env_prefix="LUCKFLOW_",
        env_nested_delimiter="__",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"
    result_dir: Path = PROJECT_ROOT / "result"

    # Wallet secrets (empty == feature disabled, validated at point of use)
    main_wallet_private_key: str = ""
    master_wallet_private_key: str = ""

    # Misc
    debug_mode: bool = False
    save_stats_every_n: int = 5

    # Nested groups
    solana: SolanaSettings = Field(default_factory=SolanaSettings)
    funding: FundingSettings = Field(default_factory=FundingSettings)
    captcha: CaptchaSettings = Field(default_factory=CaptchaSettings)
    solflare: SolflareSettings = Field(default_factory=SolflareSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    game: GameSettings = Field(default_factory=GameSettings)
    concurrency: ConcurrencySettings = Field(default_factory=ConcurrencySettings)
    daily: DailySettings = Field(default_factory=DailySettings)
    withdraw: WithdrawSettings = Field(default_factory=WithdrawSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)

    # --- Convenience accessors -------------------------------------------
    @property
    def excel_daily(self) -> Path:
        return self.data_dir / "data_daily.xlsx"

    @property
    def excel_registration(self) -> Path:
        return self.data_dir / "data_for_reg.xlsx"

    @property
    def excel_warmup_registration(self) -> Path:
        return self.data_dir / "data_for_reg_warmup.xlsx"

    @property
    def excel_hardware(self) -> Path:
        return self.data_dir / "data_hardware.xlsx"

    @property
    def excel_withdraw(self) -> Path:
        return self.data_dir / "data_withdraw.xlsx"

    @property
    def excel_extension_fix(self) -> Path:
        return self.data_dir / "data_for_fix.xlsx"

    @property
    def result_file(self) -> Path:
        return self.result_dir / "result.xlsx"

    @property
    def daily_run_state_file(self) -> Path:
        return self.data_dir / "state" / "last_daily_run.json"

    def require_main_wallet_key(self) -> str:
        """Return the main wallet key or raise a clear error if unset."""
        if not self.main_wallet_private_key:
            raise RuntimeError(
                "LUCKFLOW_MAIN_WALLET_PRIVATE_KEY is not set — required for on-chain funding."
            )
        return self.main_wallet_private_key


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide, cached settings instance."""
    return Settings()


# Eagerly-created singleton for ergonomic imports (`from ... import settings`).
settings = get_settings()
