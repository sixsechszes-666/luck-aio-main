"""Unit tests for the typed domain models."""

from __future__ import annotations

from luckflow.core.models import Account, AccountResult, ResultStatus, WorkflowSummary


def test_account_result_preserves_legacy_keys():
    result = AccountResult.new("Worker-001")
    result.RESULT = ResultStatus.SUCCESS.value
    result.START_BALANCE = "10,00"
    data = result.to_dict()
    # Legacy wire-format keys must be present for Excel/dashboard parity.
    for key in ("WORKER_ID", "UD_DIR", "RESULT", "START_BALANCE", "WITHDRAW_RESULT"):
        assert key in data
    assert data["RESULT"] == "SUCCESS"


def test_account_result_extra_is_flattened():
    result = AccountResult.new("W")
    result.extra["WALLET_ADDRESS"] = "abc"
    data = result.to_dict()
    assert data["WALLET_ADDRESS"] == "abc"
    assert "extra" not in data


def test_account_get_reads_raw_row():
    account = Account(profile_id=1, user_data_dir="1", link="x", raw={"PRIVATE_KEY_MAIN": "k"})
    assert account.get("PRIVATE_KEY_MAIN") == "k"
    assert account.get("MISSING", "default") == "default"


def test_workflow_summary_counts():
    results = []
    for status in (ResultStatus.SUCCESS, ResultStatus.SUCCESS, ResultStatus.AUTH_FAILED):
        r = AccountResult.new("W")
        r.RESULT = status.value
        results.append(r)
    summary = WorkflowSummary.from_results(results)
    assert summary.total == 3
    assert summary.succeeded == 2
    assert summary.failed == 1
