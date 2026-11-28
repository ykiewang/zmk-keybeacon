# Research: 006-keymap-firmware

**Date**: 2026-11-26 | **Phase**: 0 — Pre-plan research

## Codebase Inventory

### zmk-keybeacon 结构

```
zmk-keybeacon/
├── keybeacon.c               # 主实现文件（KBP 1.0/1.1/1.2 全部在此）
├── Kconfig.keybeacon          # 功能开关定义
├── CMakeLists.txt             # 编译入口
├── keybeacon.cmake            # central-role 检测 + 模块注入
├── compatibility.yaml         # ZMK API 依赖声明（单一来源）
├── cmake/zmk_compat.cmake     # 配置期 fail-fast 检查
├── scripts/                   # Python 辅助脚本 + 测试
├── zephyr/module.yml          # Zephyr module 声明
└── specs/
    └── 006-keymap-firmware/   # 本 feature spec 目录
```

### keybeacon.c 现有模式（供 006 遵循）

- **条件编译**：每个 KBP 版本用 `#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_xxx)` 包围，编译为 n 时零开销
- **UUID 定义**：`#define KEYBEACON_xxx_UUID BT_UUID_DECLARE_128(...)` 在 UUID 段统一定义
- **ATT handle 注释**：Attribute-index map 注释块，逐项列出 handle offset（新增特征须维护此注释）
- **READ handler 模式**：`static ssize_t read_xxx(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf, uint16_t len, uint16_t offset)` → `bt_gatt_attr_read(conn, attr, buf, len, offset, &data, sizeof(data))`
- **GATT 服务声明**：`BT_GATT_SERVICE_DEFINE` 宏，单一服务块，所有特征按 UUID 顺序追加
- **模块版本**：`compatibility.yaml` 中 `module_version` 字段，新特征需要 bump

### ZMK Physical Layout API

ZMK 通过 Devicetree 描述物理布局，核心节点：

```dts
/ {
    keymap {
        compatible = "zmk,keymap";
        ...
    };
    physical_layout0: physical_layout_0 {
        compatible = "zmk,physical-layout";
        display-name = "Default";
        keys = <&key_physical_attrs ...>;
        // 每个 key: w h x y r rx ry（以 0.01u 为单位）
    };
};
```

ZMK Studio（`zmk/physical_layouts.h`）已有读取这些节点的 C API，可直接复用：
- `zmk_physical_layouts_get_current_selected()`
- 通过 `DT_FOREACH_PROP_ELEM` 遍历 `keys` 属性

### ZMK Keymap Bindings API

- `zmk/keymap.h`：`zmk_keymap_layer_binding(layer, position)` 返回 `zmk_behavior_binding`
- `zmk_behavior_binding` 含 `.behavior_dev`（行为名字符串）+ `.param1` + `.param2`
- 行为名映射到 `behavior_id` 枚举需要手工比较字符串（无反射 API）

### CRC32

- Zephyr 内置 `#include <zephyr/sys/crc.h>`，`crc32_ieee(data, len)` 实现 IEEE 802.3 CRC32
- 对 `KeymapData` 完整 payload 计算，分块传输不影响 CRC（CRC 在 Meta 中，DataPayload 不变）

### ATT READ_BLOB

- Zephyr GATT READ handler 的 `offset` 参数直接对应 ATT READ_BLOB offset
- `bt_gatt_attr_read(conn, attr, buf, len, offset, data, data_len)` 自动处理 offset 切片
- 因此固件侧只需保持 payload 静态可寻址（全量 buffer 或流式生成均可）
- **方案选择**：编译时将完整 payload 序列化为静态 buffer（`CONFIG_ZMK_KEYBEACON_KEYMAP_MAX_BYTES`，默认 4KB），在 `SYS_INIT` 阶段填充；keymap 变化时（ZMK 目前不支持运行时 keymap 修改）不需要动态更新

### compatibility.yaml 新增符号

006 需要在 `required_symbols` 中声明：
- `zmk_physical_layouts_get_current_selected`（zmk/physical_layouts.h）
- `zmk_keymap_layer_binding`（zmk/keymap.h）
- `crc32_ieee`（zephyr/sys/crc.h）

## 关键风险 & 决策

| 风险 | 决策 |
|------|------|
| `physical_layouts.h` API 在旧 ZMK 不存在 | `compatibility.yaml` 声明为 required；缺失时 fail-fast + 有意义的错误信息；`CONFIG_ZMK_KEYBEACON_KEYMAP` 自动依赖此 API |
| Keymap payload 超过 ATT MTU | 静态 buffer 大小由 `CONFIG_ZMK_KEYBEACON_KEYMAP_MAX_BYTES`（Kconfig）控制，默认 4096；`bt_gatt_attr_read` 的 offset 参数自动切片 |
| `physical_layout` 节点缺失（老 shield） | 回退为线性布局（x = i×100, y = 0, w = 10, h = 10, r = 0）|
| 未知 behavior dev name | `behavior_id = 0xFF`，param1 = 低 16 位哈希，不阻塞其他键 |
| module_version bump | 006 合并后 compatibility.yaml `module_version` 从 1.2.1 → 1.3.0（MINOR）|

## Constitution Checklist（Phase 0）

- [x] **I. Wire-Contract Is Upstream**：UUID 和 payload 格式在 `specs/006-keymap-firmware/contracts/` 草稿，ratify 后由上游 `keybeacon/protocol/` 收录；本仓库仅实现
- [x] **II. Backward Compatibility**：新特征由 `CONFIG_ZMK_KEYBEACON_KEYMAP`（默认 y）控制，可编译为 n 还原 1.2 GATT shape；service UUID 不变
- [x] **III. Keyboard-Independent**：`keybeacon.c` 不引入 board 判断；物理布局来自 Devicetree，键盘无关
- [x] **IV. Observable Degradation**：`physical_layout` 缺失时线性回退；未知 behavior 以 0xFF 标记，不崩溃
- [x] **V. Spec-First**：本 spec → plan → tasks → analyze → impl；contracts 先于 C 代码
- [x] **VI. Build-Time Compatibility Contract**：新 ZMK 符号必须在 `compatibility.yaml` 声明
