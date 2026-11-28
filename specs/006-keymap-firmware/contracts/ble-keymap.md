# Contract: BLE Keymap Characteristics (KBP 1.3) — Firmware Side

**Status**: Draft | **Date**: 2026-11-26

This is the firmware-side copy of the wire contract. The normative source once ratified lives in `keybeacon/protocol/README.md §1.3`. This copy is a working reference during 006-keymap-firmware implementation; it must stay byte-for-byte identical to the upstream contract.

See `keybeacon/specs/006-keymap-viewer/contracts/ble-keymap.md` for the full contract text.

## Firmware Implementation Constraints

### UUID Registration

```c
#define KEYBEACON_META_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA5, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))

#define KEYBEACON_DATA_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA6, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))
```

### Static Buffer

```c
static uint8_t keymap_data_buf[CONFIG_ZMK_KEYBEACON_KEYMAP_MAX_BYTES];
static uint16_t keymap_data_len;

static uint8_t keymap_meta_buf[256];
static uint8_t keymap_meta_len;
```

Both buffers are populated once in `SYS_INIT(build_keymap_payload, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY)`.

### READ Handlers

```c
static ssize_t read_keymap_meta(struct bt_conn *conn,
                                const struct bt_gatt_attr *attr,
                                void *buf, uint16_t len, uint16_t offset) {
    return bt_gatt_attr_read(conn, attr, buf, len, offset,
                             keymap_meta_buf, keymap_meta_len);
}

static ssize_t read_keymap_data(struct bt_conn *conn,
                                const struct bt_gatt_attr *attr,
                                void *buf, uint16_t len, uint16_t offset) {
    return bt_gatt_attr_read(conn, attr, buf, len, offset,
                             keymap_data_buf, keymap_data_len);
}
```

`bt_gatt_attr_read` automatically handles READ_BLOB offset slicing; no manual chunking is required.

### Kconfig

```kconfig
config ZMK_KEYBEACON_KEYMAP
    bool "KeyBeacon KBP 1.3 Keymap characteristics"
    default y
    depends on ZMK_KEYBEACON

config ZMK_KEYBEACON_KEYMAP_MAX_BYTES
    int "Maximum KeymapData payload size in bytes"
    default 4096
    depends on ZMK_KEYBEACON_KEYMAP
```

### ATT Handle Map Update

When `CONFIG_ZMK_KEYBEACON_KEYMAP=y`, two new entries are appended to the GATT service after the existing AA4 block:

```
AA5 chrc decl   (KeymapMeta)
AA5 chrc value
AA6 chrc decl   (KeymapData)
AA6 chrc value
```

No CCC descriptors — neither characteristic uses NOTIFY.

### CRC32

```c
#include <zephyr/sys/crc.h>

uint32_t crc = crc32_ieee(keymap_data_buf, keymap_data_len);
```

Stored at bytes [0..3] of `keymap_meta_buf` in little-endian order.
