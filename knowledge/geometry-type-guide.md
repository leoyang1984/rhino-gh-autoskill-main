# GH 几何类型兼容性指南

> 供 /gh-wire 在规划连线时判断类型是否兼容，以及需要哪种转换组件。

---

<!-- GENERATED:TYPE_COMPAT:START -->

> 本区块由 `knowledge/type-compat.json` 生成，请勿手工修改。

## 诊断等级

| 等级 | 含义 |
|---|---|
| EXACT | Source and target expose the same declared type. |
| KNOWN_CAST | A reviewed Grasshopper conversion or widening conversion is expected to preserve the intended value. |
| WARN | Grasshopper may accept the connection, but the cast is runtime-dependent or can change semantics. |
| UNKNOWN | The available component snapshot or rule set cannot make a reliable decision. |
| INCOMPATIBLE | The direct wire is known to require an explicit adapter component. |

## 已审核的非同类型直连规则

| 输出类型 | 输入类型 | 结论 | 说明 |
|---|---|---|---|
| `GH_Circle` | `GH_Curve` | KNOWN_CAST | A circle can be consumed as a curve. |
| `GH_Ellipse` | `GH_Curve` | KNOWN_CAST | An ellipse can be consumed as a curve. |
| `GH_Surface` | `GH_Interval2D` | KNOWN_CAST | Grasshopper extracts the UV domain for Domain² inputs. |
| `GH_Number` | `GH_Integer` | WARN | The implicit numeric cast can round or truncate a non-integer value. |
| `GH_Number` | `GH_Interval` | WARN | Grasshopper may construct a 0..N domain; confirm that this domain semantics is intended. |
| `IGH_Goo` | `GH_Number` | WARN | The generic source type hides the runtime value; CastFrom decides compatibility. |
| `IGH_Goo` | `GH_Curve` | WARN | The generic source type hides the runtime geometry; CastFrom decides compatibility. |
| `IGH_Goo` | `GH_Vector` | WARN | The generic source type hides the runtime value; CastFrom decides compatibility. |
| `IGH_Goo` | `IGH_GeometricGoo` | WARN | Only runtime geometric values can satisfy this narrowing conversion. |
| `IGH_GeometricGoo` | `GH_Curve` | WARN | Only runtime curve values can satisfy this narrowing conversion. |
| `GH_Number` | `GH_Vector` | INCOMPATIBLE | A scalar does not directly define a vector. 建议适配器：Unit X / Unit Y / Unit Z。 |
| `GH_Number` | `GH_Point` | INCOMPATIBLE | A scalar does not directly define a point. 建议适配器：Construct Point。 |
| `GH_Point` | `GH_Plane` | INCOMPATIBLE | A point does not define plane orientation. 建议适配器：XY Plane / XZ Plane。 |
| `GH_Brep` | `GH_Surface` | INCOMPATIBLE | A Brep may contain several faces and requires an explicit selection. 建议适配器：Deconstruct Brep + List Item。 |
| `GH_Curve` | `GH_Surface` | INCOMPATIBLE | A curve does not directly define a surface. 建议适配器：Loft / Boundary Surfaces / Patch。 |

<!-- GENERATED:TYPE_COMPAT:END -->


## 基本类型层级

```
IGH_GeometricGoo        ← 接受任何几何体（最宽泛）
  ├─ GH_Brep            ← 实体/多面体
  ├─ GH_Surface         ← 单张曲面
  ├─ GH_Curve           ← 曲线（含直线、椭圆、矩形等）
  ├─ GH_Point           ← 点
  └─ GH_Mesh            ← 网格

IGH_Goo                 ← 接受任何数据（最宽泛，含几何和数值）

GH_Number               ← 数值
GH_Integer              ← 整数
GH_Boolean              ← 布尔值
GH_Interval             ← 一维域（如 0..1）
GH_Interval2D           ← 二维域（曲面 UV 域）
GH_Vector               ← 向量
GH_Plane                ← 平面（含原点 + 法向）
```

---

## 链式组合中的常见桥接

| Recipe A 输出 | 桥接 | Recipe B 接受 |
|--------------|------|--------------|
| 曲线列表（旋转楼板等） | Loft | GH_Surface → facade-* |
| GH_Brep（建筑实体） | Deconstruct Brep + List Item | GH_Surface → facade-* |
| GH_Number list（吸引子值） | 直接连接 | Factor / Scale 参数 |
| GH_Point（网格点） | Distance | GH_Number（距离值）|

---

## 常见错误与诊断

| 现象 | 原因 | 解决 |
|------|------|------|
| 组件橙色警告 | 类型不匹配 | 查本表，加转换组件 |
| Loft 失败 | 曲线方向不一致 | 加 Flip Curve 统一方向 |
| Divide Domain² 无输出 | Surface 输入为 null | 检查上游 BoundarySurf 是否正常 |
| List Item 越界 | Index 超出列表长度 | 开启 Wrap=True 或减小 Index |
| Boundary Surfaces 失败 | 曲线不闭合 | 检查 Rectangle 是否正确生成 |
