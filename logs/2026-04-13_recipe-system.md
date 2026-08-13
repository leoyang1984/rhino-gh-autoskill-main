# 2026-04-13 — Recipe 系统设计与实施

## 背景决策

用户提出 token 经济性问题，引发了对现有"每次搜索组件库"方式的重新设计。

**核心洞察：** 对已验证的拓扑模式，AI 不应每次重新规划，而应识别意图 → 匹配 Recipe → 注入参数。这是质的跃升，不是量的优化。

---

## 实施内容

### 1. SKILL.md 决策树重写（v1.0 → v2.0）

新决策树：
```
理解意图 → 读 index.json → 命中？
  ├─ 是：读 recipe.json + wiring.json → 注入参数 → 输出 wiring.json
  └─ 否：搜索组件库 → 规划拓扑 → 输出 wiring.json
```

**参数注入由 Claude 完成**（而非新脚本）：用户体验不变，多消耗少量 token，换取无缝体验。

### 2. recipes/ 目录结构

```
recipes/
├── index.json              # AI 每次只读这一个（摘要）
└── mass-rotate/
    ├── recipe.json         # 参数接口定义
    └── wiring.json         # 已验证拓扑模板
```

`result.gh` 不入版本库（在 .gitignore 中），本地按需生成。

### 3. 第一个 Recipe：mass-rotate

来源：test_05 螺旋塔楼（2026-04-12 验证通过）

参数接口：
- `floors` = 20
- `floor_height` = 5000mm
- `rot_step_deg` = 5°
- `radius_long` = 10500mm（半轴）
- `radius_short` = 3500mm（半轴）

### 4. 文档整合

| supplement 章节 | 整合位置 |
|----------------|---------|
| 不生成 GHX 的原因 | CLAUDE.md 技术决策区 |
| L4.5 定义与通过标准 | tests/README.md |
| Recipe 列表（第一/二/三批） | docs/roadmap.md |
| 商业模式方向 | docs/roadmap.md |

---

## Token 经济性对比

| 场景 | 旧方式 | 新方式（Recipe 命中）|
|------|--------|---------------------|
| 读取 | component_library.json 多条 | index.json（小文件）|
| AI 输出 | 完整 wiring.json（规划）| recipe_id + 参数值 |
| 拓扑规划 | 每次重新推理 | 零（模板复用）|
| 参数注入 | 无 | 少量 token |
| 总体 | 高 | 极低 |

---

## 下一步

按 docs/roadmap.md 中 Recipe 第一批列表逐步沉淀，优先级：
1. `mass-extrude`（最常见）
2. `array-linear` / `array-radial`（通用）
3. `facade-grid`（表皮起点）
