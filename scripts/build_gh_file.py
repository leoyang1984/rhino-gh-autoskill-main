import Grasshopper
import Grasshopper.Kernel as ghk
import System
import System.Drawing as sd
import json
import os


def find_project_root():
    """Resolve the project without binding this GH script to one workstation."""
    explicit = (
        globals().get("project_root")
        or os.environ.get("GH_AI_WIRING_ROOT")
    )
    starts = []
    if explicit:
        starts.append(os.path.abspath(os.path.expanduser(str(explicit))))
    if "__file__" in globals():
        starts.append(os.path.dirname(os.path.abspath(__file__)))
    starts.append(os.getcwd())

    for start in starts:
        candidate = start
        while True:
            if os.path.isfile(os.path.join(candidate, "recipes", "index.json")):
                return candidate
            parent = os.path.dirname(candidate)
            if parent == candidate:
                break
            candidate = parent
    raise RuntimeError(
        "找不到项目根目录。请给 GH Python 组件增加 project_root 文本输入，"
        "或设置 GH_AI_WIRING_ROOT。"
    )


PROJECT_ROOT = find_project_root()
WIRING_PATH = str(
    globals().get("wiring_path")
    or os.path.join(PROJECT_ROOT, "output", "wiring.json")
)
OUTPUT_GH = str(
    globals().get("output_gh")
    or os.path.join(PROJECT_ROOT, "output", "result.gh")
)

with open(WIRING_PATH, "r", encoding="utf-8") as f:
    wiring = json.load(f)

doc = ghk.GH_Document()
node_map = {}  # id → IGH_Component 实例

# 建立 GUID → proxy 索引
server = Grasshopper.Instances.ComponentServer
proxy_index = {}
for proxy in server.ObjectProxies:
    proxy_index[str(proxy.Guid).lower()] = proxy

# 1. 放置组件
for node in wiring["nodes"]:
    guid_str = node["guid"].lower()
    proxy = proxy_index.get(guid_str)
    if proxy is None:
        print(f"⚠️ 找不到组件：{node['name']} ({node['guid']})")
        continue

    obj = proxy.CreateInstance()
    obj.CreateAttributes()
    obj.Attributes.Pivot = sd.PointF(node["position"]["x"], node["position"]["y"])

    # 先加入文档，再写入预设值（AddObject 可能重置状态）
    doc.AddObject(obj, False)
    node_map[node["id"]] = obj

    # 写入自定义 nickname
    if "nickname" in node and node["nickname"]:
        obj.NickName = node["nickname"]

    # 写入 Slider 预设值（min / max / value）
    preset = node.get("preset")
    if preset and hasattr(obj, "Slider"):
        slider = obj.Slider
        if "min" in preset:
            slider.Minimum = System.Decimal(preset["min"])
        if "max" in preset:
            slider.Maximum = System.Decimal(preset["max"])
        if "value" in preset:
            slider.Value = System.Decimal(preset["value"])

# 2. 连线
for conn in wiring["connections"]:
    from_node = node_map.get(conn["from"]["node"])
    to_node   = node_map.get(conn["to"]["node"])
    if from_node is None or to_node is None:
        continue

    from_port_name = conn["from"]["port"]
    to_port_name   = conn["to"]["port"]

    # 找输出端口：IGH_Param（如 Slider）本身就是输出；IGH_Component 从 Params.Output 找
    if isinstance(from_node, ghk.IGH_Param):
        src_param = from_node
    else:
        src_param = next((p for p in from_node.Params.Output if p.Name == from_port_name), None)

    # 找输入端口：IGH_Param 本身就是输入；IGH_Component 从 Params.Input 找
    if isinstance(to_node, ghk.IGH_Param):
        tgt_param = to_node
    else:
        tgt_param = next((p for p in to_node.Params.Input if p.Name == to_port_name), None)

    if src_param and tgt_param:
        tgt_param.AddSource(src_param)
        
        # 处理 Flatten / Graft 数据映射
        meta = conn.get("meta")
        if meta:
            if meta.get("flatten"):
                tgt_param.DataMapping = ghk.GH_DataMapping.Flatten
            elif meta.get("graft"):
                tgt_param.DataMapping = ghk.GH_DataMapping.Graft
    else:
        print(f"⚠️ 连线失败：{conn}")

# 3. 保存
io = ghk.GH_DocumentIO(doc)
io.SaveQuiet(OUTPUT_GH)
print(f"✅ GH 文件已生成：{OUTPUT_GH}")
