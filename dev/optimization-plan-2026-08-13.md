# GH AI Wiring 项目优化方案

- **日期：** 2026-08-13
- **状态：** 代码侧 8/8 阶段完成；真实 Rhino 环境快照与动态审计证据待现场运行
- **性质：** 开发管理文档（工程改进方案，非产品路线图；产品路线见 `planning/roadmap.md`）
- **依据：** 2026-08-13 全库静态分析（17 个 recipe 逐文件核对 + `compile_recipe.py validate` 实跑全绿）

---

## 实施结果（2026-08-13）

本方案已按实施前复核意见调整顺序并完成代码侧落地：

- 先冻结 17 个 Recipe 的完整 MCP payload golden baseline，再迁移 schema；
- 17 个 Recipe 全部迁移到 schema v2，并声明公共输入、输出和 8 条公共组合规则；
- Recipe 与临时 wiring 共用 Graph IR、结构验证器和 MCP/legacy emitter；
- 类型检查采用 `EXACT / KNOWN_CAST / WARN / UNKNOWN / INCOMPATIBLE`，默认仅阻断已确认不兼容；
- `knowledge/type-compat.json` 是唯一类型事实源，Markdown 兼容表由脚本生成；
- GH 内采集完整组件快照，普通 Python 的 `health` 只做离线环境验证；
- 动态 MCP 结果归一化为版本化证据，`audit` 与只读 `admit` 分离结构、视觉和入库决策；
- `recipes/index.json` 与受控状态区块由同步脚本生成，人工文档区不被整份覆盖；
- legacy GH 脚本已移除工作站绝对路径。

最终静态验收：56 项 unittest 全部通过；17/17 Recipe 验证通过；8/8 公共
组合规则成功编译；46 个 JSON 与 23 个 Python 文件均可解析；原始 golden
baseline SHA-256 保持为 `0f0bc7deb7a09de4476146b19037a4db988ecabf39171dbd65eb68a4e8092176`。

当前没有把缺失的本机 `component_library.json` 伪装成完整参考快照，也没有伪造
Rhino/GH 动态运行证据。下次真实 Rhino 会话应先采集快照，再为重点 Recipe/组合生成
audit evidence；用户视觉确认仍是准入必需条件。

---

## 当前进度总表

| 阶段 | 工作项 | 状态 | 验收证据 |
|---|---|---|---|
| 0 | 冻结现有行为与 golden baseline | ✅ 完成 | 17 个 Recipe 的完整 MCP payload 已冻结，最终哈希未变化 |
| 1 | Recipe schema v2 与迁移规则 | ✅ 完成 | 17/17 Recipe 为 v2，旧 v1 文档仍可预览迁移 |
| 2 | 统一 Graph IR、结构验证与 emitter | ✅ 完成 | Recipe 与临时 wiring 共用验证器；MCP/legacy 输出均有测试 |
| 3 | 分级类型检查与单一事实源 | ✅ 完成 | 215 条现有连线均有诊断，0 条确认的 `INCOMPATIBLE` |
| 4 | 17 个 Recipe 公共接口迁移 | ✅ 完成 | 17/17 有公共输出，6 个有外部输入，共 26 个公共输出 |
| 5 | 公共组合规则与组合器 | ✅ 完成 | 8/8 组合规则成功编译，不再引用跨 Recipe 内部节点 id |
| 6 | 环境采集与离线健康检查 | ✅ 代码完成 | snapshot schema、`health` CLI、基线/报告目录和测试已完成 |
| 7 | 动态审计与 Recipe 准入 | ✅ 代码完成 | audit evidence schema、`audit`、`admit` 及测试已完成 |
| 8 | 索引与受控文档同步 | ✅ 完成 | index 由 Recipe 生成；文档只更新标记区块；`--check` 通过 |

### 仍需真实 Rhino 会话完成

这些不是代码欠项，而是不能在离线 Python 环境中伪造的现场证据：

1. 在 Grasshopper 中运行 `scripts/scan_gh_components.py`，生成本机完整
   `data/component_library.json`；
2. 运行 `compile_recipe.py health --snapshot data/component_library.json`；
3. 对重点单 Recipe 和 8 条组合执行 MCP apply、solve、canvas data 采集；
4. 生成 `logs/audits/` 下的标准化证据与 audit 报告；
5. 用户完成视觉确认后，将 `visual_review.status` 记为 `approved`，再运行 `admit`。

### 主要落地文件

- Schema：`schemas/recipe-v2.schema.json`、`schemas/component-snapshot-v2.schema.json`、
  `schemas/audit-evidence-v1.schema.json`
- 编译与验证：`skills/grasshopper-recipe-modeling/scripts/compile_recipe.py`、
  `graph_ir.py`、`recipe_schema.py`、`type_check.py`、`composition.py`、
  `health_check.py`、`audit.py`
- 生成器：`scripts/generate_type_guide.py`、`scripts/sync_project_status.py`
- 类型事实源：`knowledge/type-compat.json`
- 回归测试：`tests/test_compile_recipe.py`、`test_graph_ir.py`、
  `test_type_check.py`、`test_recipe_interfaces.py`、`test_composition.py`、
  `test_health_check.py`、`test_dynamic_audit.py`、`test_status_sync.py`

### 进入正确 Git 仓库后的提交前检查

```bash
python3 -m unittest discover -s tests -q
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py validate
python3 scripts/sync_project_status.py --check
git status --short
git diff --check
```

预期结果：56 项测试通过，17/17 Recipe 验证通过，同步检查退出码为 0。

> Git 说明：本次优化所在目录本身没有独立 `.git`，并被外层仓库的
> `/Code/*` 规则忽略。因此本文记录的是已经落地到该目录的工程成果；进入正确的
> 项目 Git checkout 后，需要确认这些文件都位于该 checkout 中，再自行提交和 push。

---

## 0. 现状关键事实（方案的事实基础）

> 本节保留为实施前历史基线，不再代表当前仓库状态。

1. **17 个 recipe 全部 `verified: true`，但 0 个声明"公共输出接口"** —— `chain_bridges`
   直接引用内部节点 id（如 `n14`），一旦拓扑被编辑，桥接静默失效（当前一致只是侥幸）。
2. **端口类型数据是齐的**（hot_components 31/31 带类型；完整库更全）—— 但
   `compile_recipe.py` 只做结构校验，**不做连线类型检查**，GH 最常见的"橙色警告/类型不匹配"
   目前唯一防线是人工目视。
3. **状态文档多头维护已开始漂移**：CLAUDE.md / planning/checkpoint.md / recipes/index.json
   三处计数口径不一；`data/component_library.json`（1204 组件）与 `component_index.json`
   均 gitignored 且不在本 checkout，AI 检索侧只有 31 个高频组件的 `hot_components.json` 兜底。
4. **legacy 脚本硬编码绝对路径**（`/Users/yanglin/...`），与 MCP 路径（自动探测项目根）
   行为不一致；双执行路径（build_gh_file.py 文件流 vs compile_recipe.py MCP 流）共享
   同一批 recipe 数据，但校验能力不同步。

---

## 1. 阶段一：正确性与可移植性（P0 —— 先堵住最大失效模式）

### 1.1 给编译器加静态类型检查（收益最大的一项）

**问题：** `compile_recipe.py validate` 只查"节点存在、参数合法、连线端点存在"，不查端口类型。

**方案：**
- 把 `knowledge/geometry-type-guide.md` 的兼容矩阵（直接连接表 + 需转换表）固化成机器可读的
  `knowledge/type-compat.json`，作为单一事实源（文档保留为人类可读版本，两者同源）。
- `validate` 扩展：遍历每条 connection，查源组件输出端口类型 → 目标输入端口类型，对照兼容表
  判"可直连 / 需转换 / 不兼容"，不兼容即 FAIL。
- 数据源分级：连上 `component_library.json`（完整端口类型）做全量检查；只有 hot_components
  时做覆盖检查，未覆盖的组件标记 SKIP 而非 PASS（避免假阳性）。

**收益：** 把"AI 规划错误"从"用户打开 GH 才发现"提前到"编译期就报错"。

### 1.2 Recipe ↔ 组件库健康检查（GUID 漂移检测）

**问题：** recipe 里的 GUID 是某台机器/某个插件版本下记录的，换机器或插件升级后静默失效
（proxy 找不到就跳过，无告警聚合）。

**方案：** `validate` 增加 `--health` 模式：
- 扫描本机组件库，对每个 recipe 的每个 GUID 做解析测试，输出"recipe 健康报告"
  （`planning/recipe-health.json`）：`可解析 / 缺失 / 端口名不匹配`。
- 报告附带机器指纹（GH 版本、插件列表）。换环境跑一次，得到"哪些 recipe 需要重新验证"清单。

**收益：** 让 `verified: true` 带上环境边界——环境变了自动触发复验，而不是盲目相信旧标记。

### 1.3 消除硬编码路径，统一编译入口

**方案：**
- legacy 脚本（`build_gh_file.py` / `scan_gh_components.py`）改为与 compile_recipe.py 相同的
  "项目根自动探测"逻辑，路径不写死。
- 明确单一入口约定：**一切生成都从 compile_recipe.py 走**。它已能输出 MCP 载荷
  （g1_apply_graph），再加 `--emit wiring.json`（legacy 格式）即可让两条路径共用同一个
  编译器和同一份校验；`build_gh_file.py` 退化为纯序列化器（wiring → .gh）。

### 1.4 补一份可入库的组件索引参考快照

**方案：**
- 入库 `data/component_index.reference.json`（标注"Rhino 8 + 记录时插件集"），
  `build_component_index.py` 输出时附带"本机快照 vs 参考快照"差异摘要。
- 收益：无 GH 环境也能做检索与类型检查开发；有环境时差异即"新装了什么/升级了什么"。

---

## 2. 阶段二：回归与可信度（P1 —— 让验证可重复）

### 2.1 把文档式测试变成可执行回归

**方案：**
- **静态层：** golden test 对每个 `tests/test_XX.json` 跑 compile_recipe.py，断言载荷结构
  （节点数、连线数、slider 数、参数注入）与预期一致。纯 stdlib，任何环境可跑，可进 CI。
- **动态层：** 把 `skills/grasshopper-recipe-modeling/references/mcp-execution.md` 里的
  数据审计检查项（PlaceErrors 为空、WiresOk 等于请求数、Messages 无错误、关键 lane 的
  branches/items/sample 符合预期、配对列表长度相等）固化成审计清单 schema（JSON），加
  `audit` 子命令：对 solve 后的 canvas 数据自动生成"通过/失败"报告。
- 验证结果（含失败）落盘 `logs/audits/`，作为 `/gh-ok` 决策的数据依据。

### 2.2 状态文档自动生成，消灭多头漂移

**方案：** 加 `gh-sync` 式生成脚本：从 `recipes/index.json` + validate 输出 + recipe-health
报告**自动生成** CLAUDE.md 的状态表段与 planning/checkpoint.md。人工只维护 index.json 一处，
其余是产物。

---

## 3. 阶段三：生长机制（P2 —— 让库越用越值钱）

### 3.1 Recipe 声明"公共接口"，把 Recipe 当函数用（架构级改进）

**问题：** recipe.json 只有参数契约（输入），没有输出契约；链式组合时 AI 需读 wiring.json
猜"哪个端口是出口"。

**方案：** recipe.json 增加 `outputs: [{name, node, port, type, description}]`：
- `chain_bridges` 改为引用公共输出名而非内部节点 id → 拓扑编辑不破坏桥接。
- 组合检查变为**类型驱动**：Recipe B 的 `chain_input`（如 GH_Surface）↔ Recipe A 的公共
  输出类型直接可判，配合 1.1 的类型兼容表，链式组合在编译期就能验证"能不能接"。
- 这是把 recipe 从"图模板"升级为"带类型签名的函数"，也是未来组合搜索/自动桥接推荐的地基。

### 3.2 Recipe 入库检查单脚本化

**方案：** `admit_recipe` 子命令一键检查入库必备项：schema 合法、GUID 可解析、参数默认值在
slider 范围内、chain_input/输出契约已声明、index.json 有条目、knowledge 引用已更新——
全部通过才允许标记 verified。把"沉淀知识"从"记得做"变成"检查过了"。

### 3.3 覆盖率矩阵 + 失败日志模式

- 从 index.json 自动生成"计划队列 vs 已完成"覆盖率矩阵（替代 planning/checkpoint.md 里
  手工维护的"8/?"计数）。
- knowledge 增加"失败模式"文档（curve-attractor-case 已开了头）：结构化记录失败组合尝试 +
  诊断（如"13 分支 Bounds 语义错误"），与 logs/ 会话日志打通。失败记录比成功记录更能防止
  重复踩坑。

---

## 4. 不建议做的事（防过度优化）

- **不要自动化"视觉验证"**：几何是否符合设计意图必须保留用户目视（SKILL.md 已明确，这是
  正确边界）。
- **不要重写 legacy 路径**：保留兼容，只统一编译器，不推翻已验证的东西。
- **不要给 recipe 加"淘汰机制"之外的新状态**：一个 `deprecated` 标记够了，别引入复杂生命周期。

---

## 5. 执行顺序与优先级

| 顺序 | 事项 | 投入 | 直接消除的风险 |
|---|---|---|---|
| 1 | 3.1 公共输出接口 + 1.1 类型检查 | 中 | 连线错误 / 桥接静默失效（最大失效模式） |
| 2 | 1.2 健康检查 + 1.4 索引快照 | 小 | 换机后 recipe 静默失效、检索侧无库 |
| 3 | 2.1 静态 golden test | 小 | 回归无保障 |
| 4 | 2.2 状态文档自动生成 | 小 | 文档漂移 |
| 5 | 1.3 路径统一 | 小 | 双路径行为不一致 |
| 6 | 2.1 动态 audit + 3.2 入库检查单 | 中 | 验证靠人记 |
| 7 | 3.3 覆盖率矩阵 + 失败日志 | 小 | 队列状态漂移、重复踩坑 |

**核心原则：** 所有"AI 要记得做"的事，都改成"脚本检查过了"。

---

## 6. 决策记录

- **2026-08-13** 方案文档存放于 `dev/`（新建开发管理区），不放入 `knowledge/`（运行时知识库）
  或 `planning/`（产品战略）——理由：本方案讨论的是"代码库本身怎么改"，与"用库做什么"
  （knowledge）和"产品往哪走"（planning）性质不同，混放会导致 AI 在组合任务时误读工程文档。

- **2026-08-13** Kangaroo 布料任务（`logs/2026-08-13-kangaroo-cloth-mcp.md`）暴露一个
  **schema 盲区：recipe.json 无法表达"求解行为类型"**。现有 17 个 Recipe 全部是
  确定性几何生成（设参数→一次求值→出结果）；物理模拟 Recipe（Kangaroo）需要
  Reset/On 时序、持续迭代、数值收敛，且验证要加"数值审计"（坐标量级/收敛/锚点）。
  **决策：本轮不扩展 schema，先按最小侵入落位**——求解协议写入
  `knowledge/kangaroo-physics-patterns.md`，数值审计并入
  `skills/grasshopper-recipe-modeling/references/mcp-execution.md`。
  **未来提案（等第 2 个模拟类 Recipe 出现再实施）**：recipe.json 增加
  `solve_mode: "deterministic" | "physical"` 字段，可选项 `reset_node` / `on_node`
  标注求解控制节点；届时用 2-3 个模拟实例对齐字段设计后一次性迁移，并把
  knowledge 中的求解协议并入 recipe.json 声明。

- **2026-08-13（补充证据）** `kangaroo-cloth` 以 v2 入库后实测：
  **Boolean Toggle 无法作为公共参数暴露**——v2 compiler（`graph_ir.py`）只识别
  `SLIDER_GUID` 与三个 PURE_PARAM_GUIDS（Slider/Surface/Curve），Toggle 会被当普通组件发射，
  其连线端口在 MCP 侧按 Param 处理（`Src:''`），参数映射 `field:"value"` 也不适用。
  因此 `on`/`reset` 只能作为 wiring 内部固定节点，求解控制权留在 GH 里人工操作。
  这强化了 `solve_mode` 提案：物理模拟 Recipe 不仅需要参数契约，还需要**控制节点契约**
  （哪些节点是求解开关、时序如何）。kangaroo-cloth 的公共 interface 因此只含 7 个数值参数，
  求解协议由 `knowledge/kangaroo-physics-patterns.md` 兜底。
