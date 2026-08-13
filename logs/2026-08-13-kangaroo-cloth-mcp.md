# 2026-08-13 — Kangaroo 布料 + 重力（MCP 全链路首次验证）

## 任务

做一个"给曲面添加重力、几个点拎起一块布"的 GH 模组（Kangaroo 2 布料模拟），
通过 Rhino MCP 全链路执行：router 桥接 → 建图 → 求解 → 数值审计 → 保存 .gh。

## 执行链路

1. **环境接入**：stdio JSON-RPC 桥接 `rhino-mcp-router`（0.2.1-wip）。
   关键：router 启动时自动收养用户已开的 Rhino 为 slot（`aardvark`/pid 3893/port 10500）；
   直接 `spawn_slot` 会因端口被占用而 startup_timeout。
2. **建图**：`g1_apply_graph` 一次放置 22 组件 + 8 Slider + 43 连线（零 PlaceErrors）。
3. **求解**：`g1_solve_graph` + 审计 `g1_get_canvas_graph(include_data=true)`。
4. **保存**：GH 内 `GH_DocumentIO.SaveQuiet` → `output/kangaroo_cloth.gh`；
   截图需先把 Construct Mesh 输出 bake 进 Rhino 文档（GH 预览不在 Rhino 文档里）。

## 三次调试记录（踩坑 → 修复）

| # | 现象 | 根因 | 修复 |
|---|------|------|------|
| 1 | 粒子飞到 e+12（数值爆炸） | 只有重力+锚点，**无弹簧约束** | 加 Mesh Edges → Length(Line) 边弹簧 |
| 2 | 求解后粒子仍不收敛/状态错 | 缺 Reset 机制，Solver 从上次发散状态继续 | 加 Reset toggle：True 重置 → False 迭代 |
| 3 | 中心下垂 613 单位（瀑布状） | 参数失衡：Gravity=-1、Strength=0.3 | 调 Gravity=-0.1、Strength=5~6 → 下垂约 31 单位 |

另有一个误判教训：**审计只看 sample 前 3 个点会误判**（都是锚点附近、看似不动），
必须统计全部分布（Zmin/Zmax/Zmean）——用 run_python 读 Solver.V 的 `VolatileData.AllData`。

## 最终结果

- 布料 50×50、网格 20×20（441 顶点、400 面），4 角吊点钉住
- 中心下垂 Z≈-31（≈0.6×布宽），Solver 迭代收敛（I 稳定），无报错
- 产出：`output/kangaroo_cloth.gh` + `output/kangaroo_cloth_preview.jpg`

## 沉淀去向

- 知识：`knowledge/kangaroo-physics-patterns.md`（拓扑 + 规则 + 参数经验）
- 编码规则：`docs/rhino8_python_rules.md` R7（运行时改 slider 值）
- MCP 工具坑：`skills/grasshopper-recipe-modeling/references/mcp-execution.md` 新增章节
- Recipe：**待用户视觉确认 `output/kangaroo_cloth.gh` 后入库**（`recipes/kangaroo-cloth/`）
- schema 提案：`dev/optimization-plan-2026-08-13.md` 决策记录（solve_mode 字段）
