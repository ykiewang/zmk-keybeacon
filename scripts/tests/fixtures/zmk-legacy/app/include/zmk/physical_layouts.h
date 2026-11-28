struct zmk_key_physical_attrs { int16_t width; int16_t height; int16_t x; int16_t y; };
struct zmk_physical_layout { const char *display_name; const struct zmk_key_physical_attrs *keys; size_t keys_len; };
size_t zmk_physical_layouts_get_list(struct zmk_physical_layout const *const **phys_layouts);
int zmk_physical_layouts_get_selected(void);
