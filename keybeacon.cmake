# Copyright (c) 2026 The TOTEM ZMK Contributors
# SPDX-License-Identifier: MIT
#
# KeyBeacon build snippet. A consuming shield adds exactly one line to its
# CMakeLists.txt:  include(<path-to-kit>/keybeacon.cmake)
# The feature links only for the host-link (central) role when
# CONFIG_ZMK_KEYBEACON is set.
#
# v1.1.4+ : probe ZMK revision compatibility before compiling. See
#           cmake/zmk_compat.cmake.
# v1.2.1+ : the role guard tolerates unibody builds. ZMK defines
#           ZMK_SPLIT_ROLE_CENTRAL only inside `if ZMK_SPLIT`
#           (app/src/split/Kconfig), so a non-split keyboard leaves the symbol
#           undefined — testing it directly compiled the module out of every
#           unibody target. A non-split build IS the host-link role.

include(${CMAKE_CURRENT_LIST_DIR}/cmake/zmk_compat.cmake)

if(CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE
   AND (NOT CONFIG_ZMK_SPLIT OR CONFIG_ZMK_SPLIT_ROLE_CENTRAL))
    zephyr_library()
    zephyr_library_include_directories(${CMAKE_SOURCE_DIR}/include)
    zephyr_library_sources(${CMAKE_CURRENT_LIST_DIR}/keybeacon.c)
endif()
