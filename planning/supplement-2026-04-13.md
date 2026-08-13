# 补充文档：2026-04-13 会话决策记录

> 这是一份补充文档，供 Claude Code 读取后自行判断整合到项目的相关文件中。
> 不要直接覆盖现有文件，请根据内容语义决定放在哪里。
> 本文档是 supplement-2026-04-12.md 的延续，主要深化了阶段 A 的具体实现。

---

## 1. 技术判断：为什么不直接生成 GHX

有人提出 JSON 直接生成 GHX（XML）的路径，已确认不采用，原因如下：

- GHX 是 .NET 对象序列化结果，不是描述性 XML，没有统一 schema
- 每种组件的内部 XML 结构不同，直接生成等于手动维护每种组件的序列化格式
- 现有路径（JSON → Python 脚本 → GH 内运行 → GHX）让 GH 运行时负责序列化，AI 只描述"做什么"，GH 负责"怎么存"
- 这条原则和边界原则一致：确定性的工作交给脚本/运行时，不自己重造轮子

**此决策不需要重新讨论。**

---

## 2. L4.5 定义与通过标准

**定义：** Recipe 模式库阶段。把已验证的拓扑模式缓存为可调用的 Recipe，让 AI 从"每次从零规划"变成"识别意图 + 调用 Recipe + 填入参数"。

**通过标准（三条同时成立）：**
1. 同一意图描述，10次调用里至少8次匹配到正确 Recipe，不重新规划拓扑
2. Recipe 覆盖常见几何操作的80%场景（见下方列表第一批）
3. 两个 Recipe 可以组合调用并跑通

**验证用例：** 梦露大厦场景从"每次从头生成"变成"调用 `mass-rotate` Recipe + 参数注入"即算通过。

---

## 3. Recipe 库文件结构

每个 Recipe 是一个独立文件夹：

```
recipes/
├── index.json                 # 所有 Recipe 的摘要索引，AI 每次只读这一个
└── tower-rotate/              # 单个 Recipe 文件夹
    ├── recipe.json            # 元数据 + 参数接口
    ├── wiring.json            # 已验证的节点连接图
    ├── result.gh              # 可直接打开的 GH 文件
    └── preview.png            # 可视化缩略图（可选）
```

### recipe.json 标准格式

```json
{
  "id": "tower-rotate",
  "name": "旋转塔楼",
  "description": "椭圆或圆形楼板沿垂直轴渐变旋转堆叠",
  "tags": ["tower", "rotate", "floor", "extrude"],
  "parameters": {
    "radius_x":     { "type": "number",  "unit": "mm",  "default": 20000 },
    "radius_y":     { "type": "number",  "unit": "mm",  "default": 15000 },
    "floor_count":  { "type": "integer",                "default": 40    },
    "floor_height": { "type": "number",  "unit": "mm",  "default": 3500  },
    "rotate_total": { "type": "number",  "unit": "deg", "default": 90    }
  },
  "inputs":  ["radius_x", "radius_y", "floor_count", "floor_height", "rotate_total"],
  "outputs": ["brep", "floors"],
  "composable_with": ["facade-panel-flat", "floor-stack"]
}
```

### AI 调用流程

```
用户描述
   ↓
AI 读取 index.json（摘要，token 消耗小）
   ↓
AI 输出匹配结果（recipe id + 参数值）
   ↓
脚本层读取对应 wiring.json + 注入参数 → 生成 .gh
```

AI 只读 index.json 做匹配，不读 wiring.json，不碰拓扑。

---

## 4. Recipe 列表

### 第一批（L4.5 核心，优先实现）

**建筑体量**
- `mass-extrude` — 直线挤出体量（轮廓、层高、层数）
- `mass-rotate` — 旋转塔楼（椭圆楼板渐变旋转堆叠）
- `mass-taper` — 渐变收分体量（多截面 Loft）
- `floor-stack` — 标准层堆叠（轮廓阵列）

**表皮**
- `facade-grid` — 表皮网格分格（Surface UV 分格）
- `facade-panel-flat` — 平板幕墙（分格偏移成面）

**景观地形**
- `terrain-from-contour` — 等高线生成地形

**通用几何**
- `array-linear` — 线性阵列
- `array-radial` — 环形阵列
- `attractor-remap` — 吸引子映射（距离 → 数值重映射）

### 第二批（L4.5 → L10 补全）

**建筑体量**
- `mass-podium-tower` — 裙房+塔楼组合
- `mass-setback` — 退台体量
- `mass-boolean` — 体量切割
- `floor-offset` — 楼板偏移生成
- `core-place` — 核心筒布置

**表皮**
- `facade-louver` — 遮阳百叶
- `facade-parametric-tilt` — 渐变倾斜板
- `facade-perforate` — 穿孔表皮

**屋顶**
- `roof-flat` — 平屋顶
- `roof-slope` — 坡屋顶
- `roof-shell` — 壳体屋顶

**景观**
- `terrain-grade` — 场地平整
- `terrain-cut-fill` — 挖填方分析
- `path-offset-zone` — 路径缓冲区
- `paving-grid` — 矩形铺装分格
- `paving-radial` — 放射铺装
- `plant-array-grid` — 网格种植
- `plant-array-path` — 沿路径种植
- `plant-cluster` — 组团种植
- `water-edge` — 水岸线生成
- `ramp-slope` — 无障碍坡道

**通用几何**
- `array-on-surface` — 表面分布
- `morph-between` — 两形态渐变
- `boundary-offset` — 边界内缩

### 第三批（按需沉淀）
用户遇到新场景跑通后，系统提示是否存为新 Recipe，由用户决定是否入库。

---

## 5. Recipe 库生长机制

Recipe 库不只由开发者填充，用户也是贡献者：
- 每次用户跑通一个新场景，系统提示是否存为新 Recipe
- 用户的库越积累越有价值，越难迁移——这是订阅模式的护城河
- 库的生长机制比初始内容更重要

---

## 6. 商业模式补充

- 订阅制 + 年度升级承诺
- 用户从某个 L 等级开始订阅，每年交付一个可验证的能力跃迁
- 目标市场不局限于中国，全球参数化设计圈都是潜在用户
- 商业地产方向（户型生成、面积配比）可能比建筑师工具更早到达可交付状态
- 卖的不是软件功能，是持续进化的路线图
