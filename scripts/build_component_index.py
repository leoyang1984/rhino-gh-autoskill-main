"""
把 component_library.json 压缩成 AI 可用的索引格式。
在普通 Python 环境运行（不需要 GH 运行时）。

输出：data/component_index.json
格式：按 category 分组，每个组件只保留 AI 选组件所需的字段。
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "component_library.json"
OUTPUT = ROOT / "data" / "component_index.json"

with open(INPUT, encoding="utf-8") as f:
    source = json.load(f)
comps = source.get("components", []) if isinstance(source, dict) else source

def simplify_type(t):
    """把 Grasshopper.Kernel.Types.GH_Number 简化为 Number"""
    if not t or t == "unknown":
        return "any"
    t = t.split(".")[-1]
    prefixes = ["GH_", "IGH_"]
    for p in prefixes:
        if t.startswith(p):
            t = t[len(p):]
    return t

index = defaultdict(list)

for c in comps:
    entry = {
        "name": c["name"],
        "guid": c["guid"],
        "sub": c.get("subcategory", ""),
        "desc": c.get("description", "")[:80],  # 截断过长描述
    }

    if c["inputs"]:
        entry["in"] = [
            {
                "n": p["name"],
                "t": simplify_type(p.get("type", "")),
                "a": p.get("access", "unknown")
            }
            for p in c["inputs"]
        ]

    if c["outputs"]:
        entry["out"] = [
            {
                "n": p["name"],
                "t": simplify_type(p.get("type", "")),
                "a": p.get("access", "unknown")
            }
            for p in c["outputs"]
        ]

    index[c["category"]].append(entry)

# 按 category 字母排序，category 内按 name 排序
result = {}
for cat in sorted(index.keys()):
    result[cat] = sorted(index[cat], key=lambda x: x["name"])

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

total = sum(len(v) for v in result.values())
print(f"✅ 索引生成完成：{total} 个组件，{len(result)} 个分类 → {OUTPUT}")

size_kb = len(json.dumps(result, ensure_ascii=False)) / 1024
print(f"   文件大小：{size_kb:.1f} KB")
