/* Fake ZMK endpoints.h — zmk-missing fixture.
 * Both the legacy and the new symbol are absent, simulating a hypothetical
 * breaking removal of the endpoints API altogether. Probe must fail-fast.
 */

struct zmk_endpoint_instance {
    int transport;
    int reserved;
};

/* Neither zmk_endpoints_selected nor zmk_endpoint_get_selected declared here. */
