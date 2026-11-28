struct zmk_behavior_binding { const char *behavior_dev; uint32_t param1; uint32_t param2; };
typedef uint8_t zmk_keymap_layer_index_t;
typedef uint8_t zmk_keymap_layer_id_t;
#define ZMK_KEYMAP_LAYER_ID_INVAL UINT8_MAX
zmk_keymap_layer_id_t zmk_keymap_layer_index_to_id(zmk_keymap_layer_index_t index);
const struct zmk_behavior_binding *zmk_keymap_get_layer_binding_at_idx(zmk_keymap_layer_id_t layer, uint16_t binding_idx);
const char *zmk_keymap_layer_name(zmk_keymap_layer_id_t layer_id);
