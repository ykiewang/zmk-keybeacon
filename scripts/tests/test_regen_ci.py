"""test_regen_ci.py — parametric test over compatibility.yaml:ci variants.

Each test synthesises a compat dict in memory, runs regen_ci.render(),
and asserts the rendered workflow yaml contains the expected fields.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent.parent
REGEN_PY = MODULE_ROOT / "scripts" / "regen_ci.py"


def _load_regen_ci_module():
    spec = importlib.util.spec_from_file_location("regen_ci", REGEN_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules["regen_ci"] = module
    spec.loader.exec_module(module)
    return module


regen_ci = _load_regen_ci_module()


def _base_compat() -> dict:
    """Minimal compat dict covering the fields render() touches."""
    return {
        "module_version": "1.1.4",
        "ci": {
            "schedule": "0 6 * * *",
            "matrix": {
                "zmk_refs": ["main", "4dd95d7", "e844eca2"],
                "shields": ["totem_left"],
            },
            "on_schedule_failure": {
                "create_issue": True,
                "issue_label": "compat-break",
            },
        },
    }


def test_default_matrix_present_in_rendered_yaml() -> None:
    rendered = regen_ci.render(_base_compat())
    assert 'cron: "0 6 * * *"' in rendered
    assert "zmk_ref: [main, 4dd95d7, e844eca2]" in rendered
    assert "shield:  [totem_left]" in rendered
    assert "fail-fast: false" in rendered


def test_custom_schedule_round_trip() -> None:
    compat = _base_compat()
    compat["ci"]["schedule"] = "15 2 * * 1"
    rendered = regen_ci.render(compat)
    assert 'cron: "15 2 * * 1"' in rendered


def test_custom_matrix_round_trip() -> None:
    compat = _base_compat()
    compat["ci"]["matrix"]["zmk_refs"] = ["main", "deadbee"]
    compat["ci"]["matrix"]["shields"] = ["corne_left", "totem_left"]
    rendered = regen_ci.render(compat)
    assert "zmk_ref: [main, deadbee]" in rendered
    assert "shield:  [corne_left, totem_left]" in rendered


def test_custom_issue_label_round_trip() -> None:
    compat = _base_compat()
    compat["ci"]["on_schedule_failure"]["issue_label"] = "zmk-upstream-broke-us"
    rendered = regen_ci.render(compat)
    assert "labels: 'zmk-upstream-broke-us'" in rendered
    assert "labels: ['zmk-upstream-broke-us']" in rendered


def test_header_has_warning_about_hand_editing() -> None:
    rendered = regen_ci.render(_base_compat())
    assert "scripts/regen_ci.py 从 compatibility.yaml 派生" in rendered
    assert "请勿手改" in rendered


def test_file_issue_job_guarded_by_schedule_event() -> None:
    rendered = regen_ci.render(_base_compat())
    assert "if: failure() && github.event_name == 'schedule'" in rendered


def test_defaults_when_ci_block_absent() -> None:
    """compatibility.yaml with no `ci:` block should fall back to spec defaults."""
    rendered = regen_ci.render({"module_version": "1.1.4"})
    assert 'cron: "0 6 * * *"' in rendered
    assert "zmk_ref: [main, 4dd95d7, e844eca2]" in rendered
    assert "shield:  [totem_left]" in rendered
    assert "labels: 'compat-break'" in rendered
