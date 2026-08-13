# Kangaroo 2 物理模拟模式

> 记录 Kangaroo 2 物理模拟（布料/粒子/力）的已验证拓扑与行为规则。
> 2026-08-13 首次验证：四角吊点布料 + 重力（见 `logs/2026-08-13-kangaroo-cloth-mcp.md`）。
>
> **对应 Recipe：** `recipes/kangaroo-cloth/`（布料重力模拟，schema v2，2026-08-13 入库）。
> 本文件是该 Recipe 的求解协议说明书——Recipe 只声明参数与输出，**求解时序由本文档兜底**。
> 未来若 recipe schema 增加 `solve_mode` 字段（见 `dev/optimization-plan-2026-08-13.md` 决策记录），
> 本协议将并入 recipe.json 声明。

---

## 与几何 Recipe 的根本区别

| | 确定性几何 Recipe（mass-*/facade-*） | 物理模拟 Recipe（Kangaroo） |
|---|---|---|
| 求解 | 设参数 → 一次求值 → 出结果 | 迭代求解：Reset → 持续迭代 → 收敛 |
| 验证 | 结构审计（数量/类型/报错） | **结构审计 + 数值审计**（坐标量级/收敛/锚点） |
| 结果 | 确定性 | 依赖求解过程与参数，可能爆炸/发散 |
| Slider | 改值即重算 | 改值后需 **Reset=True → 求解 → Reset=False → 迭代** 才生效 |

**推论：** 物理模拟 Recipe 入库时，`recipe.json` 目前无法表达"求解行为"
（无 `solve_mode` 字段），求解协议必须由本文件 + 人工/审计流程兜底。
schema 扩展提案见 `dev/optimization-plan-2026-08-13.md` 决策记录。

---

## 布料拓扑骨架（已验证，22 组件 + 8 Slider + 43 连线）

```
Rectangle(Width×Depth) → Boundary Surfaces → Mesh Surface(U×V)
     ↓
Deconstruct Mesh → 顶点 (U+1)×(V+1) 个
     ├─→ Load [重力]（Point=全部顶点, Force vector=Unit Z×Gravity）
     ├─→ 4 角点（List Item 索引公式，见下）→ Anchor [吊点]
     └─→ Mesh Edges（全部边）→ Length(Line) [弹簧]（目标长=网格边长, Strength 可调）
     ↓
Kangaroo Solver（On=True 持续迭代, Reset 按钮重置）
     ↓
Solver.V（新粒子位置）+ Deconstruct Mesh.F → Construct Mesh → 布料网格
```

## 必守规则（每条都来自真实踩坑）

1. **弹簧约束必不可少**：只有重力+锚点、无弹簧 → 粒子数值爆炸（飞到 e+12）。
   布料必须 `Mesh Edges → Length(Line)` 提供边约束。
2. **锚点必须是网格顶点本身**：从 `Deconstruct Mesh.V` 用 `List Item` 取角点，
   不能手造"看起来在角上"的点——Kangaroo 按位置匹配粒子，位置不一致锚不住。
3. **Reset/On 协议**：
   - `On=True` 持续求解（每次 GH solve 迭代一步，直到收敛）；
   - `Reset=True` 重置粒子到初始位置（改参数后必须先 Reset 再迭代）；
   - 流程：**Reset=True → solve → Reset=False → 多次 solve 直到 I 不再增长**。
4. **弹簧目标长度 = 网格边长**：`Length(Line).Length` 必须等于 `Width/U`（或 `Depth/V`），
   否则布会整体收缩/拉伸变形。
5. **数值审计必做**：只看 sample 前几个点会误判（前几个常是锚点附近，看似不动）。
   必须统计全部分布：`Zmin/Zmax/Zmean`、中心点、锚点是否钉住。
6. **角点索引公式**（网格 (U+1)×(V+1)，行优先）：`0, U, (U+1)·V, (U+1)·(V+1)-1`。

## 参数平衡经验（2026-08-13 实测，布宽 50、网格 20×20）

| 参数 | 值 | 效果 |
|---|---|---|
| Gravity = -1, SpringStrength = 0.3 | 下垂 600+ 单位 | 瀑布状，过度 |
| Gravity = -0.1, SpringStrength = 5~6 | 中心下垂约 31 单位 | 自然的布料深垂（≈0.6×布宽） |
| Gravity = -0.05~-0.1, Strength 高 | 下垂 < 1 单位 | 绷紧如钢板，几乎不动 |

量级经验：**下垂量 ≈ 布宽 × (0.6~0.7) × (Gravity / SpringStrength) 的经验区间**，
视觉目标"明显下垂但不夸张"取 Gravity≈-0.1、Strength≈5。

## 关键组件 GUID（Rhino 8 实测）

| 组件 | GUID |
|---|---|
| Kangaroo Solver (K2) | `313490f5-8e38-4dde-9e9a-05e4d739b35d` |
| Anchor | `3c30b1a1-4473-4ad4-a700-ea9770726c03` |
| Load（重力/单点力） | `2019c995-53af-4eb2-976d-95b1fdc823fa` |
| Length(Line)（弹簧） | `091bae84-8fa9-4b35-8aad-b25b859055f6` |
| Mesh Edges | `2b9bf01d-5fe5-464c-b0b3-b469eb5f2efb` |
| Mesh Surface (S/U/V→Mesh) | `58cf422f-19f7-42f7-9619-fc198c51c657` |
| Deconstruct Mesh | `ba2d8f57-0738-42b4-b5a5-fe4d853517eb` |
| Construct Mesh | `e2c0f9db-a862-4bd9-810c-ef2610e7a56f` |
| Boolean Toggle | `2e78987b-9dfb-42a2-8b76-3923ac8bd91a` |

> 组件库随机器/插件版本漂移，GUID 仅作参考；换环境先用 `g1_search_components` 核实。
