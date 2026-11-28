# Data Model: 006-keymap-firmware

**Date**: 2026-11-26 | **Phase**: 1

## C 结构体定义

### key_entry（10 字节，小端序）

```c
struct key_entry {
    int16_t  x;   /* 0.01u，键左上角 x */
    int16_t  y;   /* 0.01u，键左上角 y */
    uint8_t  w;   /* 0.1u，宽 */
    uint8_t  h;   /* 0.1u，高 */
    int16_t  r;   /* 0.01°，旋转角（顺时针为正） */
    int16_t  rx;  /* 0.01u，旋转原点 x */
    int16_t  ry;  /* 0.01u，旋转原点 y */
} __packed;
```

### binding_entry（5 字节，小端序）

```c
struct binding_entry {
    uint8_t  behavior_id;
    uint16_t param1;
    uint16_t param2;
} __packed;
```

## behavior_id 枚举

```c
enum kbp_behavior_id {
    KBP_BHV_KP           = 0x01,
    KBP_BHV_MT           = 0x02,
    KBP_BHV_LT           = 0x03,
    KBP_BHV_MO           = 0x04,
    KBP_BHV_TO           = 0x05,
    KBP_BHV_TOG          = 0x06,
    KBP_BHV_SL           = 0x07,
    KBP_BHV_SK           = 0x08,
    KBP_BHV_TRANS        = 0x09,
    KBP_BHV_NONE         = 0x0A,
    KBP_BHV_KEY_REPEAT   = 0x0B,
    KBP_BHV_GRESC        = 0x0C,
    KBP_BHV_CAPS_WORD    = 0x0D,
    KBP_BHV_KT           = 0x0E,
    KBP_BHV_TD           = 0x10,
    KBP_BHV_MACRO        = 0x11,
    KBP_BHV_MOD_MORPH    = 0x12,
    KBP_BHV_BT           = 0x20,
    KBP_BHV_OUT          = 0x21,
    KBP_BHV_RESET        = 0x22,
    KBP_BHV_BOOTLOADER   = 0x23,
    KBP_BHV_MKP          = 0x30,
    KBP_BHV_RGB          = 0x40,
    KBP_BHV_BL           = 0x41,
    KBP_BHV_EXT_POWER    = 0x42,
    KBP_BHV_SOFT_OFF     = 0x43,
    KBP_BHV_STUDIO_UNLOCK= 0x44,
    KBP_BHV_UNKNOWN      = 0xFF,
};
```

## Behavior Dev Name → behavior_id 映射

| `.behavior_dev` 字符串前缀 | behavior_id |
|--------------------------|-------------|
| `"behavior_key_press"` | KP |
| `"behavior_hold_tap"` + binding param1 是 modifier | MT |
| `"behavior_hold_tap"` + binding param1 是 layer | LT |
| `"behavior_momentary_layer"` | MO |
| `"behavior_to_layer"` | TO |
| `"behavior_toggle_layer"` | TOG |
| `"behavior_sticky_layer"` | SL |
| `"behavior_sticky_key"` | SK |
| `"behavior_transparent"` | TRANS |
| `"behavior_none"` | NONE |
| `"behavior_key_repeat"` | KEY_REPEAT |
| `"behavior_gresc"` | GRESC |
| `"behavior_caps_word"` | CAPS_WORD |
| `"behavior_key_toggle"` | KT |
| `"behavior_tap_dance"` | TD |
| `"behavior_macro"` / `"behavior_macro_one_param"` / `"behavior_macro_two_param"` | MACRO |
| `"behavior_mod_morph"` | MOD_MORPH |
| `"behavior_bluetooth"` | BT |
| `"behavior_outputs"` | OUT |
| `"behavior_sys_reset"` | RESET |
| `"behavior_bootloader"` | BOOTLOADER |
| `"behavior_mouse_key_press"` | MKP |
| `"behavior_rgb_underglow"` | RGB |
| `"behavior_backlight"` | BL |
| `"behavior_ext_power"` | EXT_POWER |
| `"behavior_soft_off"` | SOFT_OFF |
| `"behavior_studio_unlock"` | STUDIO_UNLOCK |
| 其他 | UNKNOWN (0xFF) |

## KeymapData Payload 布局

```
偏移 0：key_entry[0]           (10 字节)
偏移 10：key_entry[1]          (10 字节)
...
偏移 10*(N-1)：key_entry[N-1]  (10 字节，N = key_count)

偏移 10*N：binding_entry[layer=0][key=0]   (5 字节)
偏移 10*N+5：binding_entry[layer=0][key=1]
...
binding_entry[layer=L-1][key=N-1]           (layer 优先，逐 key 顺序)
```

总字节数：`10 * key_count + 5 * layer_count * key_count`

## KeymapMeta Payload 布局

```
字节 [0..3]  : CRC32（uint32_t LE），对 KeymapData 完整 payload 计算
字节 [4]     : layer_count（uint8_t）
字节 [5..6]  : key_count（uint16_t LE）
字节 [7..]   : layer_names（UTF-8，各名称以 '\0' 分隔，最后一个名称后无额外 '\0'）
```

## CRC32 计算

使用 Zephyr `crc32_ieee(data, len)`（`#include <zephyr/sys/crc.h>`），对 KeymapData 完整 buffer 计算。

## Linear Fallback（physical_layout 缺失）

```c
key_entry fallback = {
    .x  = (int16_t)(key_index * 100),
    .y  = 0,
    .w  = 10,
    .h  = 10,
    .r  = 0,
    .rx = 0,
    .ry = 0,
};
```

## compatibility.yaml 新增符号

```yaml
- name: zmk_physical_layouts_get_current_selected
  header: zmk/physical_layouts.h
  used_in: keybeacon.c

- name: zmk_keymap_layer_binding
  header: zmk/keymap.h
  used_in: keybeacon.c

- name: crc32_ieee
  header: zephyr/sys/crc.h
  used_in: keybeacon.c
```
