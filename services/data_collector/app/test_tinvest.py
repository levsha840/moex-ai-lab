"""Manual integration check for T-Invest sandbox connection.

This file is intentionally skipped when SDK import or token is missing.
It should not block unit tests for the MOEX AI LAB core.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.integration
def test_tinvest_sdk_import_and_token_present():
    token = os.getenv("TINKOFF_INVEST_TOKEN") or os.getenv("T_INVEST_TOKEN")
    if not token:
        pytest.skip("T-Invest token is not configured in .env")

    try:
        # Legacy SDK import path. New package distributions may expose a different path;
        # this check is kept non-blocking until the collector adapter is finalized.
        from tinkoff.invest import Client  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.skip(f"T-Invest SDK import path is unavailable: {exc}")

    assert Client is not None
