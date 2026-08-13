# Test 01 — Slider → Circle → Extrude 圆柱体

**级别：** L1（线性链式）
**状态：** ✅ 通过

## 输入指令

```
用一个滑杆控制半径，画一个圆，再把圆挤出成圆柱体
```

## 预期连接逻辑

```
Number Slider (半径)
  └─[Value]→ Circle [Radius]

Circle
  └─[Circle]→ Extrude [Base]

Number Slider (高度，可与半径共用或新建)
  └─[Value]→ Unit Z [Factor]

Unit Z
  └─[Unit vector]→ Extrude [Direction]
```

## 验证检查项

- [ ] 所有 GUID 存在于 component_library.json
- [ ] Circle.Radius 接收的是 GH_Number 类型 ✓
- [ ] Extrude.Base 接收的是 IGH_GeometricGoo（Circle 输出的 GH_Circle 是几何体）✓
- [ ] Extrude.Direction 接收的是 GH_Vector（不能直接接 Number）
- [ ] 节点位置不重叠（x 间距 ≥ 200）

## 输出文件

`test_01_slider_circle_extrude.json`
