# Test 04 — 两圆 Loft 锥形曲面

**级别：** L4（多分支 + 多汇聚）
**状态：** ✅ 通过

## 输入指令

```
用两个滑杆分别控制底圆和顶圆的半径，再用一个滑杆控制高度，Loft 成锥形曲面
```

## 预期连接逻辑

```
Slider R1 ──→ Circle_bottom [Radius]
Slider R2 ──→ Circle_top    [Radius]
Slider H  ──→ Unit Z [Factor]
               Circle_top [Circle] ──→ Move [Geometry]
               Unit Z [Unit vector] ──→ Move [Motion]
Circle_bottom [Circle] ──→ Loft [Curves]  ← 来源1
Move [Geometry]        ──→ Loft [Curves]  ← 来源2（同一 list 端口）
```

## 验证检查项

- [ ] 3 个 Slider（R1 / R2 / H）
- [ ] 两个独立 Circle 分支
- [ ] Move 同时接收 Circle_top（Geometry）和 Unit Z（Motion）
- [ ] Loft 的 Curves 端口接收两条线（list 输入）
- [ ] 几何体正确：Rhino 视口可见锥形曲面
- [ ] 调整 H Slider，曲面高度变化

## 输出文件

`test_04_loft_cone.json`
