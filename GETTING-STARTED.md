<!--
Copyright (c) 2026 The TOTEM ZMK Contributors
SPDX-License-Identifier: MIT
-->

# Getting Started: Adding KeyBeacon to a ZMK Keyboard

**English** · [中文](#zh-gs)

This guide takes you from zero to a verified KeyBeacon build for any ZMK keyboard. KeyBeacon
ships as a **Zephyr module** (`zmk-keybeacon`): you consume it by adding one entry to your
zmk-config's `west.yml` and flipping one Kconfig symbol — **no files are copied and no shield
wiring is edited**. The module's `zephyr/module.yml` auto-registers its cmake and Kconfig.

## Before you start: does your keyboard qualify?

KeyBeacon reports state over the **host-facing BLE connection**. Two things must be true:

| Check | How to confirm |
|-------|----------------|
| `CONFIG_ZMK_BLE=y` is available for your board | Check your board's `.conf` or `Kconfig.defconfig`; BLE boards (e.g. SEEED XIAO BLE) set this automatically. |
| Your keyboard has a **central (host-link) role** | Unibody keyboards: always yes. Split keyboards: only the half with `CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y` qualifies. |

If your keyboard has no central BLE role, stop here — KeyBeacon cannot be added as specified.

---

## Step 1 — Add the `zmk-keybeacon` module to your `west.yml`

The module's `zephyr/module.yml` declares its cmake and Kconfig entry points, so adding the
project to `west.yml` is **all** the integration your shield needs. You do **not** add any
`include(...)` or `rsource ...` lines.

### Scenario A — you don't have a `config/west.yml` yet

Many zmk-config repos build via the default GitHub Actions workflow with no local manifest.
Create `config/west.yml`:

```yaml
manifest:
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
    - name: ykiewang
      url-base: https://github.com/ykiewang
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
    - name: zmk-keybeacon
      remote: ykiewang
      revision: v1.0.0
  self:
    path: config
```

The `import: app/west.yml` line inherits all of ZMK's own dependencies (Zephyr, modules), so
you never list them by hand.

### Scenario B — you already have a `config/west.yml`

Add the `ykiewang` remote (if it isn't already present) and the `zmk-keybeacon` project entry;
leave everything else untouched:

```yaml
  remotes:
    # ... your existing remotes ...
    - name: ykiewang
      url-base: https://github.com/ykiewang
  projects:
    # ... your existing projects ...
    - name: zmk-keybeacon
      remote: ykiewang
      revision: v1.0.0
```

### Pin a tag, never track a branch

`revision` **MUST** be a released semver tag (e.g. `v1.0.0`), never `main`. Pinning a tag keeps
your firmware reproducible — a module update can never silently change your build until you bump
the tag yourself.

---

## Step 2 — Enable the feature in your keyboard's `.conf`

In the `.conf` that controls the **central** target, add:

```conf
CONFIG_ZMK_KEYBEACON=y
```

For a split keyboard this goes in the central half's conf only. The module's cmake guard
(`CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL`) ensures the code
links only for the central role; peripheral and `settings_reset` targets compile it out silently.

---

## Step 3 — Build and flash

Fetch the module first, then build both halves (or the single target for a unibody). Replace
`<board>` and `<shield_central>` / `<shield_peripheral>` with your actual names.

```bash
west update                                  # fetches zmk-keybeacon at the pinned tag

# Split keyboard — build central (left) then peripheral (right)
west build -d build/left  -b <board> -- -DSHIELD=<shield_central>
west build -d build/right -b <board> -- -DSHIELD=<shield_peripheral>

# Totem example (SEEED XIAO BLE):
west build -d build/left  -b seeeduino_xiao_ble -- -DSHIELD=totem_left
west build -d build/right -b seeeduino_xiao_ble -- -DSHIELD=totem_right
```

Flash by dragging the `.uf2` onto the keyboard's mass-storage device (double-press reset first):

```bash
cp build/left/zephyr/zmk.uf2  /Volumes/<LEFT_DRIVE>/
cp build/right/zephyr/zmk.uf2 /Volumes/<RIGHT_DRIVE>/
```

The peripheral and `settings_reset` targets build cleanly without KeyBeacon — the cmake guard
excludes `keybeacon.c` from those targets.

---

## Step 4 — Verify

Connect your keyboard to the Mac, then choose one of:

**Quick probe (no app install needed):**

```bash
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

**Full app verification:** download `BleWidget.dmg` from
[keybeacon Releases](https://github.com/ykiewang/keybeacon/releases) and confirm the floating
panel shows the active layer name and modifier indicators.

---

## Upgrading the module

To move to a newer KeyBeacon release, change **only** the `revision` in `west.yml`:

```yaml
    - name: zmk-keybeacon
      remote: ykiewang
      revision: v1.1.0   # ← the only change
```

then run `west update && west build`. No file in your `config/`, shield `CMakeLists.txt`, or
`Kconfig.defconfig` changes — upgrades are a one-line edit.

---

## Troubleshooting

### `west update` doesn't fetch the module

Confirm the `zmk-keybeacon` project entry and the `ykiewang` remote are both present in
`west.yml`, and that `revision` names a tag that exists. Re-run `west update` after any edit.

### Keyboard not discovered by the app or probe

- Confirm the keyboard is connected to the Mac as a Bluetooth HID device (System Settings →
  Bluetooth shows "Connected").
- The keyboard stops advertising once connected — the app finds it by enumerating
  already-connected peripherals, not by scanning. A plain BLE scan will not find it.
- Check that `CONFIG_ZMK_KEYBEACON=y` is in the **central** target's conf, not the peripheral's.
- Rebuild and reflash the central half after adding the conf flag.

### Payload reads as 2 bytes, layer name is empty

The snapshot always has at least 2 bytes (`layer_index` + `mods`). If `layer_name` is empty,
your keymap layers may lack a `label`. In ZMK, layer names come from the `.keymap` file:

```dts
/ {
    keymap {
        compatible = "zmk,keymap";
        base_layer {
            label = "BASE";          // ← becomes layer_name in the payload
            bindings = < ... >;
        };
    };
};
```

Without a `label`, `zmk_keymap_layer_name()` returns an empty string and the payload is exactly
2 bytes — valid per the protocol; the app shows `L0`, `L1`, etc. as fallback names.

### Constant NOTIFY traffic while idle

`keybeacon.c` suppresses notifications when the snapshot is unchanged — an idle keyboard must
produce zero traffic. Continuous notifications usually mean a layer index that keeps changing
(e.g. a momentary layer held by a macro, or a faulty mod-morph). Use the probe to find the source.

### Feature compiles into the peripheral or `settings_reset` image

The module's cmake guard checks all three conditions:

```cmake
if(CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
```

If `keybeacon.c` appears in a peripheral build, that target has `CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y`
set — check `Kconfig.defconfig` to confirm the role assignment.

---

## What you did NOT need to edit

- `keybeacon.c` — the shared GATT logic is never changed for porting.
- Your shield's `CMakeLists.txt` — **no** `include(...)` line; the module auto-injects cmake.
- Your shield's `Kconfig.defconfig` — **no** `rsource ...` line; the module auto-injects Kconfig.
- No copied files at all — `west` fetches the module at the pinned tag.

That's the module design: add one `west.yml` entry + one `.conf` symbol.

---

<a id="zh-gs"></a>

# 入门指南：为 ZMK 键盘添加 KeyBeacon 支持（中文版）

**English** · [中文](#zh-gs)

本指南带你从零开始，为任意 ZMK 键盘完成一次经过验证的 KeyBeacon 构建。KeyBeacon 以
**Zephyr 模块**（`zmk-keybeacon`）形式分发：你只需在 zmk-config 的 `west.yml` 中添加一个条目，
再打开一个 Kconfig 符号——**无需复制任何文件，也无需改动 shield 接线**。模块的
`zephyr/module.yml` 会自动注册其 cmake 和 Kconfig。

## 开始前：你的键盘是否符合条件？

KeyBeacon 通过**面向主机的 BLE 连接**上报状态。需要满足两个条件：

| 检查项 | 如何确认 |
|--------|---------|
| `CONFIG_ZMK_BLE=y` 对你的板子可用 | 查看板子的 `.conf` 或 `Kconfig.defconfig`；BLE 板（如 SEEED XIAO BLE）会自动设置此项。 |
| 键盘具有 **central（主机链路）角色** | 一体式键盘：始终满足。分体键盘：只有设置了 `CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y` 的那一半符合条件。 |

如果你的键盘没有 central BLE 角色，止步于此——无法按规范添加 KeyBeacon。

---

## 第 1 步 — 把 `zmk-keybeacon` 模块加入你的 `west.yml`

模块的 `zephyr/module.yml` 声明了 cmake 与 Kconfig 入口，因此把该 project 加入 `west.yml`
就是你的 shield 所需的**全部**接入工作。你**不需要**添加任何 `include(...)` 或 `rsource ...` 行。

### 场景 A — 你还没有 `config/west.yml`

很多 zmk-config 仓库使用默认 GitHub Actions 工作流构建，没有本地 manifest。新建 `config/west.yml`：

```yaml
manifest:
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
    - name: ykiewang
      url-base: https://github.com/ykiewang
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
    - name: zmk-keybeacon
      remote: ykiewang
      revision: v1.0.0
  self:
    path: config
```

`import: app/west.yml` 会继承 ZMK 自身的所有依赖（Zephyr、modules），你无需手动罗列。

### 场景 B — 你已有 `config/west.yml`

添加 `ykiewang` remote（若尚未存在）和 `zmk-keybeacon` project 条目，其余保持不动：

```yaml
  remotes:
    # ... 你现有的 remotes ...
    - name: ykiewang
      url-base: https://github.com/ykiewang
  projects:
    # ... 你现有的 projects ...
    - name: zmk-keybeacon
      remote: ykiewang
      revision: v1.0.0
```

### 固定 tag，切勿跟踪分支

`revision` **必须**是已发布的 semver tag（如 `v1.0.0`），绝不用 `main`。固定 tag 保证固件可复现——
在你亲手升级 tag 之前，模块更新绝不会悄悄改变你的构建。

---

## 第 2 步 — 在键盘的 `.conf` 中启用特性

在控制 **central** 目标的 `.conf` 中添加：

```conf
CONFIG_ZMK_KEYBEACON=y
```

分体键盘只加在 central 半的 conf 里。模块的 cmake 守卫
（`CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL`）确保代码仅为
central 角色链接；peripheral 与 `settings_reset` 目标会静默编译空。

---

## 第 3 步 — 构建与烧录

先拉取模块，再构建两半（一体式键盘只构建单个目标）。将 `<board>` 和
`<shield_central>` / `<shield_peripheral>` 替换为你的实际名称。

```bash
west update                                  # 按固定 tag 拉取 zmk-keybeacon

# 分体键盘——先构建 central（左），再构建 peripheral（右）
west build -d build/left  -b <board> -- -DSHIELD=<shield_central>
west build -d build/right -b <board> -- -DSHIELD=<shield_peripheral>

# Totem 示例（SEEED XIAO BLE）：
west build -d build/left  -b seeeduino_xiao_ble -- -DSHIELD=totem_left
west build -d build/right -b seeeduino_xiao_ble -- -DSHIELD=totem_right
```

将键盘置于 bootloader 模式（双击 reset），把 `.uf2` 拖拽到大容量存储设备上烧录：

```bash
cp build/left/zephyr/zmk.uf2  /Volumes/<LEFT_DRIVE>/
cp build/right/zephyr/zmk.uf2 /Volumes/<RIGHT_DRIVE>/
```

peripheral 和 `settings_reset` 目标可正常构建且不含 KeyBeacon——cmake 守卫会将 `keybeacon.c`
排除在外。

---

## 第 4 步 — 验证

将键盘连接到 Mac，然后选择以下任一方式：

**快速探针（无需安装 app）：**

```bash
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

**完整 app 验证：** 从 [keybeacon Releases](https://github.com/ykiewang/keybeacon/releases)
下载 `BleWidget.dmg`，打开后确认悬浮窗显示当前层名称与修饰键指示器。

---

## 升级模块

要升级到新的 KeyBeacon 版本，只需改 `west.yml` 中的 `revision`：

```yaml
    - name: zmk-keybeacon
      remote: ykiewang
      revision: v1.1.0   # ← 唯一改动
```

然后 `west update && west build`。你的 `config/`、shield `CMakeLists.txt`、`Kconfig.defconfig`
中没有任何文件变化——升级就是一行改动。

---

## 排错

### `west update` 没有拉取到模块

确认 `west.yml` 中同时存在 `zmk-keybeacon` project 条目与 `ykiewang` remote，且 `revision`
指向一个存在的 tag。任何改动后重跑 `west update`。

### app 或探针找不到键盘

- 确认键盘已作为蓝牙 HID 设备连接到 Mac（「系统设置 → 蓝牙」显示为"已连接"）。
- 键盘一旦连接就会停止广播——app 通过枚举已连接外设（而非扫描广播包）来发现它。普通 BLE
  扫描不会找到它。
- 确认 `CONFIG_ZMK_KEYBEACON=y` 在 **central** 目标的 conf 中，而非 peripheral 的。
- 添加 conf 标志后，重新构建并烧录 central 半。

### 载荷只有 2 字节，层名称为空

快照始终至少有 2 字节（`layer_index` + `mods`）。若 `layer_name` 为空，可能是你的 keymap 层
没有设置 `label`。在 ZMK 中，层名称在 `.keymap` 文件里定义：

```dts
/ {
    keymap {
        compatible = "zmk,keymap";
        base_layer {
            label = "BASE";          // ← 这会成为载荷中的 layer_name
            bindings = < ... >;
        };
    };
};
```

没有 `label` 时，`zmk_keymap_layer_name()` 返回空字符串，载荷恰好 2 字节——这在协议上合法，
app 会以 `L0`、`L1` 等作为回退显示名。

### 键盘空闲时持续收到 NOTIFY

`keybeacon.c` 会在快照不变时抑制通知——空闲键盘必须产生零流量。持续通知通常意味着层索引在
持续变化（例如宏持续按住某个瞬时层按键，或 mod-morph 缺陷）。用探针观察原始数据流定位来源。

### 特性编译进了 peripheral 或 settings_reset 镜像

模块的 cmake 守卫检查三个条件：

```cmake
if(CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
```

如果 `keybeacon.c` 出现在 peripheral 构建中，说明该目标设置了 `CONFIG_ZMK_SPLIT_ROLE_CENTRAL=y`
——检查 `Kconfig.defconfig` 确认角色分配。

---

## 哪些你不需要编辑

- `keybeacon.c` — 共享 GATT 逻辑，移植时永不修改。
- 你的 shield `CMakeLists.txt` — **没有** `include(...)` 行；模块自动注入 cmake。
- 你的 shield `Kconfig.defconfig` — **没有** `rsource ...` 行；模块自动注入 Kconfig。
- 完全没有复制文件——`west` 会按固定 tag 拉取模块。

这就是模块的设计：一条 `west.yml` 条目 + 一个 `.conf` 符号。
