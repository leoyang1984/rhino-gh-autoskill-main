#!/usr/bin/env python3
"""Tests for conservative, snapshot-backed Grasshopper type diagnostics."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = (
    PROJECT_ROOT
    / "skills"
    / "grasshopper-recipe-modeling"
    / "scripts"
)
sys.path.insert(0, str(SKILL_SCRIPTS))

from graph_ir import GraphIR  # noqa: E402
from type_check import (  # noqa: E402
    ComponentCatalog,
    TypeRules,
    blocking_type_results,
    check_graph_types,
    summarize_types,
)


COMPILER = SKILL_SCRIPTS / "compile_recipe.py"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TypeCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = ComponentCatalog.load(PROJECT_ROOT)
        cls.rules = TypeRules.load(PROJECT_ROOT)

    def test_reviewed_status_classes(self) -> None:
        cases = {
            ("GH_Number", "GH_Number"): "EXACT",
            ("GH_Circle", "GH_Curve"): "KNOWN_CAST",
            ("GH_Number", "GH_Integer"): "WARN",
            ("GH_Number", "GH_Vector"): "INCOMPATIBLE",
            ("GH_Transform", "GH_Plane"): "UNKNOWN",
        }
        for pair, expected in cases.items():
            with self.subTest(pair=pair):
                self.assertEqual(expected, self.rules.classify(*pair)[0])

    def test_all_recipe_connections_receive_a_diagnostic(self) -> None:
        totals = {status: 0 for status in ("EXACT", "KNOWN_CAST", "WARN", "UNKNOWN", "INCOMPATIBLE")}
        connections = 0
        for path in sorted((PROJECT_ROOT / "recipes").glob("*/wiring.json")):
            graph = GraphIR.from_wiring(read_json(path))
            results = check_graph_types(graph, self.catalog, self.rules)
            self.assertEqual(len(graph.connections), len(results))
            summary = summarize_types(results)
            connections += len(results)
            for name, count in summary.items():
                totals[name] += count
        self.assertEqual(258, connections)
        self.assertEqual(0, totals["INCOMPATIBLE"])
        self.assertGreater(totals["WARN"], 0)
        self.assertGreater(totals["UNKNOWN"], 0)

    def test_known_bad_direct_wire_is_incompatible(self) -> None:
        wiring = read_json(PROJECT_ROOT / "tests" / "test_01_slider_circle_extrude.json")
        broken = deepcopy(wiring)
        broken["nodes"].append(
            {
                "id": "bad_move",
                "guid": "e9eb1dcf-92f6-4d4d-84ae-96222d60f56b",
                "name": "Move",
                "position": {"x": 700, "y": 0},
            }
        )
        broken["connections"].append(
            {
                "from": {"node": "n1", "port": "Value"},
                "to": {"node": "bad_move", "port": "Motion"},
            }
        )
        results = check_graph_types(GraphIR.from_wiring(broken), self.catalog, self.rules)
        self.assertEqual("INCOMPATIBLE", results[-1].status)
        self.assertEqual(results[-1:], blocking_type_results(results))

    def test_strict_mode_blocks_warn_and_unknown(self) -> None:
        graph = GraphIR.from_wiring(
            read_json(PROJECT_ROOT / "recipes" / "mass-rotate" / "wiring.json")
        )
        results = check_graph_types(graph, self.catalog, self.rules)
        self.assertEqual([], blocking_type_results(results, strict=False))
        self.assertTrue(blocking_type_results(results, strict=True))

    def test_compile_strict_types_is_opt_in(self) -> None:
        normal = subprocess.run(
            [sys.executable, str(COMPILER), "compile", "mass-rotate"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        strict = subprocess.run(
            [
                sys.executable,
                str(COMPILER),
                "compile",
                "mass-rotate",
                "--strict-types",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, normal.returncode, normal.stderr)
        self.assertEqual(2, strict.returncode)
        self.assertIn("type check WARN", strict.stderr)

    def test_markdown_generated_block_matches_json_source(self) -> None:
        generator_path = PROJECT_ROOT / "scripts" / "generate_type_guide.py"
        spec = importlib.util.spec_from_file_location("generate_type_guide", generator_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        rules = read_json(PROJECT_ROOT / "knowledge" / "type-compat.json")
        guide = (PROJECT_ROOT / "knowledge" / "geometry-type-guide.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(module.generated_block(rules), guide)

    def test_component_consumers_accept_legacy_and_snapshot_shapes(self) -> None:
        for name in ("build_component_index.py", "query_components.py"):
            source = (PROJECT_ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertIn('source.get("components", [])', source)


if __name__ == "__main__":
    unittest.main()
