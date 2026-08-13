# GH AI Wiring — Claude Code Plugin 实现方案

> 目标：扫描本机 Grasshopper 组件库 → 存成 JSON → Claude Code 读取用户指令 → 生成 GH 电池连接图

---

## 项目结构

```
gh-ai-wiring/
├── CLAUDE.md                  # Claude Code 技能入口
├── skills/
│   └── gh-wiring.md           # /gh-wire 技能定义
├── scripts/
│   ├── scan_gh_components.py  # GH 内部运行：扫描组件库
│   └── build_gh_file.py       # 接收 JSON → 写入 .gh 文件
├── data/
│   └── component_library.json # 扫描结果（自动生成）
└── watcher/
    └── gh_file_watcher.gh     # GH 内监听文件变化的 Python 组件
```

---

## 阶段 1：扫描组件库

### 运行环境
在 Grasshopper 内部的 **Python Script 组件**中运行（GH 提供完整的 .NET 运行时）。

### `scripts/scan_gh_components.py`

```python
import Grasshopper
import json
import os

def scan_components():
    server = Grasshopper.Instances.ComponentServer
    components = []

    for proxy in server.ObjectProxies:
        try:
            # 跳过过时/隐藏组件
            if proxy.Obsolete or proxy.Hidden:
                continue

            obj = proxy.CreateInstance()
            if obj is None:
                continue

            comp_data = {
                "guid": str(proxy.Guid),
                "name": proxy.Desc.Name,
                "nickname": proxy.Desc.NickName,
                "category": proxy.Desc.Category,
                "subcategory": proxy.Desc.SubCategory,
                "description": proxy.Desc.Description,
                "inputs": [],
                "outputs": []
            }

            # 提取输入端口
            if hasattr(obj, "Params") and obj.Params is not None:
                for p in obj.Params.Input:
                    comp_data["inputs"].append({
                        "name": p.Name,
                        "nickname": p.NickName,
                        "description": p.Description,
                        "type": str(p.Type) if hasattr(p, "Type") else "unknown",
                        "access": str(p.Access)  # item / list / tree
                    })

                for p in obj.Params.Output:
                    comp_data["outputs"].append({
                        "name": p.Name,
                        "nickname": p.NickName,
                        "description": p.Description,
                        "type": str(p.Type) if hasattr(p, "Type") else "unknown"
                    })

            components.append(comp_data)

        except Exception as e:
            # 跳过无法实例化的组件
            continue

    return components


# 输出路径（修改为你的项目路径）
OUTPUT_PATH = r"C:\Users\<你的用户名>\gh-ai-wiring\data\component_library.json"

components = scan_components()

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(components, f, ensure_ascii=False, indent=2)

print(f"✅ 扫描完成：{len(components)} 个组件 → {OUTPUT_PATH}")
```

### 运行方式
1. 打开 Rhino + Grasshopper
2. 放一个 **Python Script** 组件在 canvas 上
3. 把上面代码粘进去，修改 `OUTPUT_PATH`
4. 右键 → Run（或连一个 Button 触发）
5. 生成 `component_library.json`

### 输出示例

```json
[
  {
    "guid": "59e0b89a-e487-49f8-827f-53e7d2a7d4f0",
    "name": "Addition",
    "nickname": "A+B",
    "category": "Maths",
    "subcategory": "Operators",
    "description": "Mathematical addition",
    "inputs": [
      { "name": "A", "nickname": "A", "description": "First operand", "type": "float", "access": "tree" },
      { "name": "B", "nickname": "B", "description": "Second operand", "type": "float", "access": "tree" }
    ],
    "outputs": [
      { "name": "Result", "nickname": "R", "description": "A + B", "type": "float" }
    ]
  }
]
```

---

## 阶段 2：Claude Code 技能定义

### `CLAUDE.md`（项目根目录）

```markdown
# GH AI Wiring

这是一个 Grasshopper 电池图生成工具。

## 可用技能
- `/gh-wire` — 根据自然语言描述生成 GH 组件连接图

## 数据
- `data/component_library.json` — 本机 GH 组件库（运行 scan_gh_components.py 生成）
- `output/` — 生成的 .gh 文件输出目录
```

### `skills/gh-wiring.md`

````markdown
# /gh-wire

根据用户的自然语言描述，从本机 Grasshopper 组件库中选取合适的组件，生成电池连接图。

## 执行步骤

1. **读取组件库**
   读取 `data/component_library.json`，获取所有可用组件及其端口信息。

2. **理解用户意图**
   分析用户描述，拆解成需要的计算步骤。

3. **选取组件 + 规划连接**
   从组件库中匹配最合适的组件，生成连接拓扑：
   - 每个节点有唯一 ID
   - 连接格式：`源节点ID:输出端口名 → 目标节点ID:输入端口名`

4. **输出 wiring JSON**
   将结果写入 `output/wiring.json`

5. **（可选）构建 .gh 文件**
   调用 `scripts/build_gh_file.py` 将 wiring.json 转成可在 GH 中打开的文件

## 输出格式（wiring.json）

```json
{
  "description": "用户描述的任务",
  "nodes": [
    {
      "id": "n1",
      "guid": "...",
      "name": "Number Slider",
      "position": { "x": 0, "y": 0 },
      "preset": { "value": 10, "min": 0, "max": 100 }
    },
    {
      "id": "n2",
      "guid": "...",
      "name": "Circle",
      "position": { "x": 300, "y": 0 }
    }
  ],
  "connections": [
    {
      "from": { "node": "n1", "port": "Value" },
      "to":   { "node": "n2", "port": "Radius" }
    }
  ]
}
```

## 示例调用

```
/gh-wire 用一个 Slider 控制半径，画一个圆，再把圆 Extrude 成一个圆柱体
```

期望输出：
- Number Slider → Circle (Radius)
- Circle (Circle) → Extrude (Base)
- Number Slider → Extrude (Height)（或另一个 Slider）
````

---

## 阶段 3：写入 GH 文件

### `scripts/build_gh_file.py`（GH 内 Python 组件运行）

```python
import Grasshopper
import Grasshopper.Kernel as ghk
import System.Drawing as sd
import json
import os

WIRING_PATH = r"C:\Users\<你的用户名>\gh-ai-wiring\output\wiring.json"
OUTPUT_GH   = r"C:\Users\<你的用户名>\gh-ai-wiring\output\result.gh"

with open(WIRING_PATH, "r", encoding="utf-8") as f:
    wiring = json.load(f)

doc = ghk.GH_Document()
node_map = {}  # id → IGH_Component 实例

# 1. 放置组件
for node in wiring["nodes"]:
    guid = System.Guid(node["guid"])
    proxy = Grasshopper.Instances.ComponentServer.FindObjectByComponentGuid(guid)
    if proxy is None:
        print(f"⚠️ 找不到组件：{node['name']} ({node['guid']})")
        continue

    obj = proxy.CreateInstance()
    obj.CreateAttributes()
    obj.Attributes.Pivot = sd.PointF(node["position"]["x"], node["position"]["y"])
    doc.AddObject(obj, False)
    node_map[node["id"]] = obj

# 2. 连线
for conn in wiring["connections"]:
    from_node = node_map.get(conn["from"]["node"])
    to_node   = node_map.get(conn["to"]["node"])
    if from_node is None or to_node is None:
        continue

    from_port_name = conn["from"]["port"]
    to_port_name   = conn["to"]["port"]

    # 找输出端口
    src_param = next((p for p in from_node.Params.Output if p.Name == from_port_name), None)
    # 找输入端口
    tgt_param = next((p for p in to_node.Params.Input  if p.Name == to_port_name),   None)

    if src_param and tgt_param:
        tgt_param.AddSource(src_param)
    else:
        print(f"⚠️ 连线失败：{conn}")

# 3. 保存
io = ghk.GH_DocumentIO(doc)
io.SaveQuiet(OUTPUT_GH)
print(f"✅ GH 文件已生成：{OUTPUT_GH}")
```

---

## 阶段 4：GH 内文件监听（可选）

在 GH canvas 上放一个 Python 组件，自动监听 `result.gh` 生成后弹出提示或自动导入：

```python
# 连接一个 Timer 组件（每2秒触发）触发此脚本
import os
import scriptcontext

WATCH_PATH = r"C:\Users\<你的用户名>\gh-ai-wiring\output\result.gh"
LAST_SEEN  = "gh_watcher_last_mtime"

if os.path.exists(WATCH_PATH):
    mtime = os.path.getmtime(WATCH_PATH)
    last  = scriptcontext.sticky.get(LAST_SEEN, 0)

    if mtime > last:
        scriptcontext.sticky[LAST_SEEN] = mtime
        # 触发导入逻辑（或在 Rhino 命令行提示）
        import Rhino
        Rhino.RhinoApp.WriteLine(f"✅ 新的 GH 文件已就绪：{WATCH_PATH}")
        # 可以进一步调用 GrasshopperDocument.MergeDocument() 自动合并
```

---

## 开发优先级

| 阶段 | 任务 | 依赖 | 工作量 |
|------|------|------|--------|
| 1 | 扫描脚本 + 生成 component_library.json | Rhino 环境 | 1h |
| 2 | CLAUDE.md + skills/gh-wiring.md | 阶段1 | 2h |
| 3 | 手动测试 /gh-wire 生成 wiring.json | 阶段2 | — |
| 4 | build_gh_file.py 写入 .gh | 阶段3 | 2h |
| 5 | Timer 监听自动刷新 | 阶段4 | 1h |

**先跑通阶段 1-3，验证 AI 能否正确规划连接拓扑，是最核心的假设验证。**

---

## 已知风险和对策

| 风险 | 描述 | 对策 |
|------|------|------|
| 端口语义歧义 | AI 可能接错端口（如把 Curve 接进 Number） | 扫描时记录端口数据类型，prompt 中明确约束 |
| 组件版本差异 | 不同 GH 版本 GUID 可能不同 | 每台机器独立扫描，JSON 随机器走 |
| 插件组件缺失 | 用户机器没装某个插件 | 扫描结果只包含已安装组件，AI 只能从中选 |
| 复杂拓扑出错 | 多分支、循环引用等 | 先限制在 DAG（有向无环图）场景，逐步扩展 |

---

## 下一步

1. 在 Rhino 里跑 `scan_gh_components.py`，看看能扫出多少组件
2. 把 JSON 片段发给我，我帮你写第一版 `/gh-wire` 的 system prompt
3. 测试一个简单场景：`Slider → Circle → Extrude`
