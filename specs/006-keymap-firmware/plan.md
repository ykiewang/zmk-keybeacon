# Implementation Plan: 006-keymap-firmware

**Branch**: `feat/006-keymap-firmware` | **Date**: 2026-11-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-keymap-firmware/spec.md`

## Summary

在 `zmk-keybeacon` 模块新增 KBP 1.3 两个可选 BLE 特征：`KeymapMeta`（`AA440AA5`，READ only，含 CRC32 + layer 元信息）和 `KeymapData`（`AA440AA6`，READ + ATT READ_BLOB 分块，含物理布局坐标 + keycode 表），通过 `CONFIG_ZMK_KEYBEACON_KEYMAP` Kconfig 控制，默认启用。

## Technical Context

**Language/Version**: C (Zephyr/ZMK，C11), CMake

**Primary Dependencies**: Zephyr RTOS, ZMK（`zmk/keymap.h`, `zmk/physical_layouts.h`, `zephyr/sys/crc.h`）

**Storage**: N/A（静态 buffer，编译时分配）

**Testing**: Python 单元测试（`scripts/tests/`，现有模式）+ conformance CLI 验证

**Target Platform**: Zephyr RTOS，ZMK 固件

**Project Type**: Zephyr firmware module

**Performance Goals**: KeymapMeta READ ≤ 200ms，KeymapData 完整读取（50键×5层≈2.5KB）≤ 1s

**Constraints**: 向后兼容 KBP 1.0/1.1/1.2，`CONFIG_ZMK_KEYBEACON_KEYMAP=n` 时零代码增量，service UUID 不变

**Scale/Scope**: 单文件扩展（`keybeacon.c`），新增约 200 行 C 代码 + Kconfig 条目

## Constitution Check

| 原则 | 评估 |
|------|------|
| I. Wire-Contract Is Upstream | UUID 和 payload 格式在 `contracts/ble-keymap.md` 中先于实现草稿；ratify 后由 `keybeacon/protocol/` 收录 |
| II. Backward Compatibility | 新特征由 `CONFIG_ZMK_KEYBEACON_KEYMAP`（默认 y）控制；`=n` 时 GATT shape 与 KBP 1.2 完全相同；service UUID 不变 |
| III. Keyboard-Independent | `keybeacon.c` 不引入 board 判断；物理布局来自 Devicetree `physical_layout` 节点 |
| IV. Observable Degradation | `physical_layout` 缺失时线性回退；未知 behavior 以 `0xFF` 标记；sentinel 不猜测 |
| V. Spec-First | 本 spec → plan → tasks → analyze → impl；contracts 先于 C 代码 |
| VI. Build-Time Compatibility Contract | 新 ZMK 符号在 `compatibility.yaml` 声明；`module_version` bump 1.2.1 → 1.3.0 |

**GATE 通过**，可进入 Phase 1。

## Project Structure

### Documentation (this feature)

```text
specs/006-keymap-firmware/
├── spec.md
├── research.md
├── plan.md              ← 本文件
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── ble-keymap.md    ← Phase 1 output（UUID、payload 字节格式）
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code

```text
keybeacon.c                   ← MODIFY: 追加 KeymapMeta + KeymapData 特征块
Kconfig.keybeacon              ← MODIFY: 新增 CONFIG_ZMK_KEYBEACON_KEYMAP + MAX_BYTES
compatibility.yaml             ← MODIFY: 新增 required_symbols + module_version bump
```

## Implementation Phases

### Phase 0（已完成）: Research
见 `research.md`。

### Phase 1: Design（本阶段）

1. **contracts/ble-keymap.md** — 定义 UUID、`key_entry` / `binding_entry` 字节格式、ATT READ_BLOB 分块协议
2. **data-model.md** — C 结构体定义、`behavior_id` 枚举、序列化顺序、CRC32 计算范围
3. **quickstart.md** — Given/When/Then 场景映射 FR/SC

### Phase 2: Tasks

由 `/speckit-tasks` 生成 `tasks.md`，分解为原子任务。

### Phase 3: Analyze

`/speckit-analyze` 验证 CRITICAL=0, HIGH=0。

### Phase 4: Implement（执行顺序）

1. `Kconfig.keybeacon` — 新增 `CONFIG_ZMK_KEYBEACON_KEYMAP`（bool，default y）和 `CONFIG_ZMK_KEYBEACON_KEYMAP_MAX_BYTES`（int，default 4096）
2. `compatibility.yaml` — 新增三个 required_symbols；bump module_version → 1.3.0
3. `keybeacon.c` — UUID 段新增 `AA440AA5`/`AA440AA6`；ATT handle map 注释更新；`#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_KEYMAP)` 块：
   - `build_keymap_payload()` — SYS_INIT 阶段调用，序列化 `key_entry` 数组 + `binding_entry` 二维数组，计算 CRC32
   - `read_keymap_meta()` — READ handler
   - `read_keymap_data()` — READ handler（`bt_gatt_attr_read` 自动处理 READ_BLOB offset）
   - GATT 服务声明追加两个新特征
4. `protocol/README.md` / `CHANGELOG.md` — 双语更新 KBP 1.3 条目

## Complexity Tracking

> 无 Constitution 违规，表格留空。
