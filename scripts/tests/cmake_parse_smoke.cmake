# Copyright (c) 2026 The TOTEM ZMK Contributors
# SPDX-License-Identifier: MIT
#
# cmake_parse_smoke.cmake — contract test for cmake/zmk_compat_parse.cmake.
#
# Run directly, no Zephyr needed:   cmake -P scripts/tests/cmake_parse_smoke.cmake
# Exit code 0 = all assertions passed.
#
# Regression guard for the bug fixed in v1.2.1: the STATUS line embeds unmatched
# '[' characters ("[zmk-keybeacon 1.2.1] … [known-good: …)"), which made the old
# newline -> ';' list split collapse STATUS and DEFINES into a single item, so
# the compile defines were silently dropped and keybeacon.c fell into its #else
# branch on a pre-rename ZMK.

cmake_minimum_required(VERSION 3.20)

include("${CMAKE_CURRENT_LIST_DIR}/../../cmake/zmk_compat_parse.cmake")

set(_failures 0)

function(assert_eq _label _expected _actual)
    if(NOT "${_expected}" STREQUAL "${_actual}")
        message("[FAIL] ${_label}: expected [${_expected}], got [${_actual}]")
        set(_failures 1)
        set(_kbfail 1 PARENT_SCOPE)
        return()
    endif()
    message("[ok]   ${_label}")
endfunction()

# ---------------------------------------------------------------------------
# 1. Probe passed on a legacy-era ZMK: bracketed STATUS + a compile define.
# ---------------------------------------------------------------------------
set(_raw_ok "STATUS: [zmk-keybeacon 1.2.1] ZMK revision check: edf5c08 ∈ [known-good: e844eca2..4dd95d7) ✓
DEFINES: -DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1")

zmk_keybeacon_parse_probe_output("${_raw_ok}" _status _defines _warn)
assert_eq("status keeps brackets and checkmark"
          "[zmk-keybeacon 1.2.1] ZMK revision check: edf5c08 ∈ [known-good: e844eca2..4dd95d7) ✓"
          "${_status}")
assert_eq("defines survived the list split"
          "-DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1"
          "${_defines}")
assert_eq("no warn block when absent" "" "${_warn}")

# ---------------------------------------------------------------------------
# 2. Probe passed on a renamed-era ZMK: empty DEFINES line.
# ---------------------------------------------------------------------------
set(_raw_empty "STATUS: [zmk-keybeacon 1.2.1] ok
DEFINES: ")
zmk_keybeacon_parse_probe_output("${_raw_empty}" _status _defines _warn)
assert_eq("empty DEFINES parses as empty" "" "${_defines}")
assert_eq("status without trailing junk" "[zmk-keybeacon 1.2.1] ok" "${_status}")

# ---------------------------------------------------------------------------
# 3. Escape hatch active: WARN block body is unwrapped, in order.
# ---------------------------------------------------------------------------
set(_raw_warn "STATUS: [zmk-keybeacon 1.2.1] ok (bypassed)
DEFINES: -DOTHER=1
WARN:
  first warn line [with brackets
  second warn line")
zmk_keybeacon_parse_probe_output("${_raw_warn}" _status _defines _warn)
assert_eq("defines with warn present" "-DOTHER=1" "${_defines}")
assert_eq("warn body joined"
          "first warn line [with brackets\nsecond warn line"
          "${_warn}")

# ---------------------------------------------------------------------------
# 4. Degenerate input: no trailing newline, no recognised lines.
# ---------------------------------------------------------------------------
zmk_keybeacon_parse_probe_output("garbage [unterminated" _status _defines _warn)
assert_eq("garbage yields empty status" "" "${_status}")
assert_eq("garbage yields empty defines" "" "${_defines}")

if(_kbfail)
    message(FATAL_ERROR "cmake_parse_smoke: FAILED")
endif()
message("cmake_parse_smoke: ALL ASSERTIONS PASSED")
