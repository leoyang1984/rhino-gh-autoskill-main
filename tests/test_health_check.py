#!/usr/bin/env python3
"""Tests for saved-snapshot Grasshopper environment health validation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = PROJECT_ROOT / "skills" / "grasshopper-recipe-modeling" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from health_check import validate_environment  # noqa: E402


COMPILER = SKILL_SCRIPTS / "compile_recipe.py"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def complete_snapshot() -> dict:
    snapshot = deepcopy(read_json(PROJECT_ROOT / "data" / "hot_components.json"))
    snapshot.update(
        {
            "snapshot_version": 2,
            "captured_at": "2026-08-13T00:00:00+00:00",
            "scope": "full_component_server",
            "environment": {
                "rhino_version": "8.0-test",
                "grasshopper_version": "1.0-test",
                "assemblies": [],
            },
        }
    )
    return snapshot


class HealthCheckTests(unittest.TestCase):
    def test_complete_saved_snapshot_validates_offline(self) -> None:
        report = validate_environment(PROJECT_ROOT, complete_snapshot(), ["mass-rotate"])
        self.assertEqual({"ERROR": 0, "WARN": 0, "INFO": 0}, report["summary"])
        self.assertEqual(1, len(report["recipes"]))

    def test_missing_component_and_port_are_hard_failures(self) -> None:
        snapshot = complete_snapshot()
        snapshot["components"] = [
            component
            for component in snapshot["components"]
            if component["name"] != "Ellipse"
        ]
        extrude = next(c for c in snapshot["components"] if c["name"] == "Extrude")
        extrude["outputs"] = []
        report = validate_environment(PROJECT_ROOT, snapshot, ["mass-rotate"])
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("MISSING_COMPONENT", codes)
        self.assertIn("MISSING_PORT", codes)
        self.assertGreater(report["summary"]["ERROR"], 0)

    def test_baseline_environment_and_port_drift_are_warnings(self) -> None:
        baseline = complete_snapshot()
        current = deepcopy(baseline)
        current["environment"]["rhino_version"] = "8.1-test"
        ellipse = next(c for c in current["components"] if c["name"] == "Ellipse")
        ellipse["outputs"][0]["type"] = "GH_Geometry"
        report = validate_environment(
            PROJECT_ROOT, current, ["mass-rotate"], baseline=baseline
        )
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("ENVIRONMENT_DRIFT", codes)
        self.assertIn("PORT_TYPE_DRIFT", codes)
        self.assertEqual(0, report["summary"]["ERROR"])

    def test_health_cli_can_print_without_writing_machine_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot_path = Path(directory) / "snapshot.json"
            snapshot_path.write_text(
                json.dumps(complete_snapshot(), ensure_ascii=False), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(COMPILER),
                    "health",
                    "--snapshot",
                    str(snapshot_path),
                    "--recipe",
                    "mass-rotate",
                    "--no-write",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(0, report["summary"]["ERROR"])
        self.assertNotIn("report_path", report)

    def test_collector_and_offline_validator_remain_separate(self) -> None:
        compiler_source = COMPILER.read_text(encoding="utf-8")
        collector_source = (PROJECT_ROOT / "scripts" / "scan_gh_components.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import Grasshopper", compiler_source)
        self.assertIn('"scope": "full_component_server"', collector_source)


if __name__ == "__main__":
    unittest.main()
