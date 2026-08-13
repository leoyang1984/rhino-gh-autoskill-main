# Rhino 8 / Grasshopper Python 编码规则

> 生成任何在 GH 内运行的 Python 脚本前，必须对照此文件检查。
> 每条规则都来自真实踩过的坑。

---

## R1 — Hidden 属性不存在

**错误写法：**
```python
if proxy.Obsolete or proxy.Hidden:
```

**正确写法：**
```python
if proxy.Obsolete or getattr(proxy, 'Hidden', False):
```

**原因：** Rhino 8 的 `GH_ObjectProxy` 没有 `Hidden` 属性，直接访问会抛 `AttributeError`，被 except 吞掉后导致所有组件静默跳过，输出空数组。

---

## R2 — 不能用 FindObjectByComponentGuid

**错误写法：**
```python
proxy = Grasshopper.Instances.ComponentServer.FindObjectByComponentGuid(guid)
```

**正确写法：**
```python
proxy_index = {str(p.Guid).lower(): p for p in server.ObjectProxies}
proxy = proxy_index.get(guid_str.lower())
```

**原因：** `GH_ComponentServer` 在 Rhino 8 中没有 `FindObjectByComponentGuid` 方法，需要手动建索引。

---

## R3 — Slider 没有 Params 属性

**错误写法：**
```python
src_param = next((p for p in from_node.Params.Output if p.Name == name), None)
```

**正确写法：**
```python
if isinstance(from_node, ghk.IGH_Param):
    src_param = from_node          # Slider 本身就是参数
else:
    src_param = next((p for p in from_node.Params.Output if p.Name == name), None)
```

**原因：** `GH_NumberSlider`、`GH_Panel` 等是 `IGH_Param` 而非 `IGH_Component`，它们本身就是输入/输出参数，没有 `Params.Input` / `Params.Output`。

---

## R4 — Slider 数值必须用 System.Decimal

**错误写法：**
```python
slider.Minimum = 0       # Python int
slider.Maximum = 100     # Python int
slider.Value   = 10      # Python int
```

**正确写法：**
```python
import System
slider.Minimum = System.Decimal(0)
slider.Maximum = System.Decimal(100)
slider.Value   = System.Decimal(10)
```

**原因：** `GH_NumberSlider` 的 `Minimum`/`Maximum`/`Value` 是 .NET `System.Decimal` 类型，Python int/float 无法隐式转换。

---

## R5 — import System 必须显式声明

```python
import System               # 用于 System.Decimal、System.Guid 等
import System.Drawing as sd  # 用于 PointF
```

**原因：** `System` 命名空间在 GH Python 里不自动导入，必须显式声明，否则 `System.Decimal` 会报 `NameError`。

---

## R6 — Slider 预设值必须在 AddObject 之后设置

**错误写法：**
```python
slider.Minimum = System.Decimal(0)
doc.AddObject(obj, False)   # AddObject 会重置 slider 状态
```

**正确写法：**
```python
doc.AddObject(obj, False)
slider.Minimum = System.Decimal(0)   # 加入文档后再设值
slider.Maximum = System.Decimal(100)
slider.Value   = System.Decimal(10)
```

**原因：** `AddObject` 初始化组件状态时会重置 slider 的 Minimum/Maximum/Value，必须在之后赋值才能生效。

---

## R7 — 运行时修改已放置的 Slider：用 obj.Slider.Value，不是 obj.Value

**错误写法：**
```python
obj.Value = -0.3        # GH_NumberSlider 组件没有可写的 Value 属性
```

**正确写法：**
```python
import System
obj.Slider.Value = System.Decimal(-0.3)   # GH_SliderBase.Value 可写
```

**原因：** canvas 上的 Number Slider 是 `GH_NumberSlider` 组件，数值存放在底层
`GH_SliderBase`（`obj.Slider`）上。`obj.Value` 要么 AttributeError，要么静默失败
（赋值后读回仍是旧值）。设置后需触发一次 GH 求解才生效。

---

## 检查清单（生成脚本后过一遍）

- [ ] 所有 `proxy.属性` 访问是否用了 `getattr` 兜底？
- [ ] 是否用了 `FindObjectByComponentGuid`？（禁用，改用索引）
- [ ] 连线逻辑是否区分了 `IGH_Param` 和 `IGH_Component`？
- [ ] Slider 数值赋值是否包了 `System.Decimal()`？
- [ ] Slider 预设值是否在 `doc.AddObject()` **之后**设置？
- [ ] 文件顶部是否有 `import System`？
- [ ] 运行时改 slider 值用的是 `obj.Slider.Value = System.Decimal(...)` 而非 `obj.Value`？
