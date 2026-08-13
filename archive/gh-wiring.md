# Step 3B 组件参考表

> 本文件是 `/gh-wire` skill 的 Step 3B 查阅资源，**不是执行规范**。
> 执行规范见 `~/.claude/skills/gh-wire/SKILL.md`。

以下组件已通过测试验证，GUID 和端口名称准确，Step 3B 中可直接使用，无需搜索组件库。

## 已知关键组件

经过测试验证的组件，端口名称已确认准确。

### 输入控件
| 组件 | GUID | 说明 |
|------|------|------|
| Number Slider | `57da07bd-ecab-415d-9d86-af36d7073abc` | IGH_Param，输出 GH_Number，port 名写 `Value` |

### 数学 / 向量
| 组件 | GUID | 输入 | 输出 |
|------|------|------|------|
| Addition | `a0d62394-a118-422d-abb3-6af115c75b25` | A:any, B:any | Result:any |
| Multiplication | `ce46b74e-00c9-43c4-805a-193b69ea4a11` | A:any, B:any | Result:any |
| Radians | `a4cd2751-414d-42ec-8916-476ebf62d7fe` | Degrees:Number | Radians:Number |
| Series | `e64c5fb1-845c-4ab1-8911-5f338516ba67` | Start:Number, Step:Number, Count:Integer | Series:Number |
| Unit Z | `9103c240-a6a9-4223-9b42-dbd19bf38e2b` | Factor:Number | Unit vector:Vector |

### 点 / 平面
| 组件 | GUID | 输入 | 输出 |
|------|------|------|------|
| Construct Point | `3581f42a-9592-4549-bd6b-1c0fc39d067b` | X coordinate:Number, Y coordinate:Number, Z coordinate:Number | Point:Point |
| XY Plane | `17b7152b-d30d-4d50-b9ef-c9fe25576fc2` | Origin:Point | Plane:Plane |

### 曲线 / 曲面 / 几何体
| 组件 | GUID | 输入 | 输出 |
|------|------|------|------|
| Circle | `807b86e3-be8d-4970-92b5-f8cdcb45b06b` | Plane:Plane, Radius:Number | Circle:Circle |
| Ellipse | `46b5564d-d3eb-4bf1-ae16-15ed132cfd88` | Plane:Plane, Radius 1:Number, Radius 2:Number | Ellipse:Curve |
| Sphere | `dabc854d-f50e-408a-b001-d043c7de151d` | Base:Plane, Radius:Number | Sphere:Surface |
| Extrude | `962034e9-cc27-4394-afc4-5c16e3447cf9` | Base:GeometricGoo, Direction:Vector | Extrusion:GeometricGoo |
| Rotate | `b7798b74-037e-4f0c-8ac7-dc1043d093e0` | Geometry:GeometricGoo, Angle:Number(rad), Plane:Plane | Geometry:GeometricGoo |
| Move | `e9eb1dcf-92f6-4d4d-84ae-96222d60f56b` | Geometry:GeometricGoo, Motion:Vector | Geometry:GeometricGoo |
| Loft | `a7a41d0a-2188-4f7a-82cc-1a2c4e4ec850` | Curves:Curve **(list)** | Loft:Brep |

