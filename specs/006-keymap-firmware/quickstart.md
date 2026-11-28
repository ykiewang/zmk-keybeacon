# Quickstart: 006-keymap-firmware

**Date**: 2026-11-26

## 前置条件

- ZMK 构建环境已配置（`west` 可用，ZMK 源码在 `zmk_known_good` 范围内）
- 已有支持 `CONFIG_ZMK_KEYBEACON=y` 的 `zmk-config`（如 totem）
- nRF Connect（手机端）或 conformance CLI 可用于验证 BLE 特征

---

## 场景 1 — KeymapMeta 特征存在且 payload 合法（FR-001、FR-002）

**SC-001**

```
Given  已烧录含 CONFIG_ZMK_KEYBEACON=y、CONFIG_ZMK_KEYBEACON_KEYMAP=y 的固件
When   用 nRF Connect 连接键盘并枚举特征
Then   服务 AA440AA0-… 下存在 AA440AA5-… 特征（KeymapMeta）
       READ 返回：4 字节 CRC32 + 1 字节 layer_count + 2 字节 key_count + layer 名称列表
       总长度 ≤ 256 字节，transaction 在 200ms 内完成
```

验证步骤：
1. `west build -b <board>` 并烧录
2. nRF Connect → Connect → 展开 KeyBeacon service
3. 点击 AA440AA5 READ，确认返回 ≥ 7 字节
4. 手工解析前 7 字节：CRC32[0..3]、layer_count[4]、key_count[5..6]
5. 用 Python 验证 CRC32 正确性（见下）

```python
import binascii, struct

meta_bytes = bytes([...])          # 粘贴 nRF Connect 读到的 hex
crc_reported = struct.unpack_from('<I', meta_bytes, 0)[0]

# 读取 KeymapData 完整字节后验证
data_bytes = bytes([...])
crc_computed = binascii.crc32(data_bytes) & 0xFFFFFFFF
assert crc_reported == crc_computed, f"{crc_reported:#010x} != {crc_computed:#010x}"
```

---

## 场景 2 — KeymapData 完整读取与 binding 解析（FR-003、FR-004、FR-005、FR-006）

**SC-002 / SC-003**

```
Given  上述固件，键盘有 N 个键、L 个 layer
When   app 通过 ATT READ_BLOB 完整读取 AA440AA6
Then   拼合后 payload 长度 = 10×N + 5×L×N 字节
       前 10×N 字节解析出 N 条 key_entry，坐标与 physical_layout 节点一致
       后续字节解析出 L×N 条 binding_entry，binding 与 .keymap 文件一致
```

验证步骤（Python 脚本）：

```python
import struct

KEY_ENTRY_FMT = '<hhBBhhh'   # x y w h r rx ry = 10 bytes
BIND_ENTRY_FMT = '<BHH'      # behavior_id param1 param2 = 5 bytes
KEY_SIZE = struct.calcsize(KEY_ENTRY_FMT)   # 10
BIND_SIZE = struct.calcsize(BIND_ENTRY_FMT) # 5

data = bytes([...])          # KeymapData 完整 payload
key_count = ...              # 从 KeymapMeta 读取
layer_count = ...

keys = [struct.unpack_from(KEY_ENTRY_FMT, data, i * KEY_SIZE)
        for i in range(key_count)]
bindings = []
offset = key_count * KEY_SIZE
for _ in range(layer_count * key_count):
    bindings.append(struct.unpack_from(BIND_ENTRY_FMT, data, offset))
    offset += BIND_SIZE

print(f"Keys: {len(keys)}, Bindings: {len(bindings)}")
print("Sample key[0]:", keys[0])
print("Sample binding[0]:", bindings[0])
```

---

## 场景 3 — keymap 修改后 CRC 变化（FR-007）

**SC-003**

```
Given  初次烧录后记录 KeymapMeta CRC32 值
When   修改 .keymap 文件（至少改一个 binding），重新编译并烧录
Then   KeymapMeta ���回不同的 CRC32
       KeymapData payload 内容与新 .keymap 文件一致
```

---

## 场景 4 — 旋转键坐标正确序列化（FR-005）

**SC-005（固件侧）**

```
Given  physical_layout 中某键 r = 1500（15.00°），rx = 300，ry = 200
When   app 读取 KeymapData，解析对应 key_entry
Then   key_entry.r  == 1500
       key_entry.rx == 300
       key_entry.ry == 200
```

---

## 场景 5 — CONFIG_ZMK_KEYBEACON_KEYMAP=n 时零增量（FR-009）

**SC-004**

```
Given  zmk-config 中设置 CONFIG_ZMK_KEYBEACON_KEYMAP=n
When   编译固件
Then   编译成功，固件大小与 KBP 1.2 基线一致（±链接对齐误差）
       nRF Connect 枚举不到 AA440AA5 / AA440AA6 特征
```

验证步骤：
1. `west build -b <board>` with KEYMAP=n
2. 记录 `.hex` / `.uf2` 大小，对比 KEYMAP=y 版本
3. 烧录后 nRF Connect 确认无 AA5/AA6 特征

---

## 场景 6 — physical_layout 缺失线性回退（FR-008）

```
Given  shield 无 physical_layout Devicetree 节点
When   app 读取 KeymapData
Then   key_entry[i].x = i * 100，y = r = rx = ry = 0，w = h = 10
       固件不崩溃，app 渲染出单行线性键位图
```

---

## 场景 7 — 老 app 向后兼容（FR-010、SC-005）

```
Given  旧版 app（不认识 AA440AA5/AA440AA6）连接到新固件
Then   旧 app 枚举 AA1~AA4 特征，忽略 AA5/AA6
       KBP 1.0/1.1/1.2 功能完全正常，无崩溃
```

---

## FR / SC 映射表

| 场景 | FR | SC |
|------|----|----|
| 1 | FR-001, FR-002 | SC-001 |
| 2 | FR-003, FR-004, FR-005, FR-006 | SC-002, SC-003 |
| 3 | FR-007 | SC-003 |
| 4 | FR-005 | — |
| 5 | FR-009 | SC-004 |
| 6 | FR-008 | — |
| 7 | FR-010 | SC-005 |
