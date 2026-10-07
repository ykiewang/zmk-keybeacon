<!--
Copyright (c) 2026 The TOTEM ZMK Contributors
SPDX-License-Identifier: MIT
-->

# Getting Started: Adding KeyBeacon to a ZMK Keyboard

**English** · [中文](#zh-gs)

This guide walks you from zero to a verified KeyBeacon build for any ZMK keyboard. You will
add the feature in under ten minutes without editing the shared kit code. The reference
implementation is the Totem shield in `config/boards/shields/totem/`; every example below uses
Totem so you can compare against the live code.

## Before you start: does your keyboard qualify?

KeyBeacon reports state over the **host-facing BLE connection**. Two things must be true:

| Check | How to confirm |
|-------|----------------|
| `CONFIG_ZMK_BLE=y` is available for your board | Check your board's `.conf` or `Kconfig.defconfig`; BLE boards (e.g. SEEED XIAO BLE) set this automatically. |
| Your keyboard has a **central (host-link) role** | Unibody keyboards: always yes. Split keyboards: only the half with `CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y` qualifies. |

If your keyboard has no central BLE role, stop here — KeyBeacon cannot be added as specified.

---

## Step 1 — Make the kit available to your shield

Copy or reference `config/keybeacon_kit/` from your shield. There are two ways:

**Option A — reference in-place (recommended if the kit is already in your config tree):**

The kit is already at `config/keybeacon_kit/`. Your shield only needs to reference it by relative
path — no copying needed.

**Option B — copy the directory:**

```bash
cp -r config/keybeacon_kit/ config/boards/shields/<your-keyboard>/keybeacon_kit/
```

All examples below use the in-place reference path (option A), matching Totem.

---

## Step 2 — Wire the kit into your shield's CMakeLists.txt

In `config/boards/shields/<your-keyboard>/CMakeLists.txt`, add **one line** that includes the
kit's build snippet:

```cmake
include(${CMAKE_CURRENT_LIST_DIR}/../../../keybeacon_kit/keybeacon.cmake)
```

The cmake snippet (`keybeacon.cmake`) does nothing unless all three conditions are met at build
time: `CONFIG_ZMK_KEYBEACON`, `CONFIG_ZMK_BLE`, and `CONFIG_ZMK_SPLIT_ROLE_CENTRAL`. This means
including it in the file is always safe — it will silently compile out for non-central and
peripheral targets.

**Totem reference** (`config/boards/shields/totem/CMakeLists.txt`):

```cmake
include(${CMAKE_CURRENT_LIST_DIR}/../../../keybeacon_kit/keybeacon.cmake)
```

---

## Step 3 — Expose the Kconfig symbol in your shield's Kconfig

In `config/boards/shields/<your-keyboard>/Kconfig.defconfig` (or `Kconfig`), add one `rsource`
line so the `ZMK_KEYBEACON` symbol is visible to the build:

```kconfig
rsource "../../../keybeacon_kit/Kconfig.keybeacon"
```

Place it outside any `if SHIELD_…` block so it is visible to all targets that include this
defconfig. The symbol itself depends on `ZMK_BLE`, so it is automatically invisible on boards
without BLE.

**Totem reference** (`config/boards/shields/totem/Kconfig.defconfig`):

```kconfig
if SHIELD_TOTEM_LEFT

config ZMK_KEYBOARD_NAME
    default "TOTEM"

config ZMK_SPLIT_ROLE_CENTRAL
    default y

endif

if SHIELD_TOTEM_LEFT || SHIELD_TOTEM_RIGHT

config ZMK_SPLIT
    default y

endif

rsource "../../../keybeacon_kit/Kconfig.keybeacon"   # ← added at the end
```

---

## Step 4 — Enable the feature in your keyboard's .conf

In the keyboard-level `.conf` that controls the **central** target, add:

```conf
CONFIG_ZMK_KEYBEACON=y
```

For a split keyboard, this goes in the central half's conf only. For Totem that is
`config/totem.conf` (shared) — since `SHIELD_TOTEM_LEFT` is the only target where
`CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y`, the cmake guard ensures `keybeacon.c` links only there.

If you want to be explicit, put it in the central-specific conf:

```conf
# config/totem_left.conf  (central only — the right half and settings_reset are unaffected)
CONFIG_ZMK_KEYBEACON=y
```

---

## Step 5 — Build and flash

Build both halves of your split keyboard (or the single target for a unibody). Replace
`<board>` and `<shield_central>` / `<shield_peripheral>` with your actual names.

```bash
# Split keyboard — build central (left) then peripheral (right)
west build -d build/left  -b <board> -- -DSHIELD=<shield_central>
west build -d build/right -b <board> -- -DSHIELD=<shield_peripheral>

# Totem example (SEEED XIAO BLE):
west build -d build/left  -b seeeduino_xiao_ble -- -DSHIELD=totem_left
west build -d build/right -b seeeduino_xiao_ble -- -DSHIELD=totem_right
```

Flash by dragging the `.uf2` onto the keyboard's mass-storage device:

```bash
# Put the left half into bootloader mode (double-press reset), then:
cp build/left/zephyr/zmk.uf2 /Volumes/<LEFT_DRIVE>/
# Repeat for right half:
cp build/right/zephyr/zmk.uf2 /Volumes/<RIGHT_DRIVE>/
```

The peripheral and `settings_reset` targets build cleanly without KeyBeacon — the cmake guard
(`CONFIG_ZMK_SPLIT_ROLE_CENTRAL`) silently excludes `keybeacon.c` from those targets.

---

## Step 6 — Verify

Connect your keyboard to the Mac, then choose one of:

**Quick probe (no app install needed):**

```bash
# From the firmware repo root
python3 -m venv tools/.venv
tools/.venv/bin/pip install bleak          # pulls in pyobjc on macOS
tools/.venv/bin/python tools/probe.py
```

Expected output (one line per state change):

```
Found keyboard: TOTEM (AA440AA0-...)
layer=0 name="BASE" mods=0x00
layer=1 name="NAVI" mods=0x00
layer=1 name="NAVI" mods=0x02   ← Left Shift held
layer=1 name="NAVI" mods=0x00
```

**Full app verification:**

Download `BleWidget.dmg` from [keybeacon Releases](https://github.com/ykiewang/keybeacon/releases),
open it, and confirm the floating panel shows the active layer name and modifier indicators.

**Conformance tool (full per-item check):**

```bash
# From the keybeacon repo
pip install pyobjc-framework-CoreBluetooth
python3 conformance/conformance_tool.py
# exit 0 = all required items pass
```

---

## Troubleshooting

### Keyboard not discovered by the app or probe

- Confirm the keyboard is connected to the Mac as a Bluetooth HID device (appears in System
  Settings → Bluetooth as "Connected").
- The keyboard stops advertising once connected — the app finds it by enumerating
  already-connected peripherals, not by scanning. A plain BLE scan will not find it.
- Check that `CONFIG_ZMK_KEYBEACON=y` is in the **central** target's conf, not the peripheral's.
- Rebuild and reflash the central half after adding the conf flag.

### Payload reads as 2 bytes, layer name is empty

The snapshot always has at least 2 bytes (`layer_index` + `mods`). If `layer_name` is empty,
your keymap layer names may not be set. In ZMK, layer names are defined in the `.keymap` file:

```dts
/ {
    keymap {
        compatible = "zmk,keymap";

        base_layer {
            label = "BASE";          // ← this becomes layer_name in the payload
            bindings = < ... >;
        };

        nav_layer {
            label = "NAVI";
            bindings = < ... >;
        };
    };
};
```

Without a `label`, `zmk_keymap_layer_name()` returns an empty string and the payload is exactly
2 bytes — this is valid per the protocol and the app shows `L0`, `L1`, etc. as fallback names.

### Constant NOTIFY traffic while keyboard is idle

`keybeacon.c` suppresses notifications when the snapshot is unchanged — an idle keyboard must
produce zero traffic. If you see continuous notifications, the most likely cause is a layer index
that keeps changing (e.g. a momentary layer key held by a macro, or a faulty mod-morph). Use the
probe to observe the raw stream and identify the source of the change.

### Feature compiles into the peripheral or settings_reset image

The cmake guard in `keybeacon.cmake` checks all three conditions:

```cmake
if(CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
```

If `keybeacon.c` appears in a peripheral build, the peripheral target has
`CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y` set — check `Kconfig.defconfig` to confirm the role assignment.

---

## What you did NOT need to edit

- `keybeacon_kit/keybeacon.c` — the shared GATT logic is never changed for porting.
- `keybeacon_kit/keybeacon.cmake` — the cmake snippet is consumed, not modified.
- `keybeacon_kit/Kconfig.keybeacon` — the symbol declaration is sourced, not modified.

That's the kit design: the shared code is fixed; you only wire it in.

---

<a id="zh-gs"></a>

# 入门指南：为 ZMK 键盘添加 KeyBeacon 支持（中文版）

**English** · [中文](#zh-gs)

本指南带你从零开始，为任意 ZMK 键盘完成一次经过验证的 KeyBeacon 构建。你只需接入套件，无需修改
任何共享代码，整个过程不超过十分钟。参考实现是 `config/boards/shields/totem/` 下的 Totem shield；
下方所有示例均使用 Totem，方便与线上代码对照。

## 开始前：你的键盘是否符合条件？

KeyBeacon 通过**面向主机的 BLE 连接**上报状态。需要满足两个条件：

| 检查项 | 如何确认 |
|--------|---------|
| `CONFIG_ZMK_BLE=y` 对你的板子可用 | 查看板子的 `.conf` 或 `Kconfig.defconfig`；BLE 板（如 SEEED XIAO BLE）会自动设置此项。 |
| 键盘具有 **central（主机链路）角色** | 一体式键盘：始终满足。分体键盘：只有设置了 `CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y` 的那一半符合条件。 |

如果你的键盘没有 central BLE 角色，止步于此——无法按规范添加 KeyBeacon。

---

## 第 1 步 — 让 kit 对你的 shield 可用

从你的 shield 复制或引用 `config/keybeacon_kit/`。有两种方式：

**方式 A — 原地引用（推荐，kit 已在你的 config 树中时）：**

kit 已在 `config/keybeacon_kit/`，你的 shield 只需用相对路径引用，无需复制。

**方式 B — 复制目录：**

```bash
cp -r config/keybeacon_kit/ config/boards/shields/<your-keyboard>/keybeacon_kit/
```

下方所有示例使用原地引用路径（方式 A），与 Totem 保持一致。

---

## 第 2 步 — 在 shield 的 CMakeLists.txt 中接入 kit

在 `config/boards/shields/<your-keyboard>/CMakeLists.txt` 中，添加**一行**来包含 kit 的构建片段：

```cmake
include(${CMAKE_CURRENT_LIST_DIR}/../../../keybeacon_kit/keybeacon.cmake)
```

cmake 片段（`keybeacon.cmake`）在构建时只有三个条件同时满足才会生效：`CONFIG_ZMK_KEYBEACON`、
`CONFIG_ZMK_BLE` 和 `CONFIG_ZMK_SPLIT_ROLE_CENTRAL`。因此将这一行写进文件是完全安全的——对于
非 central 和 peripheral 目标，它会静默地编译空。

**Totem 参考**（`config/boards/shields/totem/CMakeLists.txt`）：

```cmake
include(${CMAKE_CURRENT_LIST_DIR}/../../../keybeacon_kit/keybeacon.cmake)
```

---

## 第 3 步 — 在 shield 的 Kconfig 中暴露符号

在 `config/boards/shields/<your-keyboard>/Kconfig.defconfig`（或 `Kconfig`）中，添加一行
`rsource`，使 `ZMK_KEYBEACON` 符号对构建可见：

```kconfig
rsource "../../../keybeacon_kit/Kconfig.keybeacon"
```

将其放在所有 `if SHIELD_…` 块**外部**，使所有包含此 defconfig 的目标都能看到它。该符号本身
`depends on ZMK_BLE`，因此在无 BLE 的板上会自动不可见。

**Totem 参考**（`config/boards/shields/totem/Kconfig.defconfig`）：

```kconfig
if SHIELD_TOTEM_LEFT

config ZMK_KEYBOARD_NAME
    default "TOTEM"

config ZMK_SPLIT_ROLE_CENTRAL
    default y

endif

if SHIELD_TOTEM_LEFT || SHIELD_TOTEM_RIGHT

config ZMK_SPLIT
    default y

endif

rsource "../../../keybeacon_kit/Kconfig.keybeacon"   # ← 在末尾添加
```

---

## 第 4 步 — 在键盘的 .conf 中启用特性

在控制 **central** 目标的键盘级 `.conf` 中，添加：

```conf
CONFIG_ZMK_KEYBEACON=y
```

对于分体键盘，这只加在 central 半的 conf 里。对于 Totem，放在 `config/totem.conf`（共享）
即可——因为只有 `SHIELD_TOTEM_LEFT` 目标设置了 `CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y`，cmake 守卫
会确保 `keybeacon.c` 只链接到那个目标。

如需更明确，也可放在 central 专用 conf 里：

```conf
# config/totem_left.conf（仅 central——右半与 settings_reset 不受影响）
CONFIG_ZMK_KEYBEACON=y
```

---

## 第 5 步 — 构建与烧录

分别构建分体键盘的两半（一体式键盘只构建单个目标）。将 `<board>` 和
`<shield_central>` / `<shield_peripheral>` 替换为你的实际名称。

```bash
# 分体键盘——先构建 central（左），再构建 peripheral（右）
west build -d build/left  -b <board> -- -DSHIELD=<shield_central>
west build -d build/right -b <board> -- -DSHIELD=<shield_peripheral>

# Totem 示例（SEEED XIAO BLE）：
west build -d build/left  -b seeeduino_xiao_ble -- -DSHIELD=totem_left
west build -d build/right -b seeeduino_xiao_ble -- -DSHIELD=totem_right
```

将键盘置于 bootloader 模式（双击 reset），把 `.uf2` 拖拽到键盘的大容量存储设备上以烧录：

```bash
# 左半进入 bootloader 后：
cp build/left/zephyr/zmk.uf2 /Volumes/<LEFT_DRIVE>/
# 右半同理：
cp build/right/zephyr/zmk.uf2 /Volumes/<RIGHT_DRIVE>/
```

peripheral 和 `settings_reset` 目标可正常构建，且不包含 KeyBeacon——cmake 守卫
（`CONFIG_ZMK_SPLIT_ROLE_CENTRAL`）会将 `keybeacon.c` 静默排除在外。

---

## 第 6 步 — 验证

将键盘连接到 Mac，然后选择以下任一方式验证：

**快速探针（无需安装 app）：**

```bash
# 在固件仓根目录下执行
python3 -m venv tools/.venv
tools/.venv/bin/pip install bleak          # macOS 上会一并安装 pyobjc
tools/.venv/bin/python tools/probe.py
```

预期输出（每次状态变化一行）：

```
Found keyboard: TOTEM (AA440AA0-...)
layer=0 name="BASE" mods=0x00
layer=1 name="NAVI" mods=0x00
layer=1 name="NAVI" mods=0x02   ← 按住左 Shift
layer=1 name="NAVI" mods=0x00
```

**完整 app 验证：**

从 [keybeacon Releases](https://github.com/ykiewang/keybeacon/releases) 下载 `BleWidget.dmg`，
打开后确认悬浮窗显示当前层名称与修饰键指示器。

**一致性工具（逐项全面检查）：**

```bash
# 在 keybeacon 仓目录下执行
pip install pyobjc-framework-CoreBluetooth
python3 conformance/conformance_tool.py
# 退出 0 = 所有必需项通过
```

---

## 排错

### app 或探针找不到键盘

- 确认键盘已作为蓝牙 HID 设备连接到 Mac（在「系统设置 → 蓝牙」中显示为"已连接"）。
- 键盘一旦连接就会停止广播——app 通过枚举已连接外设（而非扫描广播包）来发现它。普通 BLE
  扫描不会找到它。
- 确认 `CONFIG_ZMK_KEYBEACON=y` 在 **central** 目标的 conf 中，而非 peripheral 的。
- 添加 conf 标志后，重新构建并烧录 central 半。

### 载荷只有 2 字节，层名称为空

快照始终至少有 2 字节（`layer_index` + `mods`）。如果 `layer_name` 为空，可能是你的 keymap
没有设置层名称。在 ZMK 中，层名称在 `.keymap` 文件里定义：

```dts
/ {
    keymap {
        compatible = "zmk,keymap";

        base_layer {
            label = "BASE";          // ← 这会成为载荷中的 layer_name
            bindings = < ... >;
        };

        nav_layer {
            label = "NAVI";
            bindings = < ... >;
        };
    };
};
```

没有 `label` 时，`zmk_keymap_layer_name()` 返回空字符串，载荷恰好为 2 字节——这在协议上是
合法的，app 会以 `L0`、`L1` 等作为回退显示名。

### 键盘空闲时持续收到 NOTIFY

`keybeacon.c` 会在快照不变时抑制通知——空闲键盘必须产生零流量。如果你看到连续通知，最可能的
原因是层索引持续变化（例如：宏持续按住某个瞬时层按键，或 mod-morph 的缺陷）。用探针观察原始
数据流，定位变化来源。

### 特性编译进了 peripheral 或 settings_reset 镜像

`keybeacon.cmake` 中的 cmake 守卫检查三个条件：

```cmake
if(CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
```

如果 `keybeacon.c` 出现在 peripheral 构建中，说明该 peripheral 目标设置了
`CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y`——检查 `Kconfig.defconfig` 确认角色分配是否正确。

---

## 哪些文件你不需要编辑

- `keybeacon_kit/keybeacon.c` — 共享 GATT 逻辑，移植时永不修改。
- `keybeacon_kit/keybeacon.cmake` — cmake 片段，被消费而非修改。
- `keybeacon_kit/Kconfig.keybeacon` — 符号声明，被引入而非修改。

这就是 kit 的设计理念：共享代码固定不变，你只需接线。
