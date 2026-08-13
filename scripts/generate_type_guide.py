#!/usr/bin/env python3
"""Generate the compatibility tables in geometry-type-guide.md from JSON."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "knowledge" / "type-compat.json"
GUIDE_PATH = ROOT / "knowledge" / "geometry-type-guide.md"
START = "<!-- GENERATED:TYPE_COMPAT:START -->"
END = "<!-- GENERATED:TYPE_COMPAT:END -->"


def table(rows: list[list[str]]) -> str:
    header = rows[0]
    result = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    result.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return "\n".join(result)


def generated_block(data: dict) -> str:
    lines = [START, "", "> 本区块由 `knowledge/type-compat.json` 生成，请勿手工修改。", ""]
    lines.extend(["## 诊断等级", ""])
    status_rows = [["等级", "含义"]]
    status_rows.extend([[name, text] for name, text in data["statuses"].items()])
    lines.extend([table(status_rows), "", "## 已审核的非同类型直连规则", ""])
    rule_rows = [["输出类型", "输入类型", "结论", "说明"]]
    for rule in data.get("rules", []):
        note = str(rule.get("reason", ""))
        if rule.get("adapter"):
            note += f" 建议适配器：{rule['adapter']}。"
        rule_rows.append([f"`{rule['from']}`", f"`{rule['to']}`", rule["status"], note])
    lines.extend([table(rule_rows), "", END])
    return "\n".join(lines)


def main() -> int:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    source = GUIDE_PATH.read_text(encoding="utf-8")
    block = generated_block(data)
    if START in source and END in source:
        prefix, rest = source.split(START, 1)
        _, suffix = rest.split(END, 1)
        result = prefix.rstrip() + "\n\n" + block + suffix
    else:
        marker = "---\n"
        position = source.find(marker)
        if position < 0:
            result = block + "\n\n" + source
        else:
            position += len(marker)
            result = source[:position] + "\n" + block + "\n\n" + source[position:]
    GUIDE_PATH.write_text(result.rstrip() + "\n", encoding="utf-8")
    print(f"Updated {GUIDE_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
