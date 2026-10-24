"""Tests for src/run_experiments.py helpers."""

import json
import sys
from pathlib import Path

import pytest

from src import run_experiments as rx

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "mvp.json").read_text())


def test_a_crashing_run_is_reported_not_raised():
    rx._init_worker(CONFIG)
    problem = {"problem_id": "x/y/0", "map_set": "x", "map_name": "y",
               "sx": 0, "sy": 0, "gx": 1, "gy": 0, "bfs_len": 1}
    status, run_id, message = rx._run_job(("no_such_map.map", problem, "astar_lazy", "none"))
    assert status == "error" and run_id == "x/y/0|astar_lazy|none"
    assert "FileNotFoundError" in message


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_keep_awake_request_succeeds_on_windows():
    assert rx.keep_windows_awake() is True
