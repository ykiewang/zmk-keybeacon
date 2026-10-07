<!--
Copyright (c) 2026 The TOTEM ZMK Contributors
SPDX-License-Identifier: MIT
-->

# Changelog — zmk-keybeacon

All notable changes to the KeyBeacon Zephyr module are documented here. The module follows
[Semantic Versioning](https://semver.org/): consumers pin a tag via `revision` in their `west.yml`.

## Versioning policy

| Change | Example | Version bump |
|--------|---------|--------------|
| Breaking change to the GATT contract | Service/characteristic UUID change, payload layout change | **MAJOR** |
| Backward-compatible addition | A new optional Kconfig symbol | **MINOR** |
| Fix with no interface change | Bug fix in change-detection, doc fix | **PATCH** |

Because consumers pin an exact tag, publishing a new version never affects an existing build
until that consumer bumps its `revision`.

## [1.0.0] — 2026-10-07

Initial release as a standalone Zephyr module, extracted unchanged from the Totem firmware repo's
`config/keybeacon_kit/`.

### Added

- `zephyr/module.yml` + `CMakeLists.txt` wrapper so the feature integrates through `west.yml`
  with no `include()`/`rsource` wiring in the consuming shield.
- `keybeacon.c` — custom GATT service exposing the active layer index, modifier flags, and layer
  name as a notify-on-change snapshot `[layer_index][mods][layer_name]`.
- `Kconfig.keybeacon` — `CONFIG_ZMK_KEYBEACON` (bool, `depends on ZMK_BLE`, `default n`).
- `keybeacon.cmake` — central-only guard
  (`CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL`).

### Contract

- GATT service UUID `AA440AA0-F5ED-4C48-84A1-8062D20D3D55`, characteristic
  `AA440AA1-F5ED-4C48-84A1-8062D20D3D55`. Unchanged from the pre-module kit — no protocol bump.
