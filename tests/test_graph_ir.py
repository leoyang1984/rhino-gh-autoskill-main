#!/usr/bin/env python3
"""Tests for the shared Graph IR and both serialization backends."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    PROJECT_ROOT
    / "skills"
    / "grasshopper-recipe-modeling"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))

from graph_ir import (  # noqa: E402
    GraphIR,
    emit_legacy_wiring,
    validate_graph_structure,
)
from recipe_schema import public_parameters  # noqa: E402


COMPILER = SCRIPTS / "compile_recipe.py"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class GraphIRTests(unittest.TestCase):
    def test_all_recipe_wirings_round_trip_without_loss(self) -> None:
        paths = sorted((PROJECT_ROOT / "recipes").glob("*/wiring.json"))
        self.assertEqual(18, len(paths))
        for path in paths:
            wiring = read_json(path)
            with self.subTest(recipe=path.parent.name):
                self.assertEqual(wiring, GraphIR.from_wiring(wiring).to_wiring())

    def test_all_standalone_wiring_fixtures_pass_structure_validation(self) -> None:
        paths = sorted((PROJECT_ROOT / "tests").glob("test_[0-9][0-9]_*.json"))
        self.assertEqual(4, len(paths))
        for path in paths:
            issues = validate_graph_structure(GraphIR.from_wiring(read_json(path)))
            with self.subTest(path=path.name):
                self.assertEqual([], [item for item in issues if item.severity == "error"])

    def test_legacy_emitter_preserves_default_recipe_wiring(self) -> None:
        for recipe_path in sorted((PROJECT_ROOT / "recipes").glob("*/recipe.json")):
            recipe = read_json(recipe_path)
            wiring = read_json(recipe_path.with_name("wiring.json"))
            emitted = emit_legacy_wiring(
                GraphIR.from_wiring(wiring), public_parameters(recipe), {}
            )
            with self.subTest(recipe=recipe["id"]):
                self.assertEqual(wiring, emitted)

    def test_legacy_emitter_applies_override_and_offset_without_mutating_source(self) -> None:
        recipe = read_json(PROJECT_ROOT / "recipes" / "mass-rotate" / "recipe.json")
        wiring = read_json(PROJECT_ROOT / "recipes" / "mass-rotate" / "wiring.json")
        before = deepcopy(wiring)
        emitted = emit_legacy_wiring(
            GraphIR.from_wiring(wiring),
            public_parameters(recipe),
            {"floors": 12},
            x_offset=100,
            y_offset=-50,
        )
        slider = next(node for node in emitted["nodes"] if node["id"] == "n1")
        self.assertEqual(12, slider["preset"]["value"])
        self.assertEqual(before["nodes"][0]["position"]["x"] + 100, slider["position"]["x"])
        self.assertEqual(before["nodes"][0]["position"]["y"] - 50, slider["position"]["y"])
        self.assertEqual(before, wiring)

    def test_missing_node_and_duplicate_wire_have_separate_severities(self) -> None:
        wiring = read_json(PROJECT_ROOT / "tests" / "test_01_slider_circle_extrude.json")
        broken = deepcopy(wiring)
        broken["connections"].append(deepcopy(broken["connections"][0]))
        broken["connections"][1]["to"]["node"] = "missing"
        issues = validate_graph_structure(GraphIR.from_wiring(broken))
        by_code = {issue.code: issue.severity for issue in issues}
        self.assertEqual("error", by_code["connection_node_missing"])
        self.assertEqual("warning", by_code["connection_duplicate"])

    def test_validate_wiring_cli_accepts_standalone_graph(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(COMPILER),
                "validate-wiring",
                "tests/test_01_slider_circle_extrude.json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("errors=0, warnings=0", result.stdout)

    def test_legacy_gh_scripts_no_longer_contain_old_absolute_path(self) -> None:
        for name in ("build_gh_file.py", "scan_gh_components.py"):
            source = (PROJECT_ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertNotIn("/Users/<username>/", source)
                self.assertIn("GH_AI_WIRING_ROOT", source)


if __name__ == "__main__":
    unittest.main()
