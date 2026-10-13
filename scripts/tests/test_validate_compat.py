"""test_validate_compat.py — pytest coverage for L1/L2/L3 failure branches.

Fixtures (scripts/tests/fixtures/*.yaml):
  - manifest-bad-yaml.yaml          -> L1 syntax error  -> exit 3
  - manifest-schema-violation.yaml  -> L2 schema fail   -> exit 4
  - manifest-dup-symbol.yaml        -> L3 rule 1 fail   -> exit 5
  - manifest-dup-macro.yaml         -> L3 rule 2 fail   -> exit 5

Plus the real ../compatibility.yaml should pass end-to-end (exit 0).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent.parent  # ../zmk-keybeacon/
VALIDATE_PY = MODULE_ROOT / "scripts" / "validate_compat.py"
SCHEMA_FILE = MODULE_ROOT / "compatibility.schema.yaml"
FIXTURES = HERE / "fixtures"


def _run(compat_file: Path) -> subprocess.CompletedProcess:
    """Run validate_compat.py with --compat-file pointing to fixture."""
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATE_PY),
            "--compat-file",
            str(compat_file),
            "--schema-file",
            str(SCHEMA_FILE),
        ],
        capture_output=True,
        text=True,
    )


def test_real_manifest_passes() -> None:
    """The real compatibility.yaml must pass L1/L2/L3 (modulo rule 4 which needs the
    real used_in files to exist — this is the case in a normal checkout)."""
    real = MODULE_ROOT / "compatibility.yaml"
    result = _run(real)
    assert result.returncode == 0, (
        f"real manifest failed: stdout={result.stdout} stderr={result.stderr}"
    )
    assert "manifest OK" in result.stdout


@pytest.mark.parametrize(
    "fixture, expected_rc, must_contain",
    [
        ("manifest-bad-yaml.yaml", 3, "L1 YAML syntax"),
        ("manifest-schema-violation.yaml", 4, "L2 schema"),
        ("manifest-dup-symbol.yaml", 5, "L3 rule 1"),
        ("manifest-dup-macro.yaml", 5, "L3 rule 2"),
    ],
)
def test_broken_fixture_exits_with_correct_code(
    fixture: str, expected_rc: int, must_contain: str
) -> None:
    result = _run(FIXTURES / fixture)
    assert result.returncode == expected_rc, (
        f"{fixture}: expected exit {expected_rc}, got {result.returncode}; "
        f"stdout={result.stdout} stderr={result.stderr}"
    )
    assert must_contain in result.stderr, (
        f"{fixture}: stderr should contain {must_contain!r}, got {result.stderr!r}"
    )
