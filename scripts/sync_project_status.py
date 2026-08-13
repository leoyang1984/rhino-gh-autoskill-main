#!/usr/bin/env python3
"""Synchronize generated Recipe index and bounded documentation status blocks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CLAUDE_START = "<!-- GENERATED:STATUS:START -->"
CLAUDE_END = "<!-- GENERATED:STATUS:END -->"
CHECKPOINT_START = "<!-- GENERATED:RECIPE-STATUS:START -->"
CHECKPOINT_END = "<!-- GENERATED:RECIPE-STATUS:END -->"


def find_root() -> Path:
    for start in (Path.cwd().resolve(), Path(__file__).resolve()):
        for candidate in (start, *start.parents):
            if (candidate / "recipes" / "index.json").is_file():
                return candidate
    raise RuntimeError("Could not locate project root")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def recipe_documents(root: Path) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "recipes").glob("*/recipe.json")):
        document = read_json(path)
        recipe_id = str(document.get("id", ""))
        if not recipe_id or recipe_id in documents:
            raise RuntimeError(f"Invalid or duplicate Recipe id in {path}")
        if path.parent.name != recipe_id:
            raise RuntimeError(f"Recipe id {recipe_id!r} does not match folder {path.parent.name!r}")
        documents[recipe_id] = document
    return documents


def generated_index(root: Path, documents: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    existing = read_json(root / "recipes" / "index.json")
    ordered = [str(item.get("id")) for item in existing if str(item.get("id")) in documents]
    ordered.extend(sorted(set(documents) - set(ordered)))
    return [
        {
            "id": recipe_id,
            "name": documents[recipe_id]["name"],
            "description": documents[recipe_id]["description"],
            "tags": documents[recipe_id].get("tags", []),
        }
        for recipe_id in ordered
    ]


def status_metrics(root: Path, documents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scripts = root / "skills" / "grasshopper-recipe-modeling" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from compile_recipe import validate_one

    total = len(documents)
    valid = sum(not validate_one(root, recipe_id) for recipe_id in documents)
    return {
        "total": total,
        "verified": sum(item.get("verified") is True for item in documents.values()),
        "v2": sum(item.get("schema_version") == 2 for item in documents.values()),
        "valid": valid,
        "public_inputs": sum(bool(item.get("interface", {}).get("inputs")) for item in documents.values()),
        "public_outputs": sum(len(item.get("interface", {}).get("outputs", {})) for item in documents.values()),
        "composition_rules": sum(len(item.get("composition_rules", [])) for item in documents.values()),
        "hot_components": len(read_json(root / "data" / "hot_components.json").get("components", [])),
        "full_snapshot": (root / "data" / "component_library.json").is_file(),
        "reference_snapshot": (root / "data" / "reference" / "component_snapshot.json").is_file(),
    }


def claude_block(metrics: dict[str, Any]) -> str:
    yes = lambda value: "✅ 有" if value else "⏳ 待采集"
    return "\n".join(
        [
            CLAUDE_START,
            "| 项目指标 | 当前状态 |",
            "|---|---|",
            f"| Recipe | {metrics['total']} 个；verified {metrics['verified']}/{metrics['total']}；schema v2 {metrics['v2']}/{metrics['total']} |",
            f"| 静态验证 | {metrics['valid']}/{metrics['total']} 通过 |",
            f"| 公共接口 | {metrics['public_inputs']} 个 Recipe 有外部输入；共 {metrics['public_outputs']} 个公共输出 |",
            f"| 公共组合规则 | {metrics['composition_rules']} 条 |",
            f"| 高频组件快照 | {metrics['hot_components']} 个组件 |",
            f"| 本机完整组件快照 | {yes(metrics['full_snapshot'])} |",
            f"| 已审查参考快照 | {yes(metrics['reference_snapshot'])} |",
            "| 编译与验证 | Graph IR、分级类型检查、compose、health、audit、admit |",
            "",
            "此区块由 `scripts/sync_project_status.py` 生成；不要手工编辑。",
            CLAUDE_END,
        ]
    )


def checkpoint_block(metrics: dict[str, Any]) -> str:
    return "\n".join(
        [
            CHECKPOINT_START,
            "| 指标 | 数量 |",
            "|---|---:|",
            f"| Recipe 总数 | {metrics['total']} |",
            f"| verified | {metrics['verified']}/{metrics['total']} |",
            f"| schema v2 | {metrics['v2']}/{metrics['total']} |",
            f"| 静态验证通过 | {metrics['valid']}/{metrics['total']} |",
            f"| 公共组合规则 | {metrics['composition_rules']} |",
            "",
            "此区块由 `scripts/sync_project_status.py` 生成；产品队列和下一步仍由人工维护。",
            CHECKPOINT_END,
        ]
    )


def replace_block(text: str, start: str, end: str, block: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise RuntimeError(f"Missing generated marker block: {start}")
    return pattern.sub(block, text, count=1)


def expected_files(root: Path) -> dict[Path, str]:
    documents = recipe_documents(root)
    metrics = status_metrics(root, documents)
    index_text = json.dumps(generated_index(root, documents), ensure_ascii=False, indent=2) + "\n"
    claude_path = root / "CLAUDE.md"
    checkpoint_path = root / "planning" / "checkpoint.md"
    return {
        root / "recipes" / "index.json": index_text,
        claude_path: replace_block(claude_path.read_text(encoding="utf-8"), CLAUDE_START, CLAUDE_END, claude_block(metrics)),
        checkpoint_path: replace_block(checkpoint_path.read_text(encoding="utf-8"), CHECKPOINT_START, CHECKPOINT_END, checkpoint_block(metrics)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated files are stale")
    args = parser.parse_args()
    root = find_root()
    stale: list[Path] = []
    for path, expected in expected_files(root).items():
        if path.read_text(encoding="utf-8") == expected:
            continue
        stale.append(path)
        if not args.check:
            path.write_text(expected, encoding="utf-8")
    if stale:
        verb = "stale" if args.check else "updated"
        for path in stale:
            print(f"{verb}: {path.relative_to(root)}")
    return 1 if args.check and stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
