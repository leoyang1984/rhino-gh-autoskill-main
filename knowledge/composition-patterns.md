# Recipe 组合模式

> 本文档记录 Recipe 链式组合的设计模式，供 Claude 在新 session 中理解并执行多 Recipe 组合任务。

---

## 核心概念

Recipe 之间有两种组合方式：

### 1. 参数共享（并列）
两个 Recipe 共享输入参数（如 Width），各自独立产出几何。没有因果关系，适合"同时生成体量和独立参考面"的场景。

```
Slider(Width) → Recipe A
             → Recipe B
```

**局限：** 视觉上两组几何没有关联，不是真正的建筑工作流。

---

### 2. 几何管道（链式）✅ 推荐
Recipe A 的几何输出，经过**桥接组件**类型转换后，成为 Recipe B 的几何输入。形成真正的因果链。

```
Recipe A 输出 → [桥接组件] → Recipe B 输入
```

**效果：** 两个 Recipe 在视觉上是同一个设计方案的不同层次，用户改动 A 的参数，B 自动响应。

---

## 几何桥接模式（Geometric Chaining）✅ 推荐
> A 的公共几何输出 → B 的公共几何输入，形成真正的物理因果链。

### 模式 1：曲线列表 → Loft → 曲面

**适用场景：** Recipe A 产出一系列截面曲线（如旋转楼板），需要生成连续外皮曲面。

```
mass-rotate.profile_curves（旋转椭圆列表）
    → Loft (Curves输入, Loft输出: GH_Surface)
        → facade-panel-flat / facade-grid
```

**验证状态：** ✅ 2026-04-13 跑通（螺旋塔楼 + 曲面平板幕墙）

**桥接组件：** Loft (`a7a41d0a-2188-4f7a-82cc-1a2c4e4ec850`)
**桥接类型：** `bridge_type: "geometric"`

---

### 模式 2：实体 → Deconstruct Brep + List Item → 某一面

**适用场景：** Recipe A 产出 Brep 实体（建筑体块），需要取其中某一立面做表皮处理。

```
mass-extrude.floor_breps（GH_Brep 列表）
    → Deconstruct Brep (Faces: GH_Surface list)
        → List Item (Index=FaceIndex slider)
            → facade-grid / facade-panel-flat
```

**验证状态：** ✅ 2026-04-13 跑通（矩形体量 + 立面 UV 分格）

**桥接组件：**
- Deconstruct Brep (`8d372bdc-9800-45e9-8a26-6e33c5253e21`)
- List Item (`59daf374-bc21-4a5e-8282-5504fb7ae9ae`)
**桥接类型：** `bridge_type: "geometric"`

**注意：** 矩形 Brep 有 6 个面（0=底, 1=顶, 2-5=四侧面）。加 FaceIndex slider 让用户选择。

**扩展验证：** ✅ 2026-04-17 跑通（`mass-setback` + `facade-grid`）

当 Recipe A 输出的是 **Brep 列表** 而不是单个 Brep 时，可先加一级 `List Item` 选中目标体量，再继续拆面：

```
mass-setback.tier_breps（GH_Brep list）
    → List Item (Index=TierIndex slider)
        → Deconstruct Brep (Faces: GH_Surface list)
            → List Item (Index=FaceIndex slider，可输入 0/1/2/3... 多个索引)
                → facade-grid
```

**适用场景：** 退台、分段塔楼、分块体量等“多段 Brep 列表”输出。

---

### 模式 3：直接连接（GH_Surface → GH_Surface，无桥接组件）

**适用场景：** Recipe A 的最终输出已经是 `GH_Surface`（如 Loft 曲面），可直接作为 facade-* 的曲面输入，无需任何类型转换组件。

```
mass-taper.mass_surface（GH_Surface）
    →（直接连接）→ facade-grid / facade-panel-flat (Divide Domain².Domain + Isotrim.Surface)
```

**触发条件：** Recipe A 的输出端口类型已是 `GH_Surface`（不是 Brep、不是 Curve list）。

**桥接组件：** 无（bridge: "Direct"）
**桥接类型：** `bridge_type: "geometric"`

**类型链：** `GH_Surface` → `GH_Surface`（透明传递）

**验证状态：** ✅ 2026-04-16 通过（mass-taper + facade-grid，锥形体量 → 立面分格）

---

## 参数协调模式（Parameter Coordination）
> A 的公共数值输出 → B 的公共参数，用于尺寸对齐或数值场驱动。

### 模式 4：数值场 → 直接驱动几何参数（GH_Number list → Factor）

**适用场景：** attractor-remap 产出数值列表，直接驱动几何操作的参数（如 Scale Factor、高度偏移）。无需桥接组件，GH 原生支持列表数值驱动 Factor 端口。

```
attractor-remap.mapped_values（GH_Number list）
    →（直接连接）→ facade-panel-flat (Scale.Factor)    ← 替换固定 ScaleFactor slider
    →（直接连接）→ array-linear / array-radial (Move.Factor 等)
```

**关键约束：** 列表长度必须匹配几何体数量（GridCount² = U_Count × V_Count）。
建议用同一个 GridCount slider 同时控制数值场和面板网格的分格数，确保严格对应。

**验证状态：** ✅ 2026-04-14 通过（attractor-remap + facade-panel-flat，吸引子驱动幕墙内缩）
**桥接类型：** `bridge_type: "parameter"`

---

### 模式 5：参数共享（GH_Number → GH_Number，尺寸联动）

**适用场景：** Recipe B 不接受几何输入，而是从数值参数自行生成几何。通过共用 Recipe A 的尺寸参数（如宽度、高度），让两套几何在空间上自动对齐。

```
mass-podium-tower.podium_width（GH_Number）
    →（参数共用）→ facade-louver (Division.A = 百叶总宽度)
mass-podium-tower.podium_height（GH_Number）
    →（参数共用）→ facade-louver (TopPts.Z = 百叶总高度)
```

**触发条件：** Recipe B 从坐标/数值生成几何（如 Series 生成等距点阵），无法接受曲面/Brep 输入。通过共享 Recipe A 的尺寸数值实现空间对齐。

**验证状态：** ✅ 2026-04-16 通过（mass-podium-tower + facade-louver，裙房尺寸驱动百叶覆盖范围）
**桥接组件：** 无（bridge: "Parameter Sharing"）
**桥接类型：** `bridge_type: "parameter"`

---

## 链式组合设计原则

1. **去掉 Recipe B 的几何生成前缀**
   链式时，Recipe B 的 Rectangle/BoundarySurf 等"自建曲面"节点要去掉，改为直接接收来自桥接组件的曲面。

2. **保留 Recipe B 的处理核心**
   Divide Domain² + Isotrim + Area + Scale 等"处理逻辑"节点完整保留。

3. **FaceIndex 或桥接参数暴露给用户**
   桥接过程中产生的选择（如取第几个面）应作为 slider 暴露，不要硬编码。

4. **共享参数只定义一次**
   两个 Recipe 都用到的参数（如 Width、Floors）只放一个 slider，分叉连接两条分支。

---

## 如何识别链式组合意图

用户描述中出现以下模式时，优先考虑链式：
- "体量 + 表皮"：`mass-*` → 桥接 → `facade-*`
- "塔楼 + 幕墙"：`mass-rotate` → Loft → `facade-panel-flat`
- "阵列 + 参数化"：`array-*` → `attractor-remap`（数值驱动）
- 描述中有明显的先后因果：先做 A，再对 A 做 B

---

## 与 recipe.json 的关系

Recipe v2 用稳定公共名称描述输入、输出和组合规则。跨 Recipe 规则不得引用内部节点 id：

```json
"composition_rules": [
  {
    "id": "profiles_to_facade_grid",
    "target_recipe": "facade-grid",
    "bindings": [
      {
        "from_output": "profile_curves",
        "to": {"input": "surface"},
        "adapters": [{"selector": "<Loft GUID>", "input_port": "Curves", "output_port": "Loft"}]
      }
    ]
  }
]
```

检测到多 Recipe 意图时，运行 `compile_recipe.py compose <source> <target>`。
组合器负责命名空间、输入前缀裁剪、adapter 插入和统一结构/类型验证。
