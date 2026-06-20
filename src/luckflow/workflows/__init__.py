"""Operating modes, one module per workflow (each a :class:`Workflow` subclass)."""

from luckflow.workflows.browser_setup import run_browser_setup
from luckflow.workflows.daily import run_daily
from luckflow.workflows.extension_fix import run_extension_fix
from luckflow.workflows.hardware_login import run_hardware_login
from luckflow.workflows.manual_withdraw import run_manual_withdraw
from luckflow.workflows.profile_list import collect_profile_list
from luckflow.workflows.registration import run_registration
from luckflow.workflows.renew import run_renew
from luckflow.workflows.warmup_registration import run_warmup_registration
from luckflow.workflows.warmup_volume import run_warmup_volume
from luckflow.workflows.withdraw import run_withdraw
from luckflow.workflows.worker_sweep import run_worker_sweep

__all__ = [
    "run_daily",
    "run_warmup_volume",
    "run_extension_fix",
    "run_registration",
    "run_warmup_registration",
    "run_withdraw",
    "run_renew",
    "run_browser_setup",
    "run_hardware_login",
    "run_manual_withdraw",
    "collect_profile_list",
    "run_worker_sweep",
]
