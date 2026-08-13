# Test 05 — 螺旋上升塔楼（真实场景）

**级别：** 真实场景（复杂拓扑 + 参数化批量操作）
**状态：** ✅ 通过

## 输入指令

```
帮我创建一个螺旋上升的塔楼。基本型是椭圆，挤出5000mm，以重心为旋转点，
螺旋上升，上面的比下面的角度转5度，20层。椭圆长轴21000mm，短轴7000mm
```

## 拓扑结构

```
Slider(Floors=20) ──→ Series [Count]
Series [0..19] ──→ Mult_height [A] ←── Slider(FloorHeight=5000)
Series [0..19] ──→ Mult_angle  [A] ←── Slider(RotStep=5°)
Mult_angle → Radians
XY Plane ──→ Ellipse [Plane]
             Ellipse [Radius1] ←── Slider(RadiusLong=10500)
             Ellipse [Radius2] ←── Slider(RadiusShort=3500)
Ellipse + Radians + XY Plane ──→ Rotate（绕原点Z轴批量旋转20次）
Mult_height ──→ Unit Z_move [Factor]（生成20个高度向量）
Rotate + Unit Z_move ──→ Move（20层定位）
Slider(FloorHeight) ──→ Unit Z_extrude [Factor]
Move + Unit Z_extrude ──→ Extrude（20层楼板）
```

## 节点总数

16 个组件，18 条连线

## 关键技术点

- Series 批量生成索引，GH 自动 list matching 处理 20 层
- Rotate 组件绕 XY Plane（原点=椭圆重心）旋转，无需额外定位
- 两个 Unit Z 实例：一个接可变 Factor（高度偏移），一个接固定 Factor（挤出方向）
- Ellipse 输出 GH_Curve，Rotate/Extrude 的 GeometricGoo 端口隐式接受
