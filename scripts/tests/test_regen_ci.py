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
    # shields field is kept in schema (future per-shield build revival) but
    # the symbol-probe CI does not consume it; it should NOT appear in the
    # rendered workflow.
    assert "shield:" not in rendered
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
    # shields are inert in the symbol-probe CI — editing them must not
    # affect the rendered yaml.
    assert "corne_left" not in rendered
    assert "totem_left" not in rendered


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
    assert "shield:" not in rendered
    assert "labels: 'compat-break'" in rendered


def test_symbol_probe_job_shape() -> None:
    """Guard against accidental revival of the heavy west-build matrix:
    the generated workflow must call check_zmk_compat.py, not run a full
    west build."""
    rendered = regen_ci.render(_base_compat())
    assert "symbol-probe:" in rendered
    assert "check_zmk_compat.py" in rendered
    # Negative checks — none of the former heavy-build infrastructure as
    # YAML keys / shell commands. The symbol-probe comment legitimately
    # mentions "west build" in prose so we must check for actual job
    # artefacts, not substrings:
    assert "image: zmkfirmware/zmk-dev-arm" not in rendered
    assert "west init -l app" not in rendered
    assert "west build -s app" not in rendered
    assert "CONFIG_ZMK_KEYBEACON=y" not in rendered
    assert "-b nice_nano_v2" not in rendered
    assert "-b xiao_ble" not in rendered
