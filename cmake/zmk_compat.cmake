# zmk_compat.cmake — ZMK revision compatibility probe entry point.
#
# Call from keybeacon.cmake BEFORE zephyr_library_sources(). This probe:
#   1. Finds the Python 3 interpreter (required for scripts/check_zmk_compat.py).
#   2. Locates ZMK root (ZEPHYR_BASE/../zmk by default; overridable via ZMK_ROOT).
#   3. Runs check_zmk_compat.py and routes its output to the proper CMake message()
#      level based on probe result + CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK.
#
# Output protocol (parsed from stdout line-by-line, see check_zmk_compat.py):
#   STATUS: <one-line status for message(STATUS)>
#   DEFINES: -DMACRO1=1 -DMACRO2=1   (empty line if none)
#   WARN:
#     <multi-line warning body, indented 2 spaces>

if(NOT CONFIG_ZMK_KEYBEACON)
    # Nothing to probe — module is disabled.
    return()
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Locate ZMK root. ZEPHYR_BASE is set by Zephyr before this file runs.
if(NOT DEFINED ZMK_ROOT)
    set(ZMK_ROOT "${ZEPHYR_BASE}/../zmk" CACHE PATH "Path to the ZMK source tree")
endif()

set(_compat_module_root "${CMAKE_CURRENT_LIST_DIR}/..")
set(_compat_script "${_compat_module_root}/scripts/check_zmk_compat.py")
set(_compat_yaml   "${_compat_module_root}/compatibility.yaml")

if(NOT EXISTS "${_compat_script}")
    message(FATAL_ERROR
        "[zmk-keybeacon] cannot find check_zmk_compat.py at ${_compat_script}; "
        "did `west update` finish correctly?")
endif()

# -------------------------------------------------------------------------
# Build the probe command. Pass --allow-incompat when the Kconfig escape
# hatch is enabled; keep as-is otherwise so Python emits the full banner.
# -------------------------------------------------------------------------
set(_compat_cmd
    "${Python3_EXECUTABLE}" "${_compat_script}"
    --compat-file "${_compat_yaml}"
    --zmk-root    "${ZMK_ROOT}"
)
if(CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK)
    list(APPEND _compat_cmd --allow-incompat)
endif()

execute_process(
    COMMAND ${_compat_cmd}
    OUTPUT_VARIABLE _compat_stdout
    ERROR_VARIABLE  _compat_stderr
    RESULT_VARIABLE _compat_rc
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_STRIP_TRAILING_WHITESPACE
)

# -------------------------------------------------------------------------
# rc != 0 — surface the banner verbatim via FATAL_ERROR.
# -------------------------------------------------------------------------
if(NOT _compat_rc EQUAL 0)
    message(FATAL_ERROR "[zmk-keybeacon] ZMK revision incompatibility detected:\n\n${_compat_stderr}")
endif()

# -------------------------------------------------------------------------
# rc == 0 — parse stdout and route output to CMake message().
# -------------------------------------------------------------------------
string(REPLACE "\n" ";" _compat_lines "${_compat_stdout}")
set(_compat_status_line "")
set(_compat_defines_line "")
set(_compat_in_warn FALSE)
set(_compat_warn_body "")

foreach(_line IN LISTS _compat_lines)
    if(_line MATCHES "^STATUS: (.*)$")
        set(_compat_status_line "${CMAKE_MATCH_1}")
        set(_compat_in_warn FALSE)
    elseif(_line MATCHES "^DEFINES: (.*)$")
        set(_compat_defines_line "${CMAKE_MATCH_1}")
        set(_compat_in_warn FALSE)
    elseif(_line STREQUAL "WARN:")
        set(_compat_in_warn TRUE)
    elseif(_compat_in_warn AND _line MATCHES "^  (.*)$")
        if(_compat_warn_body)
            set(_compat_warn_body "${_compat_warn_body}\n${CMAKE_MATCH_1}")
        else()
            set(_compat_warn_body "${CMAKE_MATCH_1}")
        endif()
    endif()
endforeach()

# Status line (always emit)
if(_compat_status_line)
    message(STATUS "${_compat_status_line}")
endif()

# Warn block (only when escape hatch active and probe would have failed)
if(_compat_warn_body)
    message(WARNING "${_compat_warn_body}")
endif()

# Emit compile definitions so keybeacon.c's #ifdef branches can key off them.
if(_compat_defines_line)
    # DEFINES line is " -DMACRO1=1 -DMACRO2=1"; split on space, strip -D prefix.
    string(STRIP "${_compat_defines_line}" _compat_defines_line)
    if(_compat_defines_line)
        string(REPLACE " " ";" _compat_define_items "${_compat_defines_line}")
        foreach(_item IN LISTS _compat_define_items)
            if(_item MATCHES "^-D(.+)$")
                add_compile_definitions("${CMAKE_MATCH_1}")
                set(ZMK_KEYBEACON_COMPAT_DEFINES
                    "${ZMK_KEYBEACON_COMPAT_DEFINES} -D${CMAKE_MATCH_1}"
                    PARENT_SCOPE)
            endif()
        endforeach()
    endif()
endif()
