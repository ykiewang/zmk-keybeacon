/*
 * Copyright (c) 2026 The TOTEM ZMK Contributors
 * SPDX-License-Identifier: MIT
 *
 * KeyBeacon shared logic:
 *   - KBP 1.0: expose the active layer + modifier state (AA440AA1-…)
 *   - KBP 1.1: optionally expose Connectivity (AA440AA2-…) and Battery
 *              (AA440AA3-…) characteristics, each gated by a Kconfig
 *              sub-option so a v1.1.0 module can emit a v1.0-equivalent
 *              GATT shape when both sub-options are disabled.
 *
 * This file is keyboard-independent and MUST NOT be edited to port the
 * feature to another keyboard — see README.md.
 */

#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/sys/util.h>
#include <string.h>

#include <zmk/keymap.h>
#include <zmk/hid.h>
#include <zmk/event_manager.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/events/keycode_state_changed.h>

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY) || IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)
#include <zmk/ble.h>
#include <zmk/events/ble_active_profile_changed.h>
#endif

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)
#include <zmk/endpoints.h>
#include <zmk/events/endpoint_changed.h>
#endif

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY) || IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)
#include <zmk/battery.h>
#include <zmk/events/battery_state_changed.h>
#endif

#if IS_ENABLED(CONFIG_ZMK_SPLIT) && IS_ENABLED(CONFIG_ZMK_SPLIT_BLE) && IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
#include <zmk/split/central.h>
#endif

/* ================================================================== */
/* Service and characteristic UUIDs                                   */
/* ================================================================== */

#define KEYBEACON_SERVICE_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA0, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))

#define KEYBEACON_CHRC_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA1, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)
#define KEYBEACON_CONN_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA2, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))
#endif

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)
#define KEYBEACON_BATT_UUID \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0xAA440AA3, 0xF5ED, 0x4C48, 0x84A1, 0x8062D20D3D55))
#endif

/* ================================================================== */
/* Attribute-index map (data-model §E5)                                */
/*                                                                    */
/*   Index 0: Primary service decl                                    */
/*   Index 1: AA1 chrc decl    (v1.0.0 bt_gatt_notify target)         */
/*   Index 2: AA1 chrc value                                          */
/*   Index 3: AA1 CCC                                                 */
/*   Index 4: AA2 chrc decl    (new, if CONNECTIVITY=y)               */
/*   Index 5: AA2 chrc value                                          */
/*   Index 6: AA2 CCC                                                 */
/*   Index 7: AA3 chrc decl    (if CONNECTIVITY=y AND BATTERY=y)      */
/*   Index 4: AA3 chrc decl    (if CONNECTIVITY=n AND BATTERY=y)      */
/*                                                                    */
/*   The AA3 index collapses from 7→4 when AA2 is disabled so the     */
/*   unusual Kconfig combination [KEYBEACON=y, CONNECTIVITY=n,        */
/*   BATTERY=y] still resolves correctly.                             */
/* ================================================================== */

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)
#define KBP_ATTR_AA2 4
#endif
#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)
#  if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)
#    define KBP_ATTR_AA3 7
#  else
#    define KBP_ATTR_AA3 4
#  endif
#endif

/* ================================================================== */
/* AA1 Layer + Modifier characteristic (KBP 1.0, byte-for-byte v1.0.0) */
/* ================================================================== */

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

/* ================================================================== */
/* Peripheral battery slot cache (data-model §E2)                      */
/*                                                                    */
/*   Shared between the Connectivity characteristic (byte 4 bit 1:    */
/*   right_online) and the Battery characteristic (byte [1]:          */
/*   right_percent). Updated by both conn_cb and batt_cb (idempotent) */
/*   from zmk_peripheral_battery_state_changed events; read on every  */
/*   payload rebuild. On integer boards the array has 0 slots and all */
/*   references are compiled out.                                     */
/* ================================================================== */

#if IS_ENABLED(CONFIG_ZMK_SPLIT) && IS_ENABLED(CONFIG_ZMK_SPLIT_BLE)
#  ifdef CONFIG_ZMK_SPLIT_BLE_CENTRAL_PERIPHERALS
#    define KBP_PERIPHERAL_SLOT_COUNT CONFIG_ZMK_SPLIT_BLE_CENTRAL_PERIPHERALS
#  else
#    define KBP_PERIPHERAL_SLOT_COUNT 1
#  endif
#else
#  define KBP_PERIPHERAL_SLOT_COUNT 0
#endif

#if KBP_PERIPHERAL_SLOT_COUNT > 0
struct peripheral_battery_slot {
    uint8_t last_percent;
    int64_t last_seen_ms;
};
static struct peripheral_battery_slot peripheral_slots[KBP_PERIPHERAL_SLOT_COUNT];
#endif

/*
 * Peripheral freshness window (TTL) in milliseconds.
 *
 * This gates both:
 *   - AA2.split_flags.right_online (bit 1): clears to 0 when the window
 *     expires without a fresh zmk_peripheral_battery_state_changed event.
 *   - AA3.right_percent: falls back to the unavailable sentinel (255) when
 *     stale, since the cached value is from the previous charge cycle.
 *
 * ZMK's default CONFIG_ZMK_BATTERY_REPORT_INTERVAL is 60 s, meaning the
 * peripheral BAS notify (which triggers the proxy event on the central)
 * arrives roughly once per minute. 75 s gives a 1.25× margin so a single
 * missed notify does not flip the online bit (jitter + occasional BLE
 * retransmit). Keyboard authors who shorten BATTERY_REPORT_INTERVAL can
 * leave this alone; those who lengthen it should bump this proportionally.
 *
 * Note: this is intentionally longer than 10 s (the value used in the
 * initial v1.1.0 release). See CHANGELOG.md v1.1.1 and the mismatch
 * between research.md §R1 and the actual ZMK event model (notify-based,
 * not sync-state-based) for the rationale.
 */
#define KBP_PERIPHERAL_FRESH_MS 75000

static inline bool kbp_peripheral_fresh(size_t slot) {
#if KBP_PERIPHERAL_SLOT_COUNT > 0
    if (slot >= KBP_PERIPHERAL_SLOT_COUNT) {
        return false;
    }
    return peripheral_slots[slot].last_seen_ms > 0 &&
           (k_uptime_get() - peripheral_slots[slot].last_seen_ms) <= KBP_PERIPHERAL_FRESH_MS;
#else
    (void)slot;
    return false;
#endif
}

/* ================================================================== */
/* AA2 Connectivity characteristic (KBP 1.1 §14.3)                     */
/* ================================================================== */

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)

#define KEYBEACON_CAP_IS_SPLIT           (IS_ENABLED(CONFIG_ZMK_SPLIT) ? 0x01u : 0u)
#define KEYBEACON_CAP_HAS_HOST_CONN      0x02u
#define KEYBEACON_CAP_HAS_PROFILE        0x04u
#define KEYBEACON_CAP_HAS_SPLIT_LINK     ((IS_ENABLED(CONFIG_ZMK_SPLIT) && \
                                            IS_ENABLED(CONFIG_ZMK_SPLIT_BLE)) ? 0x08u : 0u)
#define KEYBEACON_CAP_HAS_OUT_ENDPOINT   0x10u
#define KEYBEACON_CAP_HAS_LEFT_CHARGING  0u /* v1.1.0: no charger GPIO support */
#define KEYBEACON_CAP_HAS_RIGHT_CHARGING 0u /* v1.1.0: no charger GPIO support */

static const uint8_t keybeacon_cap_bits =
    KEYBEACON_CAP_IS_SPLIT | KEYBEACON_CAP_HAS_HOST_CONN | KEYBEACON_CAP_HAS_PROFILE |
    KEYBEACON_CAP_HAS_SPLIT_LINK | KEYBEACON_CAP_HAS_OUT_ENDPOINT;

struct __packed conn_payload {
    uint8_t capability_bits;
    uint8_t host_state;
    uint8_t profile_index;
    uint8_t profile_max_slots;
    uint8_t split_link_flags;
    uint8_t output_endpoint;
    uint8_t charging_flags;
};
BUILD_ASSERT(sizeof(struct conn_payload) == 7,
             "KBP 1.1 §14.3.1: Connectivity payload must be 7 bytes");

static uint8_t conn_payload_cache[7];
static uint8_t conn_payload_buf[7];

static void conn_build_payload(uint8_t *buf) {
    uint8_t host_state = 0;
    uint8_t profile_byte = 0;
    uint8_t profile_max = 0;
    uint8_t split_link = 0;
    uint8_t output_endpoint = 0;

    if (zmk_ble_active_profile_is_connected()) {
        host_state |= 0x01u;
    }

    int zmk_idx = zmk_ble_active_profile_index();
    if (zmk_idx < 0) {
        zmk_idx = 0;
    }
    uint8_t idx_1based = (uint8_t)(zmk_idx + 1);
    if (idx_1based > (uint8_t)ZMK_BLE_PROFILE_COUNT) {
        idx_1based = (uint8_t)ZMK_BLE_PROFILE_COUNT;
    }
    profile_byte = idx_1based & 0x7Fu;
    if (zmk_ble_active_profile_is_open()) {
        profile_byte |= 0x80u;
    }
    profile_max = (uint8_t)ZMK_BLE_PROFILE_COUNT;

#if IS_ENABLED(CONFIG_ZMK_SPLIT) && IS_ENABLED(CONFIG_ZMK_SPLIT_BLE)
    split_link |= 0x01u;
    if (kbp_peripheral_fresh(0)) {
        split_link |= 0x02u;
    }
#endif

    struct zmk_endpoint_instance ep = zmk_endpoints_selected();
    switch (ep.transport) {
    case ZMK_TRANSPORT_USB:
        output_endpoint = 1;
        break;
    case ZMK_TRANSPORT_BLE:
        output_endpoint = 2;
        break;
    default:
        output_endpoint = 0;
        break;
    }

    buf[0] = keybeacon_cap_bits;
    buf[1] = host_state;
    buf[2] = profile_byte;
    buf[3] = profile_max;
    buf[4] = split_link;
    buf[5] = output_endpoint;
    buf[6] = 0; /* charging_flags: 0 in v1.1.0 */
}

static ssize_t conn_read(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf,
                         uint16_t len, uint16_t offset) {
    return bt_gatt_attr_read(conn, attr, buf, len, offset, conn_payload_cache,
                             sizeof(conn_payload_cache));
}

static void conn_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {}

#endif /* CONFIG_ZMK_KEYBEACON_CONNECTIVITY */

/* ================================================================== */
/* AA3 Battery characteristic (KBP 1.1 §14.4)                          */
/* ================================================================== */

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)

#define KBP_BATT_PAYLOAD_LEN (IS_ENABLED(CONFIG_ZMK_SPLIT) ? 2 : 1)
BUILD_ASSERT(KBP_BATT_PAYLOAD_LEN == (IS_ENABLED(CONFIG_ZMK_SPLIT) ? 2 : 1),
             "KBP 1.1 §14.4.1: battery payload length must match is_split");

static uint8_t batt_payload_cache[KBP_BATT_PAYLOAD_LEN];
static uint8_t batt_payload_buf[KBP_BATT_PAYLOAD_LEN];
static int64_t batt_last_emit_ms;
static uint8_t central_battery_percent = 255; /* sentinel: no event yet */

static inline uint8_t kbp_clamp_percent(uint8_t v) {
    return (v == 255) ? 255 : MIN((uint8_t)100, v);
}

static void batt_build_payload(uint8_t *buf) {
    buf[0] = kbp_clamp_percent(central_battery_percent);
#if IS_ENABLED(CONFIG_ZMK_SPLIT)
#  if KBP_PERIPHERAL_SLOT_COUNT > 0
    if (kbp_peripheral_fresh(0)) {
        buf[1] = kbp_clamp_percent(peripheral_slots[0].last_percent);
    } else {
        buf[1] = 255;
    }
#  else
    buf[1] = 255;
#  endif
#endif
}

static ssize_t batt_read(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf,
                         uint16_t len, uint16_t offset) {
    return bt_gatt_attr_read(conn, attr, buf, len, offset, batt_payload_cache,
                             sizeof(batt_payload_cache));
}

static void batt_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {}

#endif /* CONFIG_ZMK_KEYBEACON_BATTERY */

/* ================================================================== */
/* GATT service definition — all characteristics in one block.         */
/* The AA1 BT_GATT_CHARACTERISTIC + BT_GATT_CCC lines are preserved    */
/* byte-for-byte from v1.0.0 to guarantee FR-G1 (KBP 1.0 regression).  */
/* ================================================================== */

BT_GATT_SERVICE_DEFINE(keybeacon_svc,
    BT_GATT_PRIMARY_SERVICE(KEYBEACON_SERVICE_UUID),
    BT_GATT_CHARACTERISTIC(KEYBEACON_CHRC_UUID,
                           BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_READ,
                           read_status, NULL, NULL),
    BT_GATT_CCC(ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)
    BT_GATT_CHARACTERISTIC(KEYBEACON_CONN_UUID,
                           BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_READ,
                           conn_read, NULL, NULL),
    BT_GATT_CCC(conn_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
#endif
#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)
    BT_GATT_CHARACTERISTIC(KEYBEACON_BATT_UUID,
                           BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_READ,
                           batt_read, NULL, NULL),
    BT_GATT_CCC(batt_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
#endif
);

/* ================================================================== */
/* AA1 build + notify (v1.0.0 identical logic)                         */
/* ================================================================== */

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

/* ================================================================== */
/* AA2 Connectivity update + notify + listener                         */
/* ================================================================== */

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)

static void conn_update_and_notify(void) {
    conn_build_payload(conn_payload_buf);
    if (memcmp(conn_payload_buf, conn_payload_cache, sizeof(conn_payload_cache)) == 0) {
        return;
    }
    memcpy(conn_payload_cache, conn_payload_buf, sizeof(conn_payload_cache));
    bt_gatt_notify(NULL, &keybeacon_svc.attrs[KBP_ATTR_AA2], conn_payload_cache,
                   sizeof(conn_payload_cache));
}

static int conn_cb(const zmk_event_t *eh) {
#if IS_ENABLED(CONFIG_ZMK_SPLIT) && IS_ENABLED(CONFIG_ZMK_SPLIT_BLE) && KBP_PERIPHERAL_SLOT_COUNT > 0
    const struct zmk_peripheral_battery_state_changed *pev =
        as_zmk_peripheral_battery_state_changed(eh);
    if (pev != NULL && pev->source < KBP_PERIPHERAL_SLOT_COUNT) {
        peripheral_slots[pev->source].last_percent = pev->state_of_charge;
        peripheral_slots[pev->source].last_seen_ms = k_uptime_get();
    }
#endif
    conn_update_and_notify();
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(conn_listener, conn_cb);
ZMK_SUBSCRIPTION(conn_listener, zmk_ble_active_profile_changed);
ZMK_SUBSCRIPTION(conn_listener, zmk_endpoint_changed);
#if IS_ENABLED(CONFIG_ZMK_SPLIT) && IS_ENABLED(CONFIG_ZMK_SPLIT_BLE)
ZMK_SUBSCRIPTION(conn_listener, zmk_peripheral_battery_state_changed);
#endif

#endif /* CONFIG_ZMK_KEYBEACON_CONNECTIVITY */

/* ================================================================== */
/* AA3 Battery update + notify + listener + 1 Hz work queue            */
/* ================================================================== */

#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)

static void batt_update_and_notify(bool event_driven) {
    batt_build_payload(batt_payload_buf);
    if (memcmp(batt_payload_buf, batt_payload_cache, sizeof(batt_payload_cache)) == 0) {
        return;
    }
    int64_t now = k_uptime_get();
    if (!event_driven && (now - batt_last_emit_ms) < 1000) {
        return;
    }
    memcpy(batt_payload_cache, batt_payload_buf, sizeof(batt_payload_cache));
    batt_last_emit_ms = now;
    bt_gatt_notify(NULL, &keybeacon_svc.attrs[KBP_ATTR_AA3], batt_payload_cache,
                   sizeof(batt_payload_cache));
}

static int batt_cb(const zmk_event_t *eh) {
    const struct zmk_battery_state_changed *bev = as_zmk_battery_state_changed(eh);
    if (bev != NULL) {
        central_battery_percent = bev->state_of_charge;
    }
#if IS_ENABLED(CONFIG_ZMK_SPLIT) && IS_ENABLED(CONFIG_ZMK_SPLIT_BLE) && KBP_PERIPHERAL_SLOT_COUNT > 0
    const struct zmk_peripheral_battery_state_changed *pev =
        as_zmk_peripheral_battery_state_changed(eh);
    if (pev != NULL && pev->source < KBP_PERIPHERAL_SLOT_COUNT) {
        /* Idempotent — conn_cb may have already done this; writing the same
         * values again is harmless and keeps batt_cb self-contained. */
        peripheral_slots[pev->source].last_percent = pev->state_of_charge;
        peripheral_slots[pev->source].last_seen_ms = k_uptime_get();
    }
#endif
    batt_update_and_notify(true);
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(batt_listener, batt_cb);
ZMK_SUBSCRIPTION(batt_listener, zmk_battery_state_changed);
#if IS_ENABLED(CONFIG_ZMK_SPLIT) && IS_ENABLED(CONFIG_ZMK_SPLIT_BLE)
ZMK_SUBSCRIPTION(batt_listener, zmk_peripheral_battery_state_changed);
#endif

static void batt_floor_work_cb(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(batt_floor_work, batt_floor_work_cb);

static void batt_floor_work_cb(struct k_work *work) {
    batt_update_and_notify(false);
    k_work_schedule(&batt_floor_work, K_SECONDS(1));
}

#endif /* CONFIG_ZMK_KEYBEACON_BATTERY */

/* ================================================================== */
/* Module init                                                        */
/* ================================================================== */

static int keybeacon_init(void) {
    build_payload(payload_cache, &payload_len_cache);
#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_CONNECTIVITY)
    conn_build_payload(conn_payload_cache);
#endif
#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_BATTERY)
    batt_build_payload(batt_payload_cache);
    k_work_schedule(&batt_floor_work, K_SECONDS(1));
#endif
    return 0;
}

SYS_INIT(keybeacon_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
