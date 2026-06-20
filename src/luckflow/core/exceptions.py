"""Project-wide exception hierarchy."""

from __future__ import annotations


class LuckFlowError(Exception):
    """Base class for all LuckFlow errors."""


class WorkflowError(LuckFlowError):
    """Raised when a workflow cannot continue."""


class BrowserLaunchError(LuckFlowError):
    """Raised when an ixBrowser profile cannot be launched/attached."""


class ChestProcessingError(LuckFlowError):
    """Raised on an unrecoverable error while claiming a daily chest."""


class OnchainError(LuckFlowError):
    """Raised when an on-chain Solana operation fails."""
