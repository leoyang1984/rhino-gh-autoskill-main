#!/usr/bin/env python3
"""Static composition tests for every migrated public Recipe rule."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = (
    PROJECT_ROOT
    / "skills"
    / "grasshopper-recipe-modeling"
    / "scripts"
)
sys.path.insert(0, str(SKILL_SCRIPTS))

from composition import compose_recipe_pair  # noqa: E402
from graph_ir import GraphIR, validate_graph_structure  # noqa: E402
from type_check import (  # noqa: E402
    ComponentCatalog,
    TypeRules,
    blocking_type_results,
    check_graph_types,
)


COMPILER = SKILL_SCRIPTS / "compile_recipe.py"
PAIRS = [
    ("mass-rotate", "facade-grid"),
    ("mass-rotate", "facade-panel-flat"),
    ("mass-extrude", "facade-grid"),
    ("mass-extrude", "facade-panel-flat"),
    ("mass-taper", "facade-grid"),
    ("mass-setback", "facade-grid"),
    ("attractor-remap", "facade-panel-flat"),
    ("mass-podium-tower", "facade-louver"),
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = ComponentCatalog.load(PROJECT_ROOT)
        cls.rules = TypeRules.load(PROJECT_ROOT)

    def test_legacy_chain_fields_are_gone(self) -> None:
        migrated_rules = 0
        for path in sorted((PROJECT_ROOT / "recipes").glob("*/recipe.json")):
            recipe = read_json(path)
            migrated_rules += len(recipe["composition_rules"])
            with self.subTest(recipe=recipe["id"]):
                self.assertNotIn("chain_input", recipe)
                self.assertNotIn("chain_bridges", recipe)
        self.assertEqual(8, migrated_rules)

    def test_rules_reference_public_names_not_internal_node_ids(self) -> None:
        internal_id = re.compile(r"^n\d+$")
        recipes = {
            path.parent.name: read_json(path)
            for path in (PROJECT_ROOT / "recipes").glob("*/recipe.json")
        }
        for source_id, source in recipes.items():
            outputs = source["interface"]["outputs"]
            for rule in source["composition_rules"]:
                target = recipes[rule["target_recipe"]]
                for binding in rule["bindings"]:
                    with self.subTest(source=source_id, rule=rule["id"]):
                        self.assertIn(binding["from_output"], outputs)
                        self.assertFalse(internal_id.fullmatch(binding["from_output"]))
                        endpoint = binding["to"]
                        if "input" in endpoint:
                            self.assertIn(endpoint["input"], target["interface"]["inputs"])
                        else:
                            self.assertIn(
                                endpoint["parameter"], target["interface"]["parameters"]
                            )

    def test_every_migrated_rule_composes_without_structure_or_type_failure(self) -> None:
        self.assertEqual(8, len(PAIRS))
        for source, target in PAIRS:
            wiring = compose_recipe_pair(PROJECT_ROOT, source, target)
            graph = GraphIR.from_wiring(wiring)
            structure_errors = [
                issue
                for issue in validate_graph_structure(graph)
                if issue.severity == "error"
            ]
            type_results = check_graph_types(graph, self.catalog, self.rules)
            with self.subTest(source=source, target=target):
                self.assertEqual([], structure_errors)
                self.assertEqual([], blocking_type_results(type_results))
                self.assertEqual(len(graph.connections), len(type_results))
                self.assertEqual(len(graph.nodes), len({node.id for node in graph.nodes}))

    def test_surface_input_replacement_prunes_self_generated_prefix(self) -> None:
        wiring = compose_recipe_pair(PROJECT_ROOT, "mass-rotate", "facade-grid")
        ids = {node["id"] for node in wiring["nodes"]}
        for removed in ("n1", "n2", "n5", "n6"):
            self.assertNotIn(f"facade-grid__{removed}", ids)
        for retained in ("n3", "n4", "n7", "n8"):
            self.assertIn(f"facade-grid__{retained}", ids)

    def test_parameter_composition_removes_target_sliders(self) -> None:
        attractor = compose_recipe_pair(
            PROJECT_ROOT, "attractor-remap", "facade-panel-flat"
        )
        attractor_ids = {node["id"] for node in attractor["nodes"]}
        self.assertNotIn("facade-panel-flat__n5", attractor_ids)

        podium = compose_recipe_pair(
            PROJECT_ROOT, "mass-podium-tower", "facade-louver"
        )
        podium_ids = {node["id"] for node in podium["nodes"]}
        self.assertNotIn("facade-louver__n1", podium_ids)
        self.assertNotIn("facade-louver__n2", podium_ids)

    def test_compose_cli_emits_valid_mcp_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(COMPILER),
                "compose",
                "mass-rotate",
                "facade-grid",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["components"])
        self.assertTrue(payload["wires"])
        self.assertTrue(payload["solve"])


if __name__ == "__main__":
    unittest.main()
