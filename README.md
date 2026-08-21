# GH AI Wiring — Grasshopper AI 自动布线

让 AI（Claude Code / Codex / 任意 Agent）把一句自然语言设计描述，转换成可直接在
Grasshopper 中打开的 `.gh` 电池连接图，或 Rhino MCP 的 `g1_apply_graph` 载荷。

核心思路：**扫描本机 Grasshopper 组件库 → 沉淀"已验证拓扑"（Recipe）→ AI 匹配意图 →
注入参数 → 编译出连线图**。AI 只描述"做什么"，`.gh` 的序列化交给 GH 运行时完成。

```
自然语言描述
   │
   ▼
AI Agent ──search──▶ recipes/index.json ──匹配──▶ recipe.json (参数契约 v2)
   │                                                   │
   │  compile_recipe.py compile <id> --set 参数=值      │ wiring.json (已验证拓扑)
   │                                                   ▼
   ▼                                              g1_apply_graph 载荷 / wiring.json
Rhino MCP 直接放置组件求解     或      scripts/build_gh_file.py 在 GH 内生成 .gh 文件
```

---

## 这是什么

- **18 个已验证 Recipe**（massing / facade / array / attractor / terrain / kangaroo 物理模拟），
  每个包含 `recipe.json`（公共参数接口 + 组合规则）和 `wiring.json`（节点拓扑模板）；
- **编译器 CLI**（纯 Python 标准库，无需 GH 运行时）：搜索、编译、校验、组合、健康检查、
  审计、准入；
- **GH 内脚本**：扫描本机组件库生成 JSON、把 wiring JSON 写成 `.gh` 文件；
- **面向 AI 的技能定义**：`skills/grasshopper-recipe-modeling/SKILL.md`，指导 Agent 如何复用
  Recipe 库、通过 Rhino MCP 构建并审计 GH 画布。

---

## 前置要求

| 组件 | 版本 | 用途 | 是否必需 |
|---|---|---|---|
| Rhino | 8（含 Grasshopper） | GH 内运行扫描/构建脚本、打开 `.gh` | 生成文件前必需 |
| Python | 3.9+（仅标准库） | 编译器 CLI、测试 | CLI 功能必需 |
| Rhino MCP（rhino-mcp / grasshopper-mcp） | 最新 | 让 Agent 直接生成画布并求解 | 可选（MCP 路径） |
| AI 客户端 | Claude Code / Codex 等 | 读取 Recipe 库、规划拓扑 | 用 AI 工作流时必需 |

> 编译器脚本只依赖标准库（`json` / `pathlib` / `argparse` …），不调用 Rhino API，
> 在普通 Python 环境可直接运行。

---

## 安装

```bash
git clone https://github.com/leoyang1984/rhino-gh-autoskill-main.git
cd rhino-gh-autoskill-main

# 验证编译器可用（无需 Rhino）
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py list
```

首次使用建议在装有 Rhino 8 的机器上采集本机组件快照（见下文"更新组件库"），
没有快照时编译器仍可工作，只是类型检查覆盖率会降级为 `UNKNOWN`。

---

## 快速上手

### 路径 A：纯 CLI —— 编译 Recipe 为 wiring.json / MCP 载荷

```bash
# 列出全部 Recipe
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py list

# 按意图搜索
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py search "螺旋塔楼"

# 编译单个 Recipe，注入参数（默认输出 g1_apply_graph 载荷）
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py compile mass-rotate \
  --set floors=12 floor_height=4000

# 输出 legacy wiring.json（供 build_gh_file.py 使用）
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py compile mass-rotate \
  --emit wiring --set floors=12
```

### 路径 B：生成 `.gh` 文件（需要 GH 运行时）

1. 把 `scripts/build_gh_file.py` 的内容粘贴进 GH 的 **Python Script 组件**运行；
2. 组件会向上查找含 `recipes/index.json` 的目录作为项目根（也可传入 `project_root`
   文本输入，或设置环境变量 `GH_AI_WIRING_ROOT`）；
3. 默认读取 `output/wiring.json`，写出 `output/result.gh`；
4. 在 GH 中打开 `output/result.gh` 验证。

### 路径 C：Rhino MCP —— Agent 直接生成画布并求解

1. Agent 读取 `skills/grasshopper-recipe-modeling/SKILL.md`；
2. 用 `compile_recipe.py compile <id>` 得到 `g1_apply_graph` 参数对象；
3. 通过 MCP 批量放置组件 / Slider / 连线并求解；
4. 取回画布数据做审计：`compile_recipe.py audit --evidence <normalized.json>`。

---

## CLI 参考（compile_recipe.py）

```
usage: compile_recipe.py {list,search,compile,validate,validate-wiring,migrate,
                          compose,health,audit,admit} ...
```

| 子命令 | 作用 | 示例 |
|---|---|---|
| `list` | 列出全部 Recipe 摘要 | `compile_recipe.py list` |
| `search` | 按意图词搜索 Recipe | `compile_recipe.py search "幕墙 百叶"` |
| `compile` | 编译为 MCP 载荷或 wiring | `compile_recipe.py compile facade-louver --emit wiring --set count=12` |
| `validate` | 校验单个或全部 Recipe | `compile_recipe.py validate` |
| `validate-wiring` | 校验独立/AI 规划的 wiring JSON | `compile_recipe.py validate-wiring tests/test_01_slider_circle_extrude.json` |
| `migrate` | 预览 schema v2 迁移（只读） | `compile_recipe.py migrate mass-rotate --dry-run` |
| `compose` | 按公共组合规则串联两个 Recipe | `compile_recipe.py compose mass-rotate facade-grid` |
| `health` | 离线校验组件快照与基线一致性 | `compile_recipe.py health --snapshot data/component_library.json` |
| `audit` | 评估 MCP 求解后的归一化证据 | `compile_recipe.py audit --evidence evidence.json` |
| `admit` | 检查 Recipe 是否具备静态/动态/视觉证据（只读准入） | `compile_recipe.py admit <id> --audit report.json` |

> 全部命令可用 `--project-root <dir>` 指定项目根（默认自动向上查找
> 含 `recipes/index.json` 的目录）。

---

## 更新组件库（换机器 / 安装新插件后）

1. 在 GH 的 Python Script 组件中运行 `scripts/scan_gh_components.py`
   → 生成 `data/component_library.json`（本机快照，已被 `.gitignore` 忽略，不会入库）；
2. 在普通 Python 中运行 `scripts/build_component_index.py` → 生成压缩索引；
3. 需要建立共享基线时，把人工审查过的快照复制到
   `data/reference/component_snapshot.json`（见 `data/reference/README.md`）。

> ⚠️ 生成或修改任何 GH Python 脚本前，先读 `docs/rhino8_python_rules.md`
> （Rhino 8 的 API 与旧版本差异，如 `Hidden` 属性不存在、无
> `FindObjectByComponentGuid` 等）。

---

## 测试

```bash
# 编译器回归测试（含 Recipe 载荷基线冻结）
python3 tests/test_compile_recipe.py

# 类型检查 / 组合 / 审计 / 健康检查等单元测试
python3 tests/test_graph_ir.py
python3 tests/test_composition.py
python3 tests/test_type_check.py
python3 tests/test_health_check.py
python3 tests/test_dynamic_audit.py
```

`tests/` 同时包含 L1–L4.5 的输入/预期配对（`.md` 指令 + `.json` 结果），
详见 `tests/README.md`。

---

## 目录结构

```
rhino-gh-autoskill-main/
├── CLAUDE.md                        # AI Agent 的入口指令（新 session 自动加载）
├── README.md                        # 本文件
├── skills/grasshopper-recipe-modeling/
│   ├── SKILL.md                     # 面向 Codex/Claude 的技能定义（必读）
│   ├── references/                  # 项目契约、MCP 执行规范、案例
│   └── scripts/                     # 编译器 + 验证器（纯标准库）
├── recipes/
│   ├── index.json                   # Recipe 索引（搜索入口）
│   └── <id>/                        # recipe.json（v2 参数契约）+ wiring.json（拓扑）
├── schemas/                         # recipe-v2 / audit-evidence-v1 / component-snapshot-v2
├── scripts/                         # GH 内运行：扫描组件库 / 生成 .gh 文件
├── data/
│   ├── hot_components.json          # 高频组件快查表（AI 优先读）
│   ├── reference/                   # 共享兼容性基线说明
│   └── component_library.json       # 本机快照（gitignore，需在 GH 内生成）
├── knowledge/                       # 组合模式、类型兼容指南、Kangaroo 物理模式
├── docs/rhino8_python_rules.md      # GH Python 编码规则 R1-R6（写脚本前必读）
├── tests/                           # L1-L4.5 用例 + 回归测试
├── planning/                        # 路线图、成长计划、进度快照
├── logs/                            # 会话日志（审计/健康 JSON 不入库）
├── dev/                             # 开发管理文档（架构方案、技术债）
└── output/                          # 生成产物：wiring.json / result.gh（result.gh 不入库）
```

---

## 给 AI Agent 的使用指南

如果你是一个被要求"阅读这个仓库"的 AI：

1. **先读 `CLAUDE.md`** —— 它定义了完整工作流、技术约束和已确定决策；
2. **搜索意图时**先读 `recipes/index.json`，命中后用
   `compile_recipe.py search/compile`，不要手动发明组件 GUID 或端口名；
3. **组合多个 Recipe**时读两侧 `recipe.json` 的公共接口和 `composition_rules`，
   用 `compile_recipe.py compose` 而不是手动改内部节点 id；
4. **编写/修改任何 GH Python 脚本前**必读 `docs/rhino8_python_rules.md`；
5. **不要修改 `recipes/`、`knowledge/`、`planning/`、`logs/`** 仅仅因为某个图求解成功；
   只有用户视觉确认并要求保留时才走 `audit` + `admit` 准入流程；
6. `scan_gh_components.py` 和 `build_gh_file.py` 必须运行在 GH 内部的 Python 3 Script
   组件中；`compile_recipe.py` 在普通 Python 中运行。

---

## 隐私与安全

- 本项目无任何第三方依赖、无网络请求、无遥测；
- 组件 GUID 来自 Grasshopper 组件库（公开元数据）；
- 本机组件快照（`data/component_library.json`）按设计不入库，避免携带个人安装信息；
- 若你 fork 后想公开发布，请检查提交作者邮箱与文档中的本地路径引用。

## License

[MIT](LICENSE) © 2026 [leoyang1984](https://github.com/leoyang1984)
