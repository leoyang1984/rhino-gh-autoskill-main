#!/usr/bin/env python3
"""Tests for dynamic evidence audit and Recipe admission checks."""

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

from audit import admission_check, evaluate_audit  # noqa: E402


COMPILER = SKILL_SCRIPTS / "compile_recipe.py"


def passing_evidence(visual_status: str = "pending") -> dict:
    return {
        "evidence_version": 1,
        "subject": {"kind": "recipe", "id": "mass-rotate"},
        "captured_at": "2026-08-13T00:00:00+00:00",
        "apply": {
            "requested": {"components": 5, "sliders": 5, "wires": 15},
            "result": {
                "place_errors": [],
                "wires_ok": 15,
                "wire_results": [{"ok": True} for _ in range(15)],
            },
        },
        "solve": {"ok": True},
        "canvas": {
            "object_count": 10,
            "wire_count": 15,
            "objects": [
                {
                    "id": "n16",
                    "name": "Extrude",
                    "messages": [],
                    "outputs": {"Extrusion": {"branches": 1, "items": 20}},
                }
            ],
        },
        "metrics": {"floor_items": 20, "profile_items": 20},
        "assertions": [
            {
                "id": "floor_output",
                "kind": "nonzero",
                "paths": ["metrics.floor_items"],
                "description": "Floor output must contain geometry.",
            },
            {
                "id": "paired_lengths",
                "kind": "lengths_equal",
                "paths": ["metrics.floor_items", "metrics.profile_items"],
            },
        ],
        "visual_review": {"status": visual_status},
        "raw": {"apply": {}, "solve": {}, "canvas": {}},
    }


class DynamicAuditTests(unittest.TestCase):
    def test_structural_pass_does_not_imply_visual_approval(self) -> None:
        report = evaluate_audit(passing_evidence())
        self.assertTrue(report["structural_pass"])
        self.assertFalse(report["admission_ready"])
        self.assertEqual("pending", report["visual_review"]["status"])

    def test_apply_wire_solve_canvas_and_assertion_failures_are_detected(self) -> None:
        evidence = passing_evidence()
        evidence["apply"]["result"]["place_errors"] = ["bad component"]
        evidence["apply"]["result"]["wires_ok"] = 14
        evidence["apply"]["result"]["wire_results"][-1] = {"ok": False}
        evidence["solve"]["ok"] = False
        evidence["canvas"]["wire_count"] = 14
        evidence["metrics"]["floor_items"] = 0
        report = evaluate_audit(evidence)
        codes = {item["code"] for item in report["findings"]}
        self.assertFalse(report["structural_pass"])
        self.assertTrue(
            {"PLACE_ERRORS", "WIRE_COUNTS", "WIRE_RESULTS", "SOLVE_FAILED", "CANVAS_WIRES", "ASSERTION_FAILED"}.issubset(codes)
        )

    def test_gh_warning_is_reported_without_becoming_structural_error(self) -> None:
        evidence = passing_evidence()
        evidence["canvas"]["objects"][0]["messages"] = [
            {"level": "warning", "text": "External input is empty"}
        ]
        report = evaluate_audit(evidence)
        self.assertTrue(report["structural_pass"])
        self.assertEqual(1, report["summary"]["WARN"])

    def test_admission_requires_matching_approved_audit(self) -> None:
        pending = evaluate_audit(passing_evidence())
        approved = evaluate_audit(passing_evidence("approved"))
        self.assertFalse(admission_check("mass-rotate", [], True, pending)["ready"])
        self.assertTrue(admission_check("mass-rotate", [], True, approved)["ready"])
        self.assertFalse(admission_check("mass-extrude", [], True, approved)["ready"])

    def test_audit_and_admit_cli_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_path = Path(directory) / "evidence.json"
            report_path = Path(directory) / "report.json"
            evidence_path.write_text(
                json.dumps(passing_evidence("approved")), encoding="utf-8"
            )
            audit = subprocess.run(
                [sys.executable, str(COMPILER), "audit", "--evidence", str(evidence_path), "--output", str(report_path)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            admit = subprocess.run(
                [sys.executable, str(COMPILER), "admit", "mass-rotate", "--audit", str(report_path)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, audit.returncode, audit.stderr)
        self.assertEqual(0, admit.returncode, admit.stderr)
        self.assertTrue(json.loads(admit.stdout)["ready"])

    def test_evidence_schema_is_machine_readable(self) -> None:
        schema = json.loads(
            (PROJECT_ROOT / "schemas" / "audit-evidence-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(1, schema["properties"]["evidence_version"]["const"])


if __name__ == "__main__":
    unittest.main()
