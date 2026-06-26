"""Shared domain primitives used across multiple layers."""

from __future__ import annotations

from enum import Enum


class OrderSide(str, Enum):
    """Canonical order side used by risk, costs, and paper layers."""

    BUY = "BUY"
    SELL = "SELL"
