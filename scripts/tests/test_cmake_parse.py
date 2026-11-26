"""test_cmake_parse.py — pytest wrapper around scripts/tests/cmake_parse_smoke.cmake.

The probe's STATUS line embeds unmatched '[' characters, and the original
newline -> ';' list split in cmake/zmk_compat.cmake collapsed STATUS and DEFINES
into one item, silently dropping the compile defines (fixed in v1.2.1). Nothing
in the Python suite could catch that: the bug lived in CMake. This test runs the
contract script with a real cmake interpreter so the parser stays covered.

Skips when cmake is unavailable (pure-Python CI legs).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "cmake_parse_smoke.cmake"
CMAKE = shutil.which("cmake")


@pytest.mark.skipif(CMAKE is None, reason="cmake not installed")
def test_parse_contract_script_passes() -> None:
    r = subprocess.run(
        [CMAKE, "-P", str(SMOKE)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    assert "ALL ASSERTIONS PASSED" in r.stdout + r.stderr


@pytest.mark.skipif(CMAKE is None, reason="cmake not installed")
def test_defines_line_survives_bracketed_status(tmp_path: Path) -> None:
    """The exact regression: brackets in STATUS must not swallow DEFINES."""
    script = tmp_path / "regression.cmake"
    script.write_text(
        f"""
include("{HERE.parent.parent}/cmake/zmk_compat_parse.cmake")
zmk_keybeacon_parse_probe_output(
    "STATUS: [zmk-keybeacon 1.2.1] ZMK revision check: edf5c08 ∈ [known-good: e844eca2..4dd95d7) ✓\\nDEFINES: -DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1"
    _status _defines _warn)
if(NOT _defines STREQUAL "-DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1")
    message(FATAL_ERROR "defines dropped: [${{_defines}}]")
endif()
""",
        encoding="utf-8",
    )
    r = subprocess.run(
        [CMAKE, "-P", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
