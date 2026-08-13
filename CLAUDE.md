# GH AI Wiring — Claude Code 交接文档

## 这个项目是什么

把本机 Grasshopper 的组件库扫描成 JSON，然后让 Claude Code 读取用户的自然语言描述，规划出 GH 电池连接图（节点 + 连线），最终写入 `.gh` 文件让用户在 Grasshopper 里直接打开。

**核心能力（已验证 ✅）：**
- 单 Recipe：识别意图 → 匹配已验证 Recipe → 注入参数 → 生成 wiring
- 链式组合：识别多 Recipe 意图 → 查公共 `composition_rules` → 编译合并图

> ⚠️ 生成或修改任何 GH Python 脚本前，必须先读取 `docs/rhino8_python_rules.md`。

---

## 当前状态

<!-- GENERATED:STATUS:START -->
| 项目指标 | 当前状态 |
|---|---|
| Recipe | 18 个；verified 18/18；schema v2 18/18 |
| 静态验证 | 18/18 通过 |
| 公共接口 | 6 个 Recipe 有外部输入；共 27 个公共输出 |
| 公共组合规则 | 8 条 |
| 高频组件快照 | 31 个组件 |
| 本机完整组件快照 | ⏳ 待采集 |
| 已审查参考快照 | ⏳ 待采集 |
| 编译与验证 | Graph IR、分级类型检查、compose、health、audit、admit |

此区块由 `scripts/sync_project_status.py` 生成；不要手工编辑。
<!-- GENERATED:STATUS:END -->

---

## 工作流程

### MCP：直接生成 Grasshopper Canvas

1. Codex 调用 `grasshopper-recipe-modeling` Skill 匹配或组合 Recipe
2. `compile_recipe.py` 将既有 `wiring.json` 转换为 `g1_apply_graph` 载荷
3. Rhino MCP 批量放置组件、Slider 和连线并求解
4. Codex 读取 Canvas 数据检查报错、条目数、数值范围和数据树；用户负责视觉确认

Skill 入口：`skills/grasshopper-recipe-modeling/SKILL.md`。

### 单 Recipe：生成一个 GH 文件

1. **用户描述需求** → Claude Code 调用 `/gh-wire` skill
   - 匹配 `recipes/index.json` → 注入参数（单 Recipe 路径）
   - 未命中 → 搜索 `data/hot_components.json` + `data/component_library.json` → 现场规划
2. **Claude 生成** `output/wiring.json`
3. **用户在 GH 里**运行 `scripts/build_gh_file.py`
4. **打开** `output/result.gh` 验证
5. 验证通过 → `/gh-ok` → 沉淀为 Recipe

### 链式组合：两个 Recipe 串联

1. **用户描述多 Recipe 意图**（如"螺旋塔楼 + 幕墙"）→ 读取两侧 Recipe v2 公共接口。
2. 用 `compile_recipe.py compose <source> <target>` 应用已验证的公共组合规则。
3. 在 GH/Rhino 中求解，并把 MCP 结果归一化后运行 `audit`。
4. 用户视觉确认后运行只读 `admit` 门禁；只有用户要求保留时才更新知识。

### 更新组件库（换机器或安装新插件后）

1. 在 GH 里运行 `scripts/scan_gh_components.py` → 更新 `data/component_library.json`
2. 在普通 Python 里运行 `scripts/build_component_index.py` → 更新索引

---

## 技术约束

- `scan_gh_components.py` 和 `build_gh_file.py` **必须在 GH 内部的 Python 3 Script 组件里运行**
- `build_component_index.py` 在普通 Python 3 环境运行（不需要 GH 运行时）
- 扫描脚本用的是 `Grasshopper.Instances.ComponentServer.ObjectProxies`
- 写入 GH 文件用的是 `Grasshopper.Kernel.GH_Document` + `GH_DocumentIO`
- Slider 预设值必须用 `System.Decimal()`，且在 `doc.AddObject()` 之后设置

## 已确定的技术决策（不需要重新讨论）

**不直接生成 GHX（XML）：**
GHX 是 .NET 对象序列化结果，没有统一 schema，每种组件的 XML 结构不同。
现有路径（JSON → Python → GH 运行时 → GHX）让 GH 负责序列化，AI 只描述"做什么"。

---

## 文件结构

```
rhino-gh-auto/
├── CLAUDE.md                          ← 你正在读的文件（新 session 自动加载）
├── scripts/
│   ├── scan_gh_components.py          ← 在 GH 内运行：扫描组件库
│   ├── build_gh_file.py               ← 在 GH 内运行：wiring.json → .gh
│   └── build_component_index.py       ← 普通 Python：生成压缩索引
├── docs/                              ← 静态技术规则（Python 脚本时必读）
│   └── rhino8_python_rules.md
├── knowledge/                         ← 生长型知识库（链式组合时按需读）
│   ├── composition-patterns.md        ← 已验证的链式桥接模式
│   └── geometry-type-guide.md         ← GH 类型兼容性 + 转换组件
├── planning/                          ← 人类战略文档（路线图、会话记录）
│   ├── checkpoint.md                  ← 进度快照（仅标记状态区块自动维护）
│   ├── L4.5-growth-plan.md            ← 当前成长计划（"开始L4.5"时读）
│   └── roadmap.md / supplement-*.md
├── recipes/                           ← 已验证 Recipe 库
│   ├── index.json                     ← /gh-wire 每次读此文件（极小）
│   └── <id>/
│       ├── recipe.json                ← schema v2 公共接口 + composition_rules
│       └── wiring.json                ← 已验证拓扑模板
├── data/
│   ├── hot_components.json            ← 高频组件快查表（/gh-wire 优先读）
│   ├── component_library.json         ← 完整组件库（fallback）
│   └── component_index.json           ← 按 category 分组压缩版
├── tests/                             ← L1-L4 拓扑测试
├── logs/                              ← 会话日志
└── output/
    ├── wiring.json                    ← 最新生成的连线图
    └── result.gh                      ← 最新生成的 GH 文件
```

---

## 当用户说"开始"时

如果 `data/component_library.json` **不存在**：
→ 提示用户在 Rhino 里运行 `scripts/scan_gh_components.py`

如果 `data/component_library.json` **存在**：
→ 报告 Recipe 库状态（recipes/index.json 条数），直接等待用户描述需求

## 当用户说"开始"或"继续"时（任何情况）

1. 读 `planning/checkpoint.md` — 快速了解当前阶段、上次操作、下一步
2. 向用户报告：当前在哪、上次做了什么、推荐下一步是什么

## 当用户说"开始 L4.5 成长计划"时

1. 读 `planning/checkpoint.md`（快速定位当前位置）
2. 读 `planning/L4.5-growth-plan.md`（详细协议 + Recipe 队列）
3. 读 `recipes/index.json`（当前已验证状态）
4. 对比队列，找出下一个 pending Recipe，向用户报告并询问是否开始
