# Tasks: 006-keymap-firmware

**Input**: Design documents from `/specs/006-keymap-firmware/`

**Prerequisites**: spec.md ✅, plan.md ✅, research.md ✅, data-model.md ✅, contracts/ble-keymap.md ✅

## Phase 1: Foundation（阻塞所有后续工作）

**Purpose**: Kconfig、compatibility.yaml、UUID 定义——所有 US 均依赖这三项

- [ ] T001 在 `Kconfig.keybeacon` 中新增：`CONFIG_ZMK_KEYBEACON_KEYMAP`（bool，default y，depends on ZMK_KEYBEACON）和 `CONFIG_ZMK_KEYBEACON_KEYMAP_MAX_BYTES`（int，default 4096，depends on ZMK_KEYBEACON_KEYMAP）
- [ ] T002 在 `compatibility.yaml` 中：bump `module_version` 1.2.1 → 1.3.0；新增三条 `required_symbols`（`zmk_physical_layouts_get_current_selected`、`zmk_keymap_layer_binding`、`crc32_ieee`）及其 header / used_in 字段
- [ ] T003 在 `keybeacon.c` UUID 段新增 `KEYBEACON_META_UUID`（`AA440AA5-…`）和 `KEYBEACON_DATA_UUID`（`AA440AA6-…`），用 `#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_KEYMAP)` 包围
- [ ] T004 更新 `keybeacon.c` 顶部 ATT handle map 注释，记录 AA5/AA6 在各 Kconfig 组合下的 handle offset

**Checkpoint**: Foundation 完成后 US1~US3 可推进

---

## Phase 2: US1 — KeymapMeta 特征（P1）🎯 MVP

**Goal**: app 读取 `AA440AA5`，得到正确的 CRC32 + layer 元信息

**Independent Test**: quickstart.md 场景 1（nRF Connect 验证）

- [ ] T010 在 `keybeacon.c` 的 `#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_KEYMAP)` 块中声明：`keymap_meta_buf[256]`、`keymap_meta_len`
- [ ] T011 实现 `build_keymap_meta(meta_buf, data_buf, data_len)`：写入 CRC32（4B LE）、`layer_count`（1B）、`key_count`（2B LE）、layer 名称列表（`\0` 分隔）
- [ ] T012 实现 `read_keymap_meta()` READ handler：`bt_gatt_attr_read(conn, attr, buf, len, offset, keymap_meta_buf, keymap_meta_len)`
- [ ] T013 在 `BT_GATT_SERVICE_DEFINE` 宏中追加 `AA440AA5` 特征声明（`BT_GATT_CHARACTERISTIC` + `BT_GATT_READ` only）

**Checkpoint**: US1 完成后可用 nRF Connect 验证 KeymapMeta payload（quickstart.md 场景 1）

---

## Phase 3: US2 — KeymapData 特征（P1）

**Goal**: app 通过 ATT READ_BLOB 完整读取 `AA440AA6`，拼合后得到物理布局 + keycode 表

**Independent Test**: quickstart.md 场景 2（Python 脚本解析验证）

- [ ] T020 在 `keybeacon.c` 的 KEYMAP 块中声明：`keymap_data_buf[CONFIG_ZMK_KEYBEACON_KEYMAP_MAX_BYTES]`、`keymap_data_len`
- [ ] T021 实现 `build_keymap_data(data_buf, max_len)`：
  - Segment 1：遍历 `physical_layout` Devicetree 节点，序列化每个 `key_entry`（x/y/w/h/r/rx/ry，10 字节）；节点缺失时使用线性回退
  - Segment 2：双重循环 layer × key，调用 `zmk_keymap_layer_binding(layer, pos)`，将 `.behavior_dev` 字符串映射到 `behavior_id` 枚举，序列化 `binding_entry`（5 字节）；未识别 behavior 以 `0xFF` 标记
- [ ] T022 实现 `read_keymap_data()` READ handler：`bt_gatt_attr_read(conn, attr, buf, len, offset, keymap_data_buf, keymap_data_len)`（ATT READ_BLOB offset 由 `bt_gatt_attr_read` 自动处理）
- [ ] T023 在 `SYS_INIT` 中注册 `build_keymap_payload()`（调用 `build_keymap_data` 后再调用 `build_keymap_meta`，保证 Meta 中的 CRC 对应已构建的 Data）
- [ ] T024 在 `BT_GATT_SERVICE_DEFINE` 宏中追加 `AA440AA6` 特征声明

**Checkpoint**: US2 完成后可用 Python 脚本验证完整 KeymapData（quickstart.md 场景 2）

---

## Phase 4: US3 — 旋转键坐标（P2）

**Goal**: ergo 键盘旋转键的 `r`/`rx`/`ry` 字段与 Devicetree 节点值一致

**Independent Test**: quickstart.md 场景 4

- [ ] T030 在 `build_keymap_data` 的 Segment 1 中确认 `r`/`rx`/`ry` 读取路径使用 `DT_PROP` 而非推断；在 totem board 配置上手工验证旋转键坐标（至少一个 r ≠ 0 的键）

---

## Phase 5: CONFIG_ZMK_KEYBEACON_KEYMAP=n 零增量（FR-009）

- [ ] T040 编译 `CONFIG_ZMK_KEYBEACON_KEYMAP=n` 配置，确认：编译通过，`.elf` 大小增量为 0（允许链接对齐误差），nRF Connect 枚举不到 AA5/AA6

---

## Phase 6: 脚本测试与 compatibility 更新

- [ ] T050 在 `scripts/tests/` 中更新 fixture 和测试，覆盖 `compatibility.yaml` 中新增的三个 required_symbols（遵循现有 `scripts/tests/` 模式）
- [ ] T051 运行 `python scripts/validate_compat.py` 确认无报错
- [ ] T052 运行 `python scripts/update-readme-table.py`（如果存在），更新 README COMPAT 块

---

## Dependencies & Execution Order

```
Phase 1（T001~T004）
  ↓
Phase 2（T010~T013）
  ↓
Phase 3（T020~T024）
  ↓
Phase 4（T030）+ Phase 5（T040，可与 Phase 4 并行）
  ↓
Phase 6（T050~T052）
```

- T003/T004 可与 T001/T002 并行（不同文件）
- Phase 6 的脚本测试依赖 T002（compatibility.yaml 修改）完成
