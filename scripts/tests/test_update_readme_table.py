"""test_update_readme_table.py — unit tests for the Compatibility table generator.

The real tests run update-readme-table.py's pure functions against synthetic
inputs (tag lists + compat dicts) so we don't need to construct fake git repos.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent.parent
SCRIPT = MODULE_ROOT / "scripts" / "update-readme-table.py"


def _load_update_readme_table():
    spec = importlib.util.spec_from_file_location("update_readme_table", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["update_readme_table"] = module
    spec.loader.exec_module(module)
    return module


urt = _load_update_readme_table()


def test_apply_to_readme_replaces_between_markers() -> None:
    original = (
        "# Hello\n\n"
        "## Compatibility\n\n"
        f"{urt.BEGIN}\n"
        "OLD CONTENT\n"
        f"{urt.END}\n\n"
        "## More\n"
    )
    new_body = "\n| tag | range |\n|---|---|\n| v1.0 | abc..def |\n"
    out = urt.apply_to_readme(original, new_body)
    assert "OLD CONTENT" not in out
    assert "| v1.0 | abc..def |" in out
    assert urt.BEGIN in out and urt.END in out
    # Rest of README is intact
    assert "# Hello" in out and "## More" in out


def test_apply_to_readme_raises_when_markers_missing() -> None:
    original = "# Hello without markers\n"
    with pytest.raises(RuntimeError, match="COMPAT:BEGIN"):
        urt.apply_to_readme(original, "anything")


def test_apply_to_readme_idempotent() -> None:
    original = (
        "pre\n"
        f"{urt.BEGIN}\n"
        "existing\n"
        f"{urt.END}\n"
        "post"
    )
    body = "\n| x | y |\n"
    once = urt.apply_to_readme(original, body)
    twice = urt.apply_to_readme(once, body)
    assert once == twice


def test_live_readme_check_mode_passes() -> None:
    """The committed README must stay in sync with the current compat yaml,
    assuming no new tag is being staged."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--pending-tag", "v1.1.4"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"README out of sync: stdout={result.stdout} stderr={result.stderr}"
    )
