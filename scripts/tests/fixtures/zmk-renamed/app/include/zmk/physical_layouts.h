struct zmk_physical_layout_key_position { int16_t x; int16_t y; uint8_t w; uint8_t h; };
struct zmk_physical_layout { uint8_t key_count; const struct zmk_physical_layout_key_position *keys; };
const struct zmk_physical_layout *zmk_physical_layouts_get_current_selected(void);
