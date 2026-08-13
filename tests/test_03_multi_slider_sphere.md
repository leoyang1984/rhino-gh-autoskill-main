# Test 03 — 多 Slider 控制球体位置和半径

**级别：** L3（多输入汇聚）
**状态：** ✅ 通过

## 输入指令

```
用三个滑杆分别控制球心的 X、Y、Z 坐标，再用一个滑杆控制半径，画一个球
```

## 预期连接逻辑

```
Slider X ──→ Construct Point [X coordinate]
Slider Y ──→ Construct Point [Y coordinate]
Slider Z ──→ Construct Point [Z coordinate]
             Construct Point [Point] ──→ XY Plane [Origin] ──→ Sphere [Base]
Slider R ─────────────────────────────────────────────────────→ Sphere [Radius]
```

## 验证检查项

- [ ] 4 个 Slider，各自独立
- [ ] Construct Point 同时接收 3 个输入（多对一汇聚）
- [ ] 类型链正确：Point → XY Plane → Sphere.Base(GH_Plane)
- [ ] 拖动 X/Y/Z Slider，球心移动
- [ ] 拖动 R Slider，球体大小变化

## 输出文件

`test_03_multi_slider_sphere.json`
