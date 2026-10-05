<!--
Copyright (c) 2026 The TOTEM ZMK Contributors
SPDX-License-Identifier: MIT
-->

# KeyBeacon Kit — Porting Guide

KeyBeacon exposes a ZMK keyboard's **active layer + modifier state** over a custom
BLE GATT service so a host app (e.g. the macOS KeyBeacon widget) can display it
live. This directory is a **self-contained, keyboard-independent kit**: the shared
logic in `keybeacon.c` is never edited to port the feature — you only wire it into a
shield and flip one Kconfig symbol.

## What's in the kit

| File | Role | Edit to port? |
|------|------|---------------|
| `keybeacon.c` | Shared GATT logic (service, read, change-detect, notify) | **No** |
| `keybeacon.cmake` | Guarded `zephyr_library` snippet (symbol + BLE + central) | No |
| `Kconfig.keybeacon` | Declares `CONFIG_ZMK_KEYBEACON` (bool, `default n`) | No |
| `README.md` | This guide | No |

## Prerequisites

- **Central BLE role**: the feature compiles **only** for the keyboard's central
  role. A split keyboard's central half qualifies; a peripheral-only or non-BLE
  keyboard does **not**. If your keyboard has no central BLE role, it is
  **unsupported** — stop here.
- `CONFIG_ZMK_BLE` must be available (it is a `depends on` of the symbol).

## Porting steps (≤ 10)

1. Make the kit available to your target shield — either copy this `keybeacon_kit/`
   directory into your `config/` tree, or reference it in place by relative path.
2. In the shield's `CMakeLists.txt`, add one line:
   `include(<path-to-kit>/keybeacon.cmake)`
3. In the shield's `Kconfig.defconfig` (or `Kconfig`), source the symbol:
   `rsource "<path-to-kit>/Kconfig.keybeacon"`
4. In the keyboard-level `.conf`, enable it: `CONFIG_ZMK_KEYBEACON=y`
5. Build the **central** target for your keyboard and flash it.

That's it — you do **not** edit `keybeacon.c`.

## Verify

- The central image links `keybeacon.c`; the peripheral and `settings_reset`
  images do **not** (the `.cmake` guard enforces central-only).
- `git diff <path-to-kit>/keybeacon.c` is empty after porting.
- Run the host probe (`tools/probe.py`) or the app: the keyboard is discovered by
  the custom service UUID `AA440AA0-…`, and the status stream decodes.

## Why shield-scoped (not a west module)

`keybeacon.c` calls ZMK `app`-private APIs (`zmk/keymap.h`, `zmk/hid.h`, the event
manager). Those headers are reachable only from the shield build scope via
`zephyr_library_include_directories(${CMAKE_SOURCE_DIR}/include)` (see
`keybeacon.cmake`). A standalone west module cannot reach them, so the kit is
consumed from within a shield rather than distributed as an independent module.

## Reference consumer

The Totem shield (`config/boards/shields/totem/`) consumes this kit as the
reference: its `CMakeLists.txt` includes `keybeacon.cmake`, its `Kconfig.defconfig`
sources `Kconfig.keybeacon`, and `config/totem.conf` sets `CONFIG_ZMK_KEYBEACON=y`.
