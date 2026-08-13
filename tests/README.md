# 测试用例

每个测试是一对文件：
- `test_XX_描述.md` — 输入指令 + 预期连接逻辑
- `test_XX_描述.json` — AI 生成的 wiring.json 输出

## 测试分级

| 级别 | 说明 |
|------|------|
| L1 | 线性链式：A→B→C，无分支 |
| L2 | 单分支：一个输出接多个下游 |
| L3 | 多输入汇聚：多个 Slider 控制同一组件 |
| L4 | 复杂拓扑：多分支 + 多汇聚 |
| L4.5 | Recipe 模式库：AI 识别意图 → 匹配 Recipe → 注入参数，不重新规划拓扑 |

### L4.5 通过标准（三条同时成立）

1. 同一意图描述，10次调用里至少8次匹配到正确 Recipe
2. Recipe 覆盖常见几何操作的80%场景（见 `recipes/index.json`）
3. 两个 Recipe 可以组合调用并跑通

## 当前测试

| 文件 | 级别 | 状态 |
|------|------|------|
| test_01_slider_circle_extrude.md | L1 | ✅ 通过 |
| test_02_shared_slider.md | L2 | ✅ 通过 |
| test_03_multi_slider_sphere.md | L3 | ✅ 通过 |
| test_04_loft_cone.md | L4 | ✅ 通过 |
| test_05_spiral_tower.md | 真实场景 | ✅ 通过 |

## 编译器回归测试

`test_compile_recipe.py` 冻结 17 个现有 Recipe 的默认 MCP 编译载荷，作为
schema 和编译器重构前的现状基线。它还覆盖参数注入与主要错误输入。

运行：

```bash
python3 tests/test_compile_recipe.py
```

只有在确认编译输出的变化是预期行为时，才允许显式更新基线：

```bash
python3 tests/test_compile_recipe.py --update-baselines
```

更新后必须审查 `tests/baselines/recipe_payloads.json` 的差异，不能把更新基线
当成修复测试失败的默认手段。

## Recipe schema v2 迁移预览

现有未声明 `schema_version` 的 Recipe 按 v1 读取。可以生成只读的 v2 草案和
待人工确认事项：

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py \
  migrate mass-rotate --dry-run
```

当前迁移命令不会写入 Recipe；不带 `--dry-run` 会直接拒绝执行。

## 统一 Graph IR

Recipe 和现场规划生成的普通 wiring 共享同一结构验证器：

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py \
  validate-wiring tests/test_01_slider_circle_extrude.json
```

编译已有 Recipe 时可选择 MCP payload 或 legacy wiring 输出：

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py \
  compile mass-rotate --emit mcp
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py \
  compile mass-rotate --emit wiring --set floors=12
```

## 渐进式类型检查

`validate` 默认报告 `EXACT / KNOWN_CAST / WARN / UNKNOWN / INCOMPATIBLE`
及当前组件快照覆盖率。只有明确的 `INCOMPATIBLE` 会在默认模式阻断编译；
`WARN` 和 `UNKNOWN` 保留诊断但继续运行。

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py validate
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py \
  compile mass-rotate --type-report
```

严格模式额外阻断 `WARN` 和 `UNKNOWN`，目前用于规则调试，不作为默认门禁：

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py \
  validate mass-rotate --strict-types --type-details
```

## Recipe v2 接口测试

17 个 Recipe 均声明 `interface.parameters / inputs / outputs`。接口测试会检查：

- 每个 Recipe 至少一个公共输出；
- 公共输入的 replace binding 对应现有内部连线目标；
- 组件快照已覆盖的公共输出端口确实存在；
- v2 元数据不改变阶段 0 冻结的 MCP payload。

## Recipe 公共接口组合

8 条已迁移组合规则均通过静态组合、结构验证和默认类型门禁：

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py \
  compose mass-rotate facade-grid --emit wiring --type-report
```

组合器会给两侧节点加命名空间，裁剪被公共输入替换的自生成前缀，并按规则
插入 adapter 组件和桥接 Slider。组合规则不再引用 `n10`、`n14` 等内部 ID。

## 环境快照与健康检查

环境验证刻意保持离线。先在真实 Rhino/Grasshopper 会话中运行
`scripts/scan_gh_components.py` 导出快照，再运行：

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py health \
  --snapshot data/component_library.json
```

当前机器的报告写入 `logs/health/`。只有经过审查的完整快照才可以另行提升为
`data/reference/component_snapshot.json` 共享基线。

## 动态审计与准入

实时 MCP 结果先按 `schemas/audit-evidence-v1.schema.json` 归一化并保留在
`raw` 字段，再执行：

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py audit \
  --evidence logs/audits/mass-rotate-evidence.json
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py admit \
  mass-rotate --audit logs/audits/mass-rotate-audit.json
```

`audit` 自动检查放置、连线、求解、画布计数、GH Messages 和关键输出断言。
结构通过与视觉通过是两件事；只有证据中明确记录用户 `approved`，`admit`
才会返回 ready。

## 索引与状态同步

`recipe.json` 是 Recipe 摘要的事实源。同步脚本生成 `recipes/index.json`，并且只
改动 `CLAUDE.md` 与 `planning/checkpoint.md` 的标记区块：

```bash
python3 scripts/sync_project_status.py
python3 scripts/sync_project_status.py --check
```
