/*
 * Copyright (c) 2026 The TOTEM ZMK Contributors
 * SPDX-License-Identifier: MIT
 *
 * KeyBeacon shared logic: expose the active layer + modifier state over a
 * custom GATT service. This file is keyboard-independent and MUST NOT be
 * edited to port the feature to another keyboard — see README.md.
 */

#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include <string.h>

#include <zmk/keymap.h>
#include <zmk/hid.h>
#include <zmk/event_manager.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/events/keycode_state_changed.h>

#define KEYBEACON_SERVICE_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA0, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))

#define KEYBEACON_CHRC_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA1, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))

#define PAYLOAD_HEADER_LEN 2
#define LAYER_NAME_MAX     32
#define PAYLOAD_MAX        (PAYLOAD_HEADER_LEN + LAYER_NAME_MAX)

static uint8_t payload_cache[PAYLOAD_MAX];
static uint8_t payload_len_cache;

static uint8_t payload_buf[PAYLOAD_MAX];
static uint8_t payload_len_buf;

static ssize_t read_status(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf,
                           uint16_t len, uint16_t offset) {
    return bt_gatt_attr_read(conn, attr, buf, len, offset, payload_cache, payload_len_cache);
}

static void ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {}

BT_GATT_SERVICE_DEFINE(keybeacon_svc,
    BT_GATT_PRIMARY_SERVICE(KEYBEACON_SERVICE_UUID),
    BT_GATT_CHARACTERISTIC(KEYBEACON_CHRC_UUID,
                           BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_READ,
                           read_status, NULL, NULL),
    BT_GATT_CCC(ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
);

static void build_payload(uint8_t *buf, uint8_t *len) {
    zmk_keymap_layer_index_t idx = zmk_keymap_highest_layer_active();
    zmk_keymap_layer_id_t id     = zmk_keymap_layer_index_to_id(idx);
    const char *name             = zmk_keymap_layer_name(id);
    zmk_mod_flags_t mods         = zmk_hid_get_explicit_mods();

    buf[0] = (uint8_t)idx;
    buf[1] = (uint8_t)mods;

    uint8_t name_len = 0;
    if (name && name[0]) {
        name_len = (uint8_t)strnlen(name, LAYER_NAME_MAX);
        memcpy(buf + PAYLOAD_HEADER_LEN, name, name_len);
    }
    *len = PAYLOAD_HEADER_LEN + name_len;
}

static void update_and_notify(void) {
    build_payload(payload_buf, &payload_len_buf);

    if (payload_len_buf == payload_len_cache &&
        memcmp(payload_buf, payload_cache, payload_len_buf) == 0) {
        return;
    }

    memcpy(payload_cache, payload_buf, payload_len_buf);
    payload_len_cache = payload_len_buf;

    bt_gatt_notify(NULL, &keybeacon_svc.attrs[1], payload_cache, payload_len_cache);
}

static int keybeacon_cb(const zmk_event_t *eh) {
    update_and_notify();
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(keybeacon, keybeacon_cb);
ZMK_SUBSCRIPTION(keybeacon, zmk_layer_state_changed);
ZMK_SUBSCRIPTION(keybeacon, zmk_keycode_state_changed);

static int keybeacon_init(void) {
    build_payload(payload_cache, &payload_len_cache);
    return 0;
}

SYS_INIT(keybeacon_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
