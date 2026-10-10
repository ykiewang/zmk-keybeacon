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

## [1.1.2] — 2026-10-09

**PATCH** release — bug fix with no wire-contract change. All KBP 1.1 bytes, UUIDs, Kconfig
symbols, and the AA1 KBP 1.0 characteristic remain byte-for-byte identical to v1.1.0 / v1.1.1.

### Fixed

- **AA3 `right_percent` no longer flaps between the last-known value and `255`.** Even with
  the v1.1.1 TTL extension to 75 s, independent 1 Hz work queues for AA2 and AA3 could cross
  the freshness boundary at slightly different wall-clock moments, producing a visible skew
  where the floating panel showed `●R72` → `●R—` → `●R72` while the online dot stayed green.
  The underlying design mistake was coupling the battery byte to the TTL at all: the TTL is a
  liveness proxy and belongs on `AA2.split_flags.right_online`, not on the electrochemical
  state-of-charge value. The battery byte should hold the last-known reading until either (a)
  the module boots without ever receiving an event, or (b) the peripheral explicitly reports
  an unavailable sample. v1.1.2 removes the TTL coupling in `batt_build_payload`, so the byte
  tracks `peripheral_slots[0].last_percent` whenever `last_seen_ms > 0`.
- A follow-up to `contracts/battery-characteristic.md §6` ("Peripheral sync-bus temporarily
  lost: `right_percent` stays at last-known value for up to 10 s, then transitions to `255`")
  is pending in the main `keybeacon` repository to reflect the corrected semantics.

## [1.1.1] — 2026-10-09

**PATCH** release — bug fix with no wire-contract change. All KBP 1.1 bytes, UUIDs, Kconfig
symbols, and the AA1 KBP 1.0 characteristic remain byte-for-byte identical to v1.1.0.

### Fixed

- **Peripheral freshness window** (`KBP_PERIPHERAL_FRESH_MS`) raised from 10 s to **75 s**. The
  10 s value in v1.1.0 was derived from `research.md §R1` under the (incorrect) assumption
  that the peripheral emits events on split-sync state changes. In practice the
  `zmk_peripheral_battery_state_changed` proxy event is triggered by the standard periodic BAS
  notify, whose default cadence is `CONFIG_ZMK_BATTERY_REPORT_INTERVAL=60 s`. With a 10 s TTL
  the central would therefore mark the peripheral offline ~50 s out of every 60 s window even
  on a fully healthy split keyboard; AA2.split_flags.right_online would flip to `0` and
  AA3.right_percent would fall back to the unavailable sentinel (`255`). 75 s gives a 1.25×
  margin on the default report interval, tolerating a single missed notify without flipping
  the online bit. Keyboard authors who shorten `BATTERY_REPORT_INTERVAL` keep working
  unchanged; those who lengthen it should bump this proportionally in a fork.

### Documentation note

`specs/002-zmk-keybeacon-kbp11/research.md §R1` and `contracts/connectivity-characteristic.md`
in the main `keybeacon` repository will be updated in a follow-up to describe the correct
notify-based event model.

## [1.1.0] — 2026-10-09

Additive **MINOR** release implementing KBP 1.1 Connectivity + Power. Service UUID unchanged;
the KBP 1.0 characteristic `AA440AA1-…` is **byte-for-byte identical** to v1.0.0 (same
declaration, same CCC, same emission cadence). KBP 1.0 hosts continue to work unchanged.

### Added

- **AA2 Connectivity characteristic** `AA440AA2-F5ED-4C48-84A1-8062D20D3D55` (optional,
  READ|NOTIFY + CCC, 7-byte payload per `protocol/README.md §14.3.1`): capability_bits,
  host_state, profile_byte, profile_max_slots, split_link_flags, output_endpoint,
  charging_flags.
- **AA3 Battery characteristic** `AA440AA3-F5ED-4C48-84A1-8062D20D3D55` (optional,
  READ|NOTIFY + CCC, 1-byte on integer boards / 2-byte on splits per `protocol/README.md
  §14.4.1`): `[overall]` or `[left, right]` with `255` as "temporarily unavailable" sentinel.
- Two new Kconfig sub-options under `CONFIG_ZMK_KEYBEACON` (both `default y` so a consumer
  simply bumps `revision: v1.0.0 → v1.1.0` to pick up the new characteristics with zero
  `.conf` edits):
  - `CONFIG_ZMK_KEYBEACON_CONNECTIVITY` — gates AA2.
  - `CONFIG_ZMK_KEYBEACON_BATTERY` — gates AA3.
- ZMK event subscriptions: `zmk_ble_active_profile_changed`, `zmk_endpoint_changed`,
  `zmk_battery_state_changed`, `zmk_peripheral_battery_state_changed` (last one is gated on
  `CONFIG_ZMK_SPLIT_BLE`).
- 1 Hz `k_work_delayable` worker to satisfy the §14.4.5 OR-relation `≥ 1 s` floor for the
  Battery characteristic's throttling policy.
- `BUILD_ASSERT`s guarding the Connectivity payload length (7 bytes) and the Battery payload
  length (1 or 2 bytes depending on `IS_ENABLED(CONFIG_ZMK_SPLIT)`).
- `has_left_charging` and `has_right_charging` capability bits — both wired to `0` in this
  release. A follow-up (`v1.2.x` or board-overlay-driven) can read a per-board charger GPIO.

### Backward compatibility

- Service UUID `AA440AA0-F5ED-4C48-84A1-8062D20D3D55` unchanged.
- Characteristic `AA440AA1-F5ED-4C48-84A1-8062D20D3D55` unchanged (same `BT_GATT_CHARACTERISTIC`
  + `BT_GATT_CCC` block, same `bt_gatt_notify(…, &keybeacon_svc.attrs[1], …)` call site, same
  change-detect suppression).
- The combination `CONFIG_ZMK_KEYBEACON=y, CONFIG_ZMK_KEYBEACON_CONNECTIVITY=n,
  CONFIG_ZMK_KEYBEACON_BATTERY=n` on this v1.1.0 module produces GATT output that is
  **byte-indistinguishable** from a `revision: v1.0.0` build.

### Versioning rationale

Semver **MINOR**: additive new characteristics (KBP §9 "adding a new optional characteristic
or descriptor; service UUID unchanged"). Existing consumers are unaffected until they bump
`revision` in their `west.yml`.

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
