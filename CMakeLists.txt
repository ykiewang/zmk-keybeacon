# Copyright (c) 2026 The TOTEM ZMK Contributors
# SPDX-License-Identifier: MIT
#
# Zephyr module cmake entry point. Delegates to keybeacon.cmake so the original
# file name and the central-only guard are preserved verbatim; this wrapper adds
# no logic of its own.
include(${CMAKE_CURRENT_LIST_DIR}/keybeacon.cmake)
