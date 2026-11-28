# Feature Specification: 键位图固件侧（Keymap Firmware）

**Feature Branch**: `006-keymap-firmware`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "在 zmk-keybeacon 模块新增 KBP 1.3 BLE 特征，序列化 ZMK physical_layout 坐标与 keymap bindings，支持 KeymapMeta CRC32 校验和 KeymapData 全量读取，配合 keybeacon 主仓库 006-keymap-viewer（app 侧）实现零配置键位图速查"

## Clarifications

### Session 2026-11-26

- Q: 协议版本号？→ A: KBP 1.3 MINOR 增量，新增两个可选特征，向后兼容 KBP 1.0/1.1/1.2。
- Q: `KeymapMeta` 和 `KeymapData` 是否分两个特征？→ A: 是。`KeymapMeta`（READ only，轻量）供 app 快速读取 CRC32 和元信息；`KeymapData`（READ，分块协议）传输完整布局和 keycode 表。
- Q: 分块协议如何设计？→ A: app 发送 `(offset, max_len)` 请求到 KeymapData 控制点，固件返回对应分块；ATT MTU 约 244 字节，单 layer 50 键约 500 字节，需要分 2~3 包。
- Q: 物理布局坐标来源？→ A: 直接读取 ZMK `physical_layout` Devicetree 节点（`key-positions` + `transform`），单位 0.01u，与 ZMK Studio 同源。
- Q: keycode 编码方式？→ A: 枚举每个 binding 的类型和参数，序列化为固定结构体（见 Key Entities），未识别 behavior 以 `behavior_id=0xFF` 标记。
- Q: CRC32 算法？→ A: 标准 CRC32（ISO 3309 / IEEE 802.3），对全部 layer × key binding 字节序列计算，ZMK 自带 `crc32` 实现可直接调用。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 固件正确上报 KeymapMeta（Priority: P1）

app 连接键盘后，读取 `KeymapMeta` 特征，得到正确的 CRC32、layer 数量和 layer 名称列表，整个 READ transaction 在 200ms 内完成。

**Why this priority**: `KeymapMeta` 是 app 侧缓存机制的入口，CRC 不准确会导致 app 永远使用过期缓存或永远全量拉取。

**Independent Test**: 用 conformance CLI 或 nRF Connect 读取 `KeymapMeta` 特征，解析 payload，验证 CRC32 与手工计算值一致。

**Acceptance Scenarios**:

1. **Given** 已烧录含 `CONFIG_ZMK_KEYBEACON=y` 且 KBP 1.3 支持的固件，**When** app 读取 `KeymapMeta`，**Then** 返回 payload 包含：4 字节 CRC32、1 字节 layer 数量、各 layer 名称（NUL 分隔字符串）。
2. **Given** 固件重新编译（keymap 有改动），**When** 重新计算 CRC32，**Then** CRC32 与上次不同，app 能检测到变化并重新拉取。
3. **Given** `CONFIG_ZMK_KEYBEACON_KEYMAP=n`（显式关闭键位图特征），**When** app 枚举特征，**Then** `KeymapMeta` 和 `KeymapData` 均不存在，app 不崩溃。

---

### User Story 2 - 固件正确上报 KeymapData（Priority: P1）

app 通过分块协议读取 `KeymapData`，拼合后得到完整的物理布局坐标（所有键的 x/y/w/h/r）和所有 layer 的 keycode 数组，数据与键盘实际配置一致。

**Why this priority**: 这是渲染键位图的原始数据来源，任何字段错误都会导致 app 侧渲染错误。

**Independent Test**: 写一个 Python 脚本，读取 `KeymapData` 全部分块，解析为结构体数组，与 `.keymap` 文件手工对比至少 3 个键的 binding 值。

**Acceptance Scenarios**:

1. **Given** 键盘有 3 个 layer、34 个键，**When** app 完整读取 `KeymapData`，**Then** 解析出 34 条物理布局记录和 3 × 34 = 102 条 binding 记录，数量正确。
2. **Given** 某键配置为 `&mt LSHIFT A`，**When** app 读取该键的 binding，**Then** 解析出 `behavior_id = MT, param1 = HID_LSHIFT, param2 = HID_A`。
3. **Given** 某键配置为 `&trans`，**When** app 读取，**Then** `behavior_id = TRANS`，无参数。
4. **Given** 请求超出数据范围的 offset，**When** 固件收到请求，**Then** 返回空 payload 或 ATT Error，不崩溃。

---

### User Story 3 - 旋转键坐标正确序列化（Priority: P2）

ergo 键盘（如 Dactyl、Totem）的旋转键，坐标和旋转角度在 `KeymapData` 中与 `physical_layout` 节点一致。

**Why this priority**: 旋转键是 ergo 键盘的核心特征，坐标错误会导致 app 侧渲染出错位的键位图，影响用户判断。

**Independent Test**: 在 adept 键盘上验证已知旋转角度的键，对比 `physical_layout` 节点值与 `KeymapData` 解析值。

**Acceptance Scenarios**:

1. **Given** 某键在 `physical_layout` 中 `r = 1500`（15.00 度），**When** app 读取 `KeymapData`，**Then** 该键的 `r` 字段为 `1500`（int16_t，单位 0.01 度）。
2. **Given** 某键无旋转（`r = 0`），**When** app 读取，**Then** `r` 字段为 `0`。

---

### Edge Cases

- `physical_layout` 节点缺失（老 shield 未定义）时，固件应回退为线性布局（逐行排列，每键 1u × 1u），不崩溃。
- keymap 中的自定义 behavior（非内置类型）以 `behavior_id=0xFF` + 原始 binding 字符串哈希标记，不阻塞其他键的序列化。
- layer 名称未定义时，以空字符串填充，`KeymapMeta` payload 仍合法。
- 分块请求 offset 未对齐时，固件按字节对齐处理，不截断记录。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 固件 MUST 在 KBP service（`AA440AA0-…`）下新增 `KeymapMeta` 特征（UUID `AA440AA5-…`），属性 `READ`，编译期默认启用（由 `CONFIG_ZMK_KEYBEACON_KEYMAP` 控制，默认 `y`）。
- **FR-002**: `KeymapMeta` payload MUST 包含：CRC32（4 字节 LE）、layer 数量（1 字节）、key 数量（2 字节 LE）、layer 名称列表（UTF-8，各名称以 `\0` 分隔）。
- **FR-003**: 固件 MUST 在同一 KBP service 下新增 `KeymapData` 特征（UUID `AA440AA6-…`），属性 `READ`，支持 ATT `READ_BLOB` 分块读取。
- **FR-004**: `KeymapData` payload MUST 按以下顺序排列：① 物理布局段（所有键的 `key_entry` 结构体，按键序）；② keycode 段（所有 layer × 所有键的 `binding_entry` 结构体，layer 优先）。
- **FR-005**: `key_entry` 结构体 MUST 包含：`x`（int16_t，0.01u）、`y`（int16_t）、`w`（uint8_t，0.1u）、`h`（uint8_t）、`r`（int16_t，0.01 度）、`rx`（int16_t，旋转原点 x）、`ry`（int16_t，旋转原点 y），共 10 字节。
- **FR-006**: `binding_entry` 结构体 MUST 包含：`behavior_id`（uint8_t，枚举值见 data-model）、`param1`（uint16_t）、`param2`（uint16_t），共 5 字节。
- **FR-007**: CRC32 MUST 对 `KeymapData` 完整 payload 字节序列计算，使用 ZMK 内置 `crc32` 实现（`#include <zephyr/sys/crc.h>`）。
- **FR-008**: 若 `physical_layout` 节点缺失，固件 MUST 回退为线性布局（x = key_index × 100，y = 0，w = 10，h = 10，r = 0）。
- **FR-009**: `CONFIG_ZMK_KEYBEACON_KEYMAP=n` 时，MUST 完全不编译两个新特征，不占用 ATT handle。
- **FR-010**: 新特征 MUST 不影响 KBP 1.0/1.1/1.2 既有特征的行为，service UUID 不变。

### Key Entities *(include if feature involves data)*

- **KeymapMeta 特征**（UUID `AA440AA5-F5ED-4C48-84A1-8062D20D3D55`）：只读，轻量，含 CRC32 + 元信息；app 每次连接时读取用于缓存校验。
- **KeymapData 特征**（UUID `AA440AA6-F5ED-4C48-84A1-8062D20D3D55`）：只读，分块，含完整物理布局 + keycode 表；仅在 CRC 变化时由 app 读取。
- **key_entry**：每个物理键的坐标/尺寸/旋转，10 字节固定长度。
- **binding_entry**：每个 layer 中每个键的 behavior 类型和参数，5 字节固定长度。
- **behavior_id 枚举**：`KP=0x01, MT=0x02, LT=0x03, MO=0x04, TO=0x05, TOG=0x06, SL=0x07, SK=0x08, TRANS=0x09, NONE=0x0A, KEY_REPEAT=0x0B, GRESC=0x0C, CAPS_WORD=0x0D, KT=0x0E, TD=0x10, MACRO=0x11, MOD_MORPH=0x12, BT=0x20, OUT=0x21, RESET=0x22, BOOTLOADER=0x23, MKP=0x30, RGB=0x40, BL=0x41, EXT_POWER=0x42, SOFT_OFF=0x43, STUDIO_UNLOCK=0x44, UNKNOWN=0xFF`。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `KeymapMeta` READ transaction 在 BLE 连接后 200ms 内完成（含 ATT 握手）。
- **SC-002**: `KeymapData` 完整读取（50 键 × 5 layer = 约 2.5KB）在 1s 内完成。
- **SC-003**: CRC32 计算结果与参考实现（Python `binascii.crc32`）对同一 payload 的计算结果一致。
- **SC-004**: `CONFIG_ZMK_KEYBEACON_KEYMAP=n` 编译后，固件大小增量为 0（不引入任何代码）。
- **SC-005**: 老版本 app（不认识 `AA440AA5`/`AA440AA6`）连接到新固件时，无崩溃，KBP 1.0/1.1/1.2 功能正常。

## Assumptions

- 本 feature 仅覆盖固件侧实现，app 侧由 `keybeacon` 仓库 `006-keymap-viewer` 覆盖，两侧通过 UUID 和 payload 格式对齐。
- ZMK 版本锁定在现有 `west.yml` 指定的 commit，`physical_layout` 节点 API 在该版本已稳定。
- `crc32` 函数来自 Zephyr 内核，不引入额外依赖。
- 分块读取使用标准 BLE ATT `READ_BLOB` 协议（opcode 0x0C），无需自定义分块控制点。
- Windows 客户端不在本 feature 范围内。
