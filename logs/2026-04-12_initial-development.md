# 2026-04-12 — 初始开发：从零到 L4 拓扑验证

## 目标

验证核心假设：AI 能否根据 GH 组件库 + 自然语言描述，正确规划出可执行的节点连接图，并写入 `.gh` 文件。

---

## 完成的工作

### 1. 项目脚手架搭建
- 创建目录结构：`scripts/`、`skills/`、`data/`、`output/`、`tests/`、`docs/`、`logs/`
- 写入 `scripts/scan_gh_components.py`：在 GH 内运行，扫描组件库
- 写入 `scripts/build_gh_file.py`：接收 wiring.json，在 GH 内生成 .gh 文件
- 写入 `scripts/build_component_index.py`：普通 Python，生成压缩索引
- 写入 `skills/gh-wiring.md`：AI 生成 wiring.json 的完整操作规范

### 2. 组件库扫描（用户在 Rhino 8 中完成）
- 扫描结果：**1204 个组件**，14 个分类
- 主要分类：Params(159)、Maths(123)、Kangaroo2(120)、Curve(117)、Surface(99)

### 3. build_gh_file.py 调试（踩坑记录 → 形成 R1-R6 规则）

| 错误 | 原因 | 修复 |
|------|------|------|
| 扫描返回空数组 | `proxy.Hidden` 在 Rhino 8 不存在，被 except 吞掉 | 改用 `getattr(proxy, 'Hidden', False)` |
| `FindObjectByComponentGuid` 不存在 | Rhino 8 API 变更 | 手动建 proxy_index 字典 |
| Slider 无 `Params` 属性 | Slider 是 `IGH_Param` 不是 `IGH_Component` | 用 `isinstance(obj, ghk.IGH_Param)` 分支判断 |
| Slider 数值报 TypeError | `.Minimum/.Maximum/.Value` 需要 `System.Decimal` | 包裹 `System.Decimal()` |
| Slider 预设值不生效 | `AddObject` 会重置 slider 状态 | 先 `AddObject`，再设值 |

所有规则归档至 `docs/rhino8_python_rules.md`（R1-R6）。

### 4. 连线拓扑测试

| 测试 | 场景 | 组件数 | 结果 |
|------|------|--------|------|
| L1 test_01 | Slider→Circle→Extrude 圆柱 | 5 | ✅ |
| L2 test_02 | 共享 Slider 同时控制半径和高度 | 4 | ✅ |
| L3 test_03 | 3 Slider 控制球心坐标 + 1 Slider 控制半径 | 7 | ✅ |
| L4 test_04 | 两圆 Loft 锥形曲面（多分支 + 多汇聚） | 8 | ✅ |

### 5. 已验证的组件（GUID 可直接复用）

| 组件 | GUID |
|------|------|
| Number Slider | `57da07bd-ecab-415d-9d86-af36d7073abc` |
| Circle | `807b86e3-be8d-4970-92b5-f8cdcb45b06b` |
| Sphere | `dabc854d-f50e-408a-b001-d043c7de151d` |
| Extrude | `962034e9-cc27-4394-afc4-5c16e3447cf9` |
| Move | `e9eb1dcf-92f6-4d4d-84ae-96222d60f56b` |
| Loft | `a7a41d0a-2188-4f7a-82cc-1a2c4e4ec850` |
| Unit Z | `9103c240-a6a9-4223-9b42-dbd19bf38e2b` |
| Addition | `a0d62394-a118-422d-abb3-6af115c75b25` |
| Construct Point | `3581f42a-9592-4549-bd6b-1c0fc39d067b` |
| XY Plane | `17b7152b-d30d-4d50-b9ef-c9fe25576fc2` |

---

## 结论

核心假设验证通过。系统能处理：
- 线性链、一对多、多对一、多分支+多汇聚 四种拓扑
- Slider 预设值（nickname、min/max/value）正确写入
- list 类型端口（如 Loft.Curves）多来源连接正常

---

## 下一步方向（待定）

- 真实建筑/设计场景测试（用户驱动）
- 探索更复杂组件：DataTree、Dispatch、Cull、Merge 等集合操作
- 考虑是否需要把 `/gh-wire` 注册为真正的 Claude Code 技能
