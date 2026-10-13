/* Fake ZMK endpoints.h — zmk-renamed fixture (ZMK ≥ 6e7e0de2, 2026-02-12).
 * Only the NEW name is present; the probe hits via the `fallback` list,
 * so ZMK_KEYBEACON_HAS_LEGACY_ENDPOINT must NOT be emitted.
 */

struct zmk_endpoint_instance {
    int transport;
    int reserved;
};

/* The new name — probe hits here via fallback */
struct zmk_endpoint_instance zmk_endpoint_get_selected(void);
