# 开发日志：Token 优化问题（2026-04-16）

## 背景

随着 Recipe 库扩展到 11 个，每次 `/gh-wire` 生成新 Recipe 的 token 消耗显著上升，
导致 session 用量快速耗尽，操作明显变慢。

---

## 根本原因

每次生成 wiring（新 Recipe 路径）需要读取：

| 文件 | 行数 | 频率 |
|------|------|------|
| gh-wire skill prompt | ~190 行 | 每次调用注入 |
| `data/hot_components.json` | ~325 行 | 每次新 Recipe |
| `data/component_library.json` | 极大 | 缺组件时 grep |
| 参考 wiring.json（查模式） | ~150 行/个 | 遇到陌生拓扑 |

合计每次消耗 600–1000+ 行上下文，session 很快达到上限。

---

## 待执行的优化

### 优化 1：组件表嵌入 CLAUDE.md（高优先级）

**问题：** `hot_components.json` 每次都要读；缺组件时还要 grep 大文件。

**方案：**
- 将约 40 个高频组件整理为紧凑 Markdown 表格，直接写入 `CLAUDE.md` 末尾
- 格式：`| 名称 | GUID | 输入端口 | 输出端口 |`（每行 1 组件，比 JSON 节省 ~70%）
- CLAUDE.md 自动加载，组件信息零读取成本
- `data/hot_components.json` 降级为备份，不再作为运行时查询源
- `SKILL.md` 中的 "优先读 hot_components.json" 指令改为 "直接查 CLAUDE.md 组件表"

**需要补充的组件（当前 hot_components.json 缺失）：**
- `Subtraction`（GUID: `9c007a04-d0d9-48e4-9da3-9ba142bc4d46`，输入 A/B，输出 Result）
- `Negative`（取负数）
- `Integer`（整数 slider）
- `Panel`（常量文本/数值）
- `Flatten Tree`
- `Graft Tree`

---

### 优化 2：压缩 gh-wire SKILL.md（高优先级）

**问题：** SKILL.md 约 190 行，大量是解释性文字，每次调用都注入 context。

**方案：**
- 保留骨架决策树（~30 行）
- 删除每个 Step 的解释段落
- 把 wiring.json 格式示例、类型兼容规则等移到 `docs/gh-wire-rules.md`（按需读）
- 目标：SKILL.md 压缩到 ~60 行

**建议压缩后结构：**
```
Step 0: Python 脚本才读 rhino8_python_rules.md
Step 1: 理解意图
Step 2: 读 recipes/index.json → 匹配
  命中单个 → Step 3A: 读 recipe.json + wiring.json → 注入参数 → 写 output
  命中多个 → Step 3C: 读两个 wiring.json → 合并 + _chain_meta → 写 output
  未命中  → Step 3B: 查 CLAUDE.md 组件表 → 规划 → 写 output
Step 4: 写 output/wiring.json
Step 5: 汇报路径 + 摘要
[约束] GUID 必须来自组件表，port 区分大小写
```

---

### 优化 3：建立 topology-patterns.json（中期）

**问题：** 生成新 Recipe 时需要读参考 wiring.json 理解组合方式。

**方案：** 新建 `knowledge/topology-patterns.json`，存储可复用子图（含完整 GUID 和端口）：

```json
[
  {
    "id": "series-height-stack",
    "description": "Series × Step → Unit Z → Move，用于垂直堆叠",
    "nodes": [...],
    "connections": [...],
    "output_node": "nMove", "output_port": "Geometry"
  },
  {
    "id": "rect-extrude-brep",
    "description": "Rectangle → Boundary Surfaces → Extrude，基础体量",
    "nodes": [...],
    "connections": [...]
  },
  {
    "id": "tier-size-series",
    "description": "Series + Subtraction → 每级收进尺寸列表",
    "nodes": [...],
    "connections": [...]
  }
]
```

可在每次 `/gh-ok` 后顺手提取，逐步积累，不需要一次完成。

---

## 预期效果

| 场景 | 当前读取量 | 优化后读取量 |
|------|-----------|------------|
| Recipe 命中 | ~515 行 | ~150 行（只读 wiring.json）|
| 新 Recipe 生成 | 600-1000+ 行 | ~250 行（CLAUDE.md 内联 + patterns）|

---

## 备注

- 优化 1 + 2 可独立执行，互不依赖
- 优化 3 依赖优化 1（组件表完整后，patterns 才有意义）
- 执行优化 1 时注意：CLAUDE.md 行数不要超过 ~250 行，否则自动加载反而变慢

---

## 优化 4（推荐，更根本）：组件查询脚本

**问题：** 优化 1–3 都在"读文件"框架内打转。CLAUDE.md 嵌入组件表治标不治本——内容越来越多，迟早也会撑大。

**更正确的方向：把知识库从"被动读取"变成"主动检索"。**

```
现在：理解意图 → 读整个文件 → 从里面找需要的
脚本方案：理解意图 → 告诉脚本要哪些组件 → 脚本返回精确结果
```

**方案：** 新增 `scripts/query_components.py`

```bash
# 调用方式（在 SKILL.md Step 3B 中用 Bash 执行）
python scripts/query_components.py "Rectangle" "Extrude" "Series" "Subtraction"

# 输出：只返回命中的组件，~20行
[
  {"name": "Rectangle", "guid": "d93100b6-...", "inputs": ["Plane","X Size","Y Size","Radius"], "outputs": ["Rectangle","Length"]},
  {"name": "Subtraction", "guid": "9c007a04-...", "inputs": ["A","B"], "outputs": ["Result"]},
  ...
]
```

SKILL.md Step 3B 改为：先分析需要哪些组件，一次 Bash 调用拿到所有结果，不再读任何 JSON 文件。

**与其他方案对比：**

| | 现在 | 嵌入CLAUDE.md | 查询脚本 |
|--|------|--------------|---------|
| 每次读取量 | 325行+ | 0（但CLAUDE.md变大） | ~20行（精确返回） |
| 可扩展性 | 差 | 差（会撑死） | 好（无上限） |
| 覆盖新组件 | 需手动维护 | 需手动维护 | 自动（查原始库） |
| 实现难度 | — | 低 | 低（~30行Python） |

**实施顺序建议：** 直接做优化 4，跳过优化 1。优化 2（压缩 SKILL.md）仍然值得做，与优化 4 互补。
