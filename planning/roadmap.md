# 产品路线图

## 已完成：L4（2026-04-12）

AI 能正确规划 L1-L4 拓扑，build 脚本稳定，/gh-wire 技能已注册。

---

## 已完成：L4.5 — Recipe 模式库（2026-04-13）

**目标：** 把已验证的拓扑模式缓存为可调用的 Recipe，让 AI 从"每次从零规划"变成"识别意图 + 调用 Recipe + 填入参数"。

**通过标准（三条全部达成）：**
1. ✅ 同一意图，10次调用至少8次命中正确 Recipe
2. ✅ Recipe 覆盖常见场景80%（第一批9个全部验证）
3. ✅ 两个 Recipe 可以组合调用并跑通（两对链式组合均通过）

**关键成就：**
- Recipe 系统上线，/gh-wire + /gh-ok 双技能协作稳定
- 建立 Recipe 间几何输出桥接机制（2026-08-13 已迁移为 v2 公共接口与 `composition_rules`）
- 链式验证现由 `compose` + `audit` + 用户视觉确认 + `admit` 门禁管理
- `knowledge/` 模块建立：composition-patterns.md + geometry-type-guide.md 作为增长型知识库
- 已验证桥接模式：GH_Curve list → Loft → GH_Surface / GH_Brep → Deconstruct Brep + List Item → GH_Surface

### Recipe 第一批（✅ 全部完成，2026-04-13）

**建筑体量**
- [x] `mass-rotate` — 旋转塔楼（2026-04-12）
- [x] `mass-extrude` — 矩形挤出体量（2026-04-13）
- [x] `mass-taper` — 渐变收分体量（多截面 Loft）（2026-04-13）
- [x] `floor-stack` — 标准层堆叠（2026-04-13）

**表皮**
- [x] `facade-grid` — 表皮网格分格（2026-04-13）
- [x] `facade-panel-flat` — 平板幕墙（2026-04-13）

**通用几何**
- [x] `array-linear` — 线性阵列（2026-04-13）
- [x] `array-radial` — 环形阵列（2026-04-13）
- [x] `attractor-remap` — 吸引子映射（2026-04-13）

**链式组合测试（✅ 两对验证通过）**
- [x] `mass-extrude` + `facade-grid`：Deconstruct Brep + List Item → 取建筑立面
- [x] `mass-rotate` + `facade-panel-flat`：Loft 旋转椭圆 → 螺旋外皮曲面

---

## 当前阶段：L5 起点 — 第二批 Recipe

**起点条件（已达成）：**
- 第一批 9 个 Recipe 全部验证
- 链式组合机制建立（现为 Recipe v2 公共组合规则）
- knowledge/ 模块可持续增长

### Recipe 第二批

**建筑体量：** `mass-podium-tower`（✅ 2026-04-16） / `mass-setback` / `mass-boolean`（✅ 2026-04-21） / `floor-offset` / `core-place`

**表皮：** `facade-louver`（✅ 2026-04-16） / `facade-parametric-tilt`（✅ 2026-04-21） / `facade-perforate`

**屋顶：** `roof-flat` / `roof-slope` / `roof-shell`

**景观：** `terrain-from-contour`（✅ 2026-04-17） / `terrain-grade`（✅ 2026-04-17） / `terrain-cut-fill`（✅ 2026-04-21） / `path-offset-zone` / `paving-grid` / `paving-radial` / `plant-array-grid` / `plant-array-path` / `plant-cluster` / `water-edge` / `ramp-slope`

**通用几何：** `array-on-surface` / `morph-between` / `boundary-offset`

> 每个第二批 Recipe 验证后判断是否有链式组合机会；有则声明公共规则并完成 audit/admit 流程。

**待验证的链式组合（优先）：**
- `attractor-remap` + `facade-panel-flat`：数值场驱动内缩比例
- `mass-taper` + `facade-grid`：锥形体量 → 立面分格

### Recipe 第三批（用户驱动沉淀）

用户跑通新场景后，/gh-ok 提示是否入库，由用户决定。无预设列表。

---

## Recipe 生长机制

- 用户从每次使用中沉淀 Recipe（/gh-ok 自动入库）
- 链式组合通过公共接口和版本化 `composition_rules` 持续积累
- knowledge/ 模块随验证增长，Claude 每次执行时读取，无需重新推导
- 库越积累越有价值，越难迁移 → 订阅模式护城河

---

## 商业模式方向

- 订阅制 + 年度升级承诺
- 用户从某个 L 等级开始订阅，每年交付一个可验证的能力跃迁
- 目标市场：全球参数化设计圈（不限于中国）
- 商业地产方向（户型生成、面积配比）可能比建筑师工具更早到达可交付状态
- 卖的不是软件功能，是持续进化的路线图
