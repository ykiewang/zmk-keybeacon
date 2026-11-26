# Copyright (c) 2026 The TOTEM ZMK Contributors
# SPDX-License-Identifier: MIT
#
# zmk_compat_parse.cmake — bracket-safe parser for check_zmk_compat.py stdout.
#
# Why this file exists
# --------------------
# The probe's STATUS line embeds square brackets:
#
#   STATUS: [zmk-keybeacon 1.2.1] ZMK revision check: edf5c08 ∈ [known-good: …) ✓
#
# The original parser split raw stdout on newlines into a CMake list
#
#   string(REPLACE "\n" ";" _compat_lines "${_compat_stdout}")
#   foreach(_line IN LISTS _compat_lines)
#
# and an element holding an unmatched '[' makes `foreach(IN LISTS)` swallow the
# following elements, so "STATUS: …" and "DEFINES: …" collapsed into ONE item.
# The DEFINES branch never matched, the compile definition never reached the
# compiler, and on a pre-rename ZMK (the era with zmk_endpoints_selected-only)
# keybeacon.c failed to compile at its #else branch. Reproduced with the real
# banner text on cmake 4.0.3; see scripts/tests/cmake_parse_smoke.cmake.
#
# Everything here therefore works on plain strings — no CMake lists — so '[' is
# just a character.

# ---------------------------------------------------------------------------
# _zb_find_line(<value> <out_line> <out_rest> <out_more>)
#
# Splits the first newline-terminated line off <value>: <out_line> is that line,
# <out_rest> the remainder ("" when <value> held no newline) and <out_more> is
# TRUE when another line follows. Implemented without the `string(FIND … <start>)`
# form, which cmake 4.x no longer accepts, and without CMake lists, so arbitrary
# characters are safe.
# ---------------------------------------------------------------------------
function(_zb_find_line _value _out_line _out_rest _out_more)
    string(FIND "${_value}" "\n" _nl)
    if(_nl EQUAL -1)
        set(_line "${_value}")
        set(_rest "")
        set(_more FALSE)
    else()
        string(SUBSTRING "${_value}" 0 ${_nl} _line)
        math(EXPR _next "${_nl} + 1")
        string(SUBSTRING "${_value}" ${_next} -1 _rest)
        set(_more TRUE)
    endif()
    set(${_out_line} "${_line}" PARENT_SCOPE)
    set(${_out_rest} "${_rest}" PARENT_SCOPE)
    set(${_out_more} ${_more} PARENT_SCOPE)
endfunction()

# ---------------------------------------------------------------------------
# zmk_keybeacon_parse_probe_output(<raw_stdout>
#                                  <out_status> <out_defines> <out_warn>)
#
# Splits the probe contract (see scripts/check_zmk_compat.py) into its three
# fields:
#   STATUS: <one line>            -> <out_status>   (set to "" when absent)
#   DEFINES: -DA=1 -DB=1          -> <out_defines>  (empty string when none)
#   WARN:                         -> <out_warn>
#     <two-space-indented body>     (body with the two-space prefix stripped;
#                                    empty string when the block is absent)
# ---------------------------------------------------------------------------
function(zmk_keybeacon_parse_probe_output _raw _out_status _out_defines _out_warn)
    set(_status "")
    set(_defines "")
    set(_warn_body "")
    set(_in_warn FALSE)

    set(_rest "${_raw}")
    while(TRUE)
        _zb_find_line("${_rest}" _line _next_rest _more)
        if(_line MATCHES "^STATUS: (.*)$")
            set(_status "${CMAKE_MATCH_1}")
            set(_in_warn FALSE)
        elseif(_line MATCHES "^DEFINES: (.*)$")
            set(_defines "${CMAKE_MATCH_1}")
            set(_in_warn FALSE)
        elseif(_line STREQUAL "WARN:")
            set(_in_warn TRUE)
        elseif(_in_warn AND _line MATCHES "^  (.*)$")
            if(_warn_body STREQUAL "")
                set(_warn_body "${CMAKE_MATCH_1}")
            else()
                string(APPEND _warn_body "\n${CMAKE_MATCH_1}")
            endif()
        endif()
        if(NOT _more)
            break()
        endif()
        set(_rest "${_next_rest}")
    endwhile()

    set(${_out_status} "${_status}" PARENT_SCOPE)
    set(${_out_defines} "${_defines}" PARENT_SCOPE)
    set(${_out_warn} "${_warn_body}" PARENT_SCOPE)
endfunction()
