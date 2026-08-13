# 2026-04-12 — /gh-wire 技能注册 + 螺旋塔楼真实案例

## 完成的工作

### 1. /gh-wire 技能注册

**问题：** 最初将技能文件放在项目内 `.claude/skills/gh-wire.md`，未被 Claude Code 识别。

**根本原因：** Claude Code 技能需要：
- 放在 `~/.claude/skills/<name>/` 目录下（全局，非项目级）
- 文件名必须是 `SKILL.md`（大写）
- 包含标准 frontmatter：`name`、`preamble-tier`、`version`、`description`、`allowed-tools`

**修复：** 创建 `~/.claude/skills/gh-wire/SKILL.md`，技能立即出现在可用列表中，无需重启。

### 2. 新增已知组件

通过本次测试验证并补充至 `skills/gh-wiring.md`：

| 组件 | GUID | 备注 |
|------|------|------|
| Series | `e64c5fb1-845c-4ab1-8911-5f338516ba67` | Start/Step/Count → list |
| Ellipse | `46b5564d-d3eb-4bf1-ae16-15ed132cfd88` | Plane+R1+R2 → GH_Curve |
| Rotate | `b7798b74-037e-4f0c-8ac7-dc1043d093e0` | Geometry+Angle(rad)+Plane |
| Multiplication | `ce46b74e-00c9-43c4-805a-193b69ea4a11` | A×B → Result |
| Radians | `a4cd2751-414d-42ec-8916-476ebf62d7fe` | Degrees → Radians |

### 3. 螺旋塔楼真实案例（test_05）

**需求：** 椭圆截面（21000×7000mm）塔楼，20层，每层高5000mm，每层旋转5°。

**关键设计决策：**
- 用 `Series` 生成 0..19 索引，让 GH 的 list matching 自动处理批量操作
- `Rotate` 组件以 `XY Plane`（原点=椭圆重心）为旋转轴，无需额外定位
- 两个 `Unit Z` 实例分别处理可变高度（接 Series×FloorHeight）和固定挤出方向（接 FloorHeight slider）

**结果：** 16 节点、18 连线，一次生成通过。

## 当前已验证组件总数：15 个

见 `skills/gh-wiring.md` 已知组件表。
