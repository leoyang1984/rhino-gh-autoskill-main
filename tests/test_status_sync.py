#!/usr/bin/env python3
"""Tests for generated Recipe index and bounded status documentation."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = PROJECT_ROOT / "scripts" / "sync_project_status.py"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_project_status", SYNC_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StatusSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sync = load_sync_module()

    def test_all_generated_files_are_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SYNC_SCRIPT), "--check"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_index_is_derived_from_recipe_documents(self) -> None:
        documents = self.sync.recipe_documents(PROJECT_ROOT)
        expected = self.sync.generated_index(PROJECT_ROOT, documents)
        actual = self.sync.read_json(PROJECT_ROOT / "recipes" / "index.json")
        self.assertEqual(expected, actual)
        self.assertEqual(18, len(actual))

    def test_marker_replacement_preserves_manual_text(self) -> None:
        original = "manual before\n<!-- S -->old<!-- E -->\nmanual after\n"
        updated = self.sync.replace_block(original, "<!-- S -->", "<!-- E -->", "<!-- S -->new<!-- E -->")
        self.assertTrue(updated.startswith("manual before\n"))
        self.assertTrue(updated.endswith("\nmanual after\n"))
        self.assertIn("new", updated)

    def test_active_contract_docs_do_not_teach_legacy_composition_fields(self) -> None:
        for path in (
            PROJECT_ROOT / "CLAUDE.md",
            PROJECT_ROOT / "knowledge" / "composition-patterns.md",
            PROJECT_ROOT / "skills" / "grasshopper-recipe-modeling" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("chain_bridges", text)
                self.assertNotIn("chain_input", text)


if __name__ == "__main__":
    unittest.main()
