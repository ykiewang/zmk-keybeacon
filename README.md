<!--
Copyright (c) 2026 The TOTEM ZMK Contributors
SPDX-License-Identifier: MIT
-->

# KeyBeacon Kit — Porting Guide

KeyBeacon exposes a ZMK keyboard's **active layer + modifier state** over a custom
BLE GATT service so a host app (e.g. the macOS KeyBeacon widget) can display it
live. This directory is a **self-contained, keyboard-independent kit**: the shared
logic in `keybeacon.c` is never edited to port the feature — you only wire it into a
shield and flip one Kconfig symbol.

## What's in the kit

| File | Role | Edit to port? |
|------|------|---------------|
| `keybeacon.c` | Shared GATT logic (service, read, change-detect, notify) | **No** |
| `keybeacon.cmake` | Guarded `zephyr_library` snippet (symbol + BLE + central) | No |
| `Kconfig.keybeacon` | Declares `CONFIG_ZMK_KEYBEACON` (bool, `default n`) | No |
| `README.md` | This guide | No |

## Prerequisites

- **Central BLE role**: the feature compiles **only** for the keyboard's central
  role. A split keyboard's central half qualifies; a peripheral-only or non-BLE
  keyboard does **not**. If your keyboard has no central BLE role, it is
  **unsupported** — stop here.
- `CONFIG_ZMK_BLE` must be available (it is a `depends on` of the symbol).

## Porting steps (≤ 10)

1. Make the kit available to your target shield — either copy this `keybeacon_kit/`
   directory into your `config/` tree, or reference it in place by relative path.
2. In the shield's `CMakeLists.txt`, add one line:
   `include(<path-to-kit>/keybeacon.cmake)`
3. In the shield's `Kconfig.defconfig` (or `Kconfig`), source the symbol:
   `rsource "<path-to-kit>/Kconfig.keybeacon"`
4. In the keyboard-level `.conf`, enable it: `CONFIG_ZMK_KEYBEACON=y`
5. Build the **central** target for your keyboard and flash it.

That's it — you do **not** edit `keybeacon.c`.

## Verify

- The central image links `keybeacon.c`; the peripheral and `settings_reset`
  images do **not** (the `.cmake` guard enforces central-only).
- `git diff <path-to-kit>/keybeacon.c` is empty after porting.
- Run the host probe (`tools/probe.py`) or the app: the keyboard is discovered by
  the custom service UUID `AA440AA0-…`, and the status stream decodes.

## Why shield-scoped (not a west module)

`keybeacon.c` calls ZMK `app`-private APIs (`zmk/keymap.h`, `zmk/hid.h`, the event
manager). Those headers are reachable only from the shield build scope via
`zephyr_library_include_directories(${CMAKE_SOURCE_DIR}/include)` (see
`keybeacon.cmake`). A standalone west module cannot reach them, so the kit is
consumed from within a shield rather than distributed as an independent module.

## Reference consumer

The Totem shield (`config/boards/shields/totem/`) consumes this kit as the
reference: its `CMakeLists.txt` includes `keybeacon.cmake`, its `Kconfig.defconfig`
sources `Kconfig.keybeacon`, and `config/totem.conf` sets `CONFIG_ZMK_KEYBEACON=y`.

---

<a id="zh-kit"></a>

# KeyBeacon Kit — 移植指南（中文版）

**English** · [中文](#zh-kit)

KeyBeacon 通过自定义 BLE GATT 服务暴露 ZMK 键盘的**当前层 + 修饰键状态**，使桌面应用（如 macOS KeyBeacon widget）能够实时显示。本目录是一个**自包含、与键盘无关的套件**：移植时**不需要**修改 `keybeacon.c` 中的共享逻辑，你只需将其接入 shield 并打开一个 Kconfig 符号。

## 套件内容

| 文件 | 作用 | 移植时需编辑？ |
|------|------|--------------|
| `keybeacon.c` | 共享 GATT 逻辑（服务、读取、变化检测、通知） | **不** |
| `keybeacon.cmake` | 带守卫的 `zephyr_library` 片段（符号 + BLE + central） | 不 |
| `Kconfig.keybeacon` | 声明 `CONFIG_ZMK_KEYBEACON`（bool，`default n`） | 不 |
| `README.md` | 本指南 | 不 |

## 前提条件

- **Central BLE 角色**：本功能**仅**为键盘的 central 角色编译。分体键盘的 central 半边符合条件；纯 peripheral 或无 BLE 的键盘**不**符合。如果你的键盘没有 central BLE 角色，它**不受支持**——止步于此。
- `CONFIG_ZMK_BLE` 必须可用（它是该符号的 `depends on` 条件）。

## 移植步骤（≤ 10 步）

1. 将套件提供给目标 shield——可以将本 `keybeacon_kit/` 目录复制到你的 `config/` 树中，或通过相对路径在原地引用。
2. 在 shield 的 `CMakeLists.txt` 中添加一行：
   `include(<path-to-kit>/keybeacon.cmake)`
3. 在 shield 的 `Kconfig.defconfig`（或 `Kconfig`）中引入符号：
   `rsource "<path-to-kit>/Kconfig.keybeacon"`
4. 在键盘级别的 `.conf` 中启用：`CONFIG_ZMK_KEYBEACON=y`
5. 为你的键盘构建 **central** 目标并刷写。

就这些——你**不需要**编辑 `keybeacon.c`。

## 验证

- central 镜像链接了 `keybeacon.c`；peripheral 和 `settings_reset` 镜像**没有**（`.cmake` 守卫强制 central-only）。
- 移植后 `git diff <path-to-kit>/keybeacon.c` 为空。
- 运行主机探针（`tools/probe.py`）或应用：键盘通过自定义服务 UUID `AA440AA0-…` 被发现，状态流可正常解码。

## 为什么是 shield 范围而非 west module

`keybeacon.c` 调用了 ZMK `app` 私有 API（`zmk/keymap.h`、`zmk/hid.h`、事件管理器）。这些头文件只能通过 `zephyr_library_include_directories(${CMAKE_SOURCE_DIR}/include)` 从 shield 构建范围访问（见 `keybeacon.cmake`）。独立的 west module 无法访问它们，因此本套件从 shield 内部消费，而非作为独立模块分发。

## 参考消费者

Totem shield（`config/boards/shields/totem/`）以参考实现的方式消费本套件：其 `CMakeLists.txt` 包含 `keybeacon.cmake`，其 `Kconfig.defconfig` 引入 `Kconfig.keybeacon`，`config/totem.conf` 设置 `CONFIG_ZMK_KEYBEACON=y`。
