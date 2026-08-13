# Test 02 — 共享 Slider 同时控制半径和高度

**级别：** L2（一对多连线）
**状态：** ✅ 通过

## 输入指令

```
用一个滑杆同时控制半径和高度，画一个圆，挤出成等比圆柱
```

## 预期连接逻辑

```
Number Slider (Size)
  ├─[Value]→ Circle [Radius]
  └─[Value]→ Unit Z [Factor]

Circle
  └─[Circle]→ Extrude [Base]

Unit Z
  └─[Unit vector]→ Extrude [Direction]
```

## 验证检查项

- [ ] 只有 1 个 Slider（不是 2 个）
- [ ] Slider 输出连了 2 条线（到 Circle.Radius 和 Unit Z.Factor）
- [ ] 几何体正确：圆柱半径 = 高度
- [ ] 节点位置不重叠

## 输出文件

`test_02_shared_slider.json`
