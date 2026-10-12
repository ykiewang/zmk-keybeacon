/* Fake ZMK ble.h — common across all four fixtures.
 * Carries the three profile-related symbols that zmk-keybeacon depends on.
 */

bool zmk_ble_active_profile_is_connected(void);
int  zmk_ble_active_profile_index(void);
bool zmk_ble_active_profile_is_open(void);
