#!/usr/bin/env python3
"""Characterization tests for the legacy Recipe compiler.

These tests deliberately freeze the current compiler output before schema and
compiler refactors. Refreshing snapshots is an explicit operation:

    python3 tests/test_compile_recipe.py --update-baselines
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPILER_PATH = (
    PROJECT_ROOT
    / "skills"
    / "grasshopper-recipe-modeling"
    / "scripts"
    / "compile_recipe.py"
)
BASELINE_PATH = PROJECT_ROOT / "tests" / "baselines" / "recipe_payloads.json"


def load_compiler() -> ModuleType:
    spec = importlib.util.spec_from_file_location("compile_recipe", COMPILER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import compiler from {COMPILER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPILER = load_compiler()


def recipe_ids() -> list[str]:
    return [str(entry["id"]) for entry in COMPILER.load_index(PROJECT_ROOT)]


def compile_default(recipe_id: str) -> dict[str, Any]:
    recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, recipe_id)
    return COMPILER.compile_payload(recipe, wiring, {})


def build_baseline() -> dict[str, Any]:
    recipes: dict[str, Any] = {}
    for recipe_id in recipe_ids():
        recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, recipe_id)
        payload = COMPILER.compile_payload(recipe, wiring, {})
        recipes[recipe_id] = {
            "default_parameters": {
                name: spec.get("default")
                for name, spec in COMPILER.public_parameters(recipe).items()
            },
            "counts": {
                "sliders": len(payload["sliders"]),
                "components": len(payload["components"]),
                "wires": len(payload["wires"]),
            },
            "payload": payload,
        }
    return {
        "format_version": 1,
        "purpose": "Legacy compile_recipe.py characterization baseline",
        "recipes": recipes,
    }


def write_baseline() -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(build_baseline(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class RecipeCompilerCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    def test_index_and_recipe_files_are_in_one_to_one_correspondence(self) -> None:
        indexed = recipe_ids()
        folders = sorted(
            path.parent.name
            for path in (PROJECT_ROOT / "recipes").glob("*/recipe.json")
        )
        self.assertEqual(len(indexed), len(set(indexed)), "duplicate ids in index")
        self.assertEqual(sorted(indexed), folders)
        self.assertEqual(18, len(indexed))

    def test_all_recipes_match_frozen_payloads(self) -> None:
        actual = build_baseline()
        self.assertEqual(self.baseline, actual)

    def test_all_recipes_pass_current_validator(self) -> None:
        errors = {
            recipe_id: COMPILER.validate_one(PROJECT_ROOT, recipe_id)
            for recipe_id in recipe_ids()
        }
        self.assertEqual({}, {key: value for key, value in errors.items() if value})

    def test_numeric_parameter_overrides_reach_their_sliders(self) -> None:
        for recipe_id in recipe_ids():
            recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, recipe_id)
            parameters = recipe.get("parameters", {})
            if not parameters:
                continue
            name, spec = next(iter(parameters.items()))
            node = next(item for item in wiring["nodes"] if item["id"] == spec["node"])
            preset = node["preset"]
            override = preset["min"]
            if override == spec.get("default"):
                override = preset["max"]
            payload = COMPILER.compile_payload(recipe, wiring, {name: override})
            slider = next(item for item in payload["sliders"] if item["Key"] == spec["node"])
            with self.subTest(recipe=recipe_id, parameter=name):
                self.assertEqual(override, slider["Value"])

    def test_unknown_parameter_is_rejected(self) -> None:
        recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        with self.assertRaisesRegex(COMPILER.RecipeError, "Unknown parameter"):
            COMPILER.compile_payload(recipe, wiring, {"does_not_exist": 1})

    def test_slider_override_outside_range_is_rejected(self) -> None:
        recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        with self.assertRaisesRegex(COMPILER.RecipeError, "outside"):
            COMPILER.compile_payload(recipe, wiring, {"floors": 10_000})

    def test_non_integer_override_for_integer_slider_is_rejected(self) -> None:
        recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        with self.assertRaisesRegex(COMPILER.RecipeError, "non-integer"):
            COMPILER.compile_payload(recipe, wiring, {"floors": 3.5})

    def test_duplicate_node_id_is_rejected(self) -> None:
        recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        broken = deepcopy(wiring)
        broken["nodes"].append(deepcopy(broken["nodes"][0]))
        with self.assertRaisesRegex(COMPILER.RecipeError, "unique non-empty id"):
            COMPILER.compile_payload(recipe, broken, {})

    def test_missing_connection_node_is_rejected(self) -> None:
        recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        broken = deepcopy(wiring)
        broken["connections"][0]["from"]["node"] = "missing-node"
        with self.assertRaisesRegex(COMPILER.RecipeError, "missing node"):
            COMPILER.compile_payload(recipe, broken, {})

    def test_invalid_guid_is_reported_by_validator(self) -> None:
        recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        broken = deepcopy(wiring)
        broken["nodes"][0]["guid"] = "not-a-guid"

        original_load_recipe = COMPILER.load_recipe
        try:
            COMPILER.load_recipe = lambda root, recipe_id: (recipe, broken)
            errors = COMPILER.validate_one(PROJECT_ROOT, "mass-rotate")
        finally:
            COMPILER.load_recipe = original_load_recipe

        self.assertTrue(any("invalid guid" in error for error in errors), errors)

    def test_unversioned_recipes_are_treated_as_v1(self) -> None:
        recipe_v2, _ = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        legacy = deepcopy(recipe_v2)
        legacy["parameters"] = legacy.pop("interface")["parameters"]
        legacy.pop("$schema")
        legacy.pop("schema_version")
        legacy.pop("composition_rules")
        self.assertEqual(1, COMPILER.schema_version(legacy))
        self.assertEqual(
            legacy["parameters"], COMPILER.public_parameters(legacy)
        )

    def test_v2_json_schema_is_machine_readable(self) -> None:
        schema = json.loads(
            (PROJECT_ROOT / "schemas" / "recipe-v2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(2, schema["properties"]["schema_version"]["const"])
        self.assertIn("interface", schema["required"])
        self.assertIn("composition_rules", schema["required"])

    def test_migration_preview_is_non_destructive_for_current_v2_recipe(self) -> None:
        recipe_path = PROJECT_ROOT / "recipes" / "mass-rotate" / "recipe.json"
        before = recipe_path.read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                str(COMPILER_PATH),
                "migrate",
                "mass-rotate",
                "--dry-run",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        preview = json.loads(result.stdout)
        self.assertEqual(2, preview["source_version"])
        self.assertEqual(2, preview["target_version"])
        self.assertTrue(preview["ready"])
        self.assertEqual(2, preview["draft"]["schema_version"])
        self.assertIn("profile_curves", preview["draft"]["interface"]["outputs"])
        self.assertEqual(before, recipe_path.read_bytes())

    def test_legacy_migration_preview_remains_available(self) -> None:
        recipe_v2, wiring = COMPILER.load_recipe(PROJECT_ROOT, "facade-grid")
        legacy = deepcopy(recipe_v2)
        interface = legacy.pop("interface")
        legacy["parameters"] = interface["parameters"]
        legacy.pop("$schema")
        legacy.pop("schema_version")
        legacy.pop("composition_rules")
        legacy["chain_input"] = "GH_Surface"
        preview = COMPILER.migration_preview(legacy, wiring)
        self.assertEqual(1, preview["source_version"])
        self.assertEqual(2, preview["target_version"])
        self.assertFalse(preview["ready"])
        self.assertIn("external_input", preview["draft"]["interface"]["inputs"])

    def test_migration_without_dry_run_is_rejected(self) -> None:
        result = subprocess.run(
            [sys.executable, str(COMPILER_PATH), "migrate", "mass-rotate"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("preview-only", result.stderr)

    def test_v2_recipe_uses_interface_parameters(self) -> None:
        legacy_recipe, wiring = COMPILER.load_recipe(PROJECT_ROOT, "mass-rotate")
        preview = COMPILER.migration_preview(legacy_recipe, wiring)
        recipe_v2 = preview["draft"]
        payload = COMPILER.compile_payload(recipe_v2, wiring, {"floors": 12})
        floors = next(slider for slider in payload["sliders"] if slider["Key"] == "n1")
        self.assertEqual(12, floors["Value"])


def main() -> int:
    if "--update-baselines" in sys.argv:
        sys.argv.remove("--update-baselines")
        write_baseline()
        print(f"Updated {BASELINE_PATH.relative_to(PROJECT_ROOT)}")
        if not sys.argv[1:]:
            return 0
    unittest.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
