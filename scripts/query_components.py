"""
query_components.py — 从 component_library.json 精确查询组件信息

用法：
    python scripts/query_components.py "Rectangle" "Extrude" "Series"

输出：
    匹配组件的紧凑 JSON（name, guid, inputs, outputs），供 gh-wire 直接使用。
    匹配规则：组件 name 包含任意一个查询词（不区分大小写）。
"""

import json
import sys
from pathlib import Path

def query(terms):
    lib_path = Path(__file__).parent.parent / "data" / "component_library.json"
    with open(lib_path, encoding="utf-8") as f:
        source = json.load(f)
    library = source.get("components", []) if isinstance(source, dict) else source

    terms_lower = [t.lower() for t in terms]
    results = []
    seen = set()

    for comp in library:
        name = comp.get("name", "")
        if name in seen:
            continue
        if any(t in name.lower() for t in terms_lower):
            seen.add(name)
            results.append({
                "name": name,
                "guid": comp.get("guid", ""),
                "inputs":  [p["name"] for p in comp.get("inputs",  [])],
                "outputs": [p["name"] for p in comp.get("outputs", [])]
            })

    return results

if __name__ == "__main__":
    terms = sys.argv[1:]
    if not terms:
        print("用法: python query_components.py <组件名1> <组件名2> ...")
        sys.exit(1)
    print(json.dumps(query(terms), ensure_ascii=False, indent=2))
