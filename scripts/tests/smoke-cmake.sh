#!/usr/bin/env bash
# smoke-cmake.sh — End-to-end smoke of cmake/zmk_compat.cmake against the
# three fixture ZMK trees. Runs check_zmk_compat.py directly (same CLI path
# cmake uses) instead of spinning up a full Zephyr configure — the latter
# needs the ARM toolchain and is left to the CI matrix.
#
# This script asserts the OBSERVABLE OUTPUT CONTRACT:
#   zmk-legacy    -> exit 0 + stdout contains "DEFINES: -DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1"
#   zmk-renamed   -> exit 0 + stdout DEFINES line is empty of HAS_LEGACY_ENDPOINT
#   zmk-missing   -> exit 2 + stderr contains the full banner
#   escape hatch  -> exit 0 + stdout contains "WARN:" block
#
# Exit code 0 if all four assertions pass; 1 if any fail.

set -u

HERE=$(cd "$(dirname "$0")" && pwd)
MODULE_ROOT=$(cd "${HERE}/../.." && pwd)
CHECK_PY="${MODULE_ROOT}/scripts/check_zmk_compat.py"
COMPAT="${MODULE_ROOT}/compatibility.yaml"
FIXTURES="${HERE}/fixtures"
PY=${PYTHON:-python3}

fail=0

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [[ "${expected}" != "${actual}" ]]; then
        printf "  ✗ %s: expected %q, got %q\n" "${label}" "${expected}" "${actual}"
        fail=1
    else
        printf "  ✓ %s\n" "${label}"
    fi
}

assert_contains() {
    local label="$1" needle="$2" haystack="$3"
    if [[ "${haystack}" != *"${needle}"* ]]; then
        printf "  ✗ %s: substring %q not found in output\n" "${label}" "${needle}"
        fail=1
    else
        printf "  ✓ %s\n" "${label}"
    fi
}

assert_not_contains() {
    local label="$1" needle="$2" haystack="$3"
    if [[ "${haystack}" == *"${needle}"* ]]; then
        printf "  ✗ %s: forbidden substring %q found in output\n" "${label}" "${needle}"
        fail=1
    else
        printf "  ✓ %s\n" "${label}"
    fi
}

run_probe() {
    local fixture="$1" ; shift
    "${PY}" "${CHECK_PY}" \
        --compat-file "${COMPAT}" \
        --zmk-root "${FIXTURES}/${fixture}" \
        "$@"
}

# -----------------------------------------------------------------------
echo "[1/4] zmk-legacy fixture (旧 API, 应 emit HAS_LEGACY_ENDPOINT)"
out=$(run_probe zmk-legacy 2>&1); rc=$?
assert_eq "exit code" 0 "${rc}"
assert_contains "DEFINES line" "DEFINES: -DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1" "${out}"
assert_contains "✓ marker" "✓" "${out}"

# -----------------------------------------------------------------------
echo "[2/4] zmk-renamed fixture (新 API, fallback 命中, 不应 emit 宏)"
out=$(run_probe zmk-renamed 2>&1); rc=$?
assert_eq "exit code" 0 "${rc}"
# DEFINES 行存在但不含 HAS_LEGACY_ENDPOINT
defines_line=$(printf "%s\n" "${out}" | grep "^DEFINES:" || true)
assert_not_contains "DEFINES 不含旧宏" "HAS_LEGACY_ENDPOINT" "${defines_line}"
assert_contains "✓ marker" "✓" "${out}"

# -----------------------------------------------------------------------
echo "[3/4] zmk-missing fixture (fail-fast, 完整 banner)"
out=$(run_probe zmk-missing 2>stderr.txt); rc=$?
stderr_out=$(cat stderr.txt); rm -f stderr.txt
assert_eq "exit code" 2 "${rc}"
assert_contains "banner title" "is INCOMPATIBLE" "${stderr_out}"
assert_contains "Missing symbol" "Missing symbol: zmk_endpoints_selected" "${stderr_out}"
assert_contains "How to fix" "How to fix" "${stderr_out}"
assert_contains "Also 段落" "DO NOT disable" "${stderr_out}"

# -----------------------------------------------------------------------
echo "[4/4] escape hatch (--allow-incompat, missing fixture 应降级 WARN)"
out=$(run_probe zmk-missing --allow-incompat 2>&1); rc=$?
assert_eq "exit code" 0 "${rc}"
assert_contains "WARN block" "WARN:" "${out}"
assert_contains "would have failed" "would have failed on symbol zmk_endpoints_selected" "${out}"
assert_contains "at your own risk" "at your own risk" "${out}"

echo "---"
if [[ ${fail} -eq 0 ]]; then
    echo "smoke-cmake.sh: ALL ASSERTIONS PASSED"
    exit 0
else
    echo "smoke-cmake.sh: FAILURE — see ✗ lines above"
    exit 1
fi
