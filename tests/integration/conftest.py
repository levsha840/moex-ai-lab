"""Shared fixtures for M11.5 integration tests."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

STORE_PATH     = PROJECT_ROOT / "data" / "knowledge" / "evolution" / "store.json"
MANIFEST_INDEX = PROJECT_ROOT / "data" / "universe" / "manifest_index.json"
UNIVERSE_JSON  = PROJECT_ROOT / "terminal" / "frontend" / "src" / "data" / "universe_manifest.json"
ALPHA_JSON     = PROJECT_ROOT / "terminal" / "frontend" / "src" / "data" / "alpha_discovery.json"
LEARNING_JSON  = PROJECT_ROOT / "terminal" / "frontend" / "src" / "data" / "learning_state.json"
REPORTS_DIR    = PROJECT_ROOT / "reports"
VB_DIR         = PROJECT_ROOT / "reports" / "visual_backtest"


@pytest.fixture(scope="session")
def store() -> dict:
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def manifest_index() -> dict:
    return json.loads(MANIFEST_INDEX.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def universe_manifest() -> dict:
    return json.loads(UNIVERSE_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def alpha_data() -> dict:
    return json.loads(ALPHA_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def learning_data() -> dict:
    return json.loads(LEARNING_JSON.read_text(encoding="utf-8"))
