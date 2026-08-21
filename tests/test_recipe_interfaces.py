#!/usr/bin/env python3
"""Contract tests for the 17 Recipe v2 public interfaces."""

from __future__ import annotations

import json
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

from recipe_schema import validate_recipe_contract  # noqa: E402
from type_check import ComponentCatalog  # noqa: E402


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class RecipeInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = ComponentCatalog.load(PROJECT_ROOT)
        cls.recipe_paths = sorted((PROJECT_ROOT / "recipes").glob("*/recipe.json"))

    def test_all_recipes_are_schema_v2_with_public_outputs(self) -> None:
        self.assertEqual(18, len(self.recipe_paths))
        for path in self.recipe_paths:
            recipe = read_json(path)
            with self.subTest(recipe=recipe["id"]):
                self.assertEqual(2, recipe["schema_version"])
                self.assertNotIn("parameters", recipe)
                self.assertTrue(recipe["interface"]["outputs"])

    def test_every_v2_contract_passes_runtime_validation(self) -> None:
        for path in self.recipe_paths:
            recipe = read_json(path)
            wiring = read_json(path.with_name("wiring.json"))
            with self.subTest(recipe=recipe["id"]):
                self.assertEqual([], validate_recipe_contract(recipe, wiring))

    def test_public_input_replace_bindings_target_existing_internal_wires(self) -> None:
        input_recipes = 0
        for path in self.recipe_paths:
            recipe = read_json(path)
            wiring = read_json(path.with_name("wiring.json"))
            targets = {
                (wire["to"]["node"], wire["to"]["port"])
                for wire in wiring["connections"]
            }
            inputs = recipe["interface"]["inputs"]
            input_recipes += bool(inputs)
            for input_name, spec in inputs.items():
                for binding in spec["bindings"]:
                    with self.subTest(recipe=recipe["id"], input=input_name, binding=binding):
                        self.assertEqual("replace", binding["mode"])
                        self.assertIn((binding["node"], binding["port"]), targets)
        self.assertEqual(6, input_recipes)

    def test_public_output_ports_exist_when_component_is_in_snapshot(self) -> None:
        checked = 0
        unknown_components = 0
        total_outputs = 0
        for path in self.recipe_paths:
            recipe = read_json(path)
            wiring = read_json(path.with_name("wiring.json"))
            nodes = {node["id"]: node for node in wiring["nodes"]}
            for output_name, output in recipe["interface"]["outputs"].items():
                total_outputs += 1
                node = nodes[output["node"]]
                component = self.catalog.by_guid.get(node["guid"].lower())
                if component is None:
                    unknown_components += 1
                    continue
                ports = {port["name"] for port in component.get("outputs", [])}
                checked += 1
                with self.subTest(recipe=recipe["id"], output=output_name):
                    self.assertIn(output["port"], ports)
        self.assertEqual(total_outputs, checked + unknown_components)
        self.assertGreater(checked, unknown_components)
        self.assertGreater(unknown_components, 0)

    def test_v2_schema_no_longer_accepts_legacy_chain_metadata(self) -> None:
        schema = read_json(PROJECT_ROOT / "schemas" / "recipe-v2.schema.json")
        for key in ("chain_input", "chain_bridges"):
            self.assertNotIn(key, schema["properties"])


if __name__ == "__main__":
    unittest.main()
