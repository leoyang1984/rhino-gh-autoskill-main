import Grasshopper
import json
import os
from datetime import datetime, timezone

try:
    import Rhino
except ImportError:
    Rhino = None


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

def scan_components():
    server = Grasshopper.Instances.ComponentServer
    components = []

    for proxy in server.ObjectProxies:
        try:
            # 跳过过时/隐藏组件
            if proxy.Obsolete or getattr(proxy, 'Hidden', False):
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
                "outputs": [],
                "assembly": {}
            }

            try:
                assembly = obj.GetType().Assembly
                comp_data["assembly"] = {
                    "name": str(assembly.GetName().Name),
                    "version": str(assembly.GetName().Version),
                    "location": str(assembly.Location or "")
                }
            except Exception:
                pass

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
                        "type": str(p.Type) if hasattr(p, "Type") else "unknown",
                        "access": str(p.Access)
                    })

            components.append(comp_data)

        except Exception as e:
            # 跳过无法实例化的组件
            continue

    return components


def build_snapshot(components):
    assemblies = {}
    for component in components:
        assembly = component.get("assembly") or {}
        name = assembly.get("name")
        if name:
            assemblies[name] = assembly

    try:
        gh_assembly = Grasshopper.Instances.ComponentServer.GetType().Assembly
        gh_version = str(gh_assembly.GetName().Version)
    except Exception:
        gh_version = "unknown"
    try:
        rhino_version = str(Rhino.RhinoApp.Version) if Rhino is not None else "unknown"
    except Exception:
        rhino_version = "unknown"

    return {
        "snapshot_version": 2,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "full_component_server",
        "environment": {
            "rhino_version": rhino_version,
            "grasshopper_version": gh_version,
            "assemblies": sorted(assemblies.values(), key=lambda item: item["name"])
        },
        "components": components
    }


# 可用 GH Python 文本输入 output_path 覆盖默认输出位置。
PROJECT_ROOT = find_project_root()
OUTPUT_PATH = str(
    globals().get("output_path")
    or os.path.join(PROJECT_ROOT, "data", "component_library.json")
)

components = scan_components()
snapshot = build_snapshot(components)

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2)

print(f"✅ 扫描完成：{len(components)} 个组件 → {OUTPUT_PATH}")
