/* Fake ZMK endpoints.h — zmk-legacy fixture (ZMK < 6e7e0de2, 2026-02-12).
 * Mirrors the real pre-rename API surface so zmk-keybeacon's symbol probe
 * sees `zmk_endpoints_selected()` and emits ZMK_KEYBEACON_HAS_LEGACY_ENDPOINT.
 */

struct zmk_endpoint_instance {
    int transport;
    int reserved;
};

/* The legacy name — present here, probed as primary match */
struct zmk_endpoint_instance zmk_endpoints_selected(void);
