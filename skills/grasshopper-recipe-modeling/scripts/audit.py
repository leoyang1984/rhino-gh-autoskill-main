"""Evaluate normalized evidence from a live Grasshopper MCP run."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    code: str
    message: str
    check_id: str | None = None


def _value_at(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(path)
        value = value[part]
    return value


def _assertion_findings(evidence: dict[str, Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for assertion in evidence.get("assertions", []):
        check_id = str(assertion.get("id", "unnamed"))
        kind = assertion.get("kind")
        paths = assertion.get("paths", [])
        try:
            values = [_value_at(evidence, str(path)) for path in paths]
        except KeyError as exc:
            findings.append(AuditFinding("ERROR", "ASSERTION_PATH", f"Missing evidence path {exc.args[0]!r}.", check_id))
            continue
        passed = False
        if kind == "nonzero" and len(values) == 1:
            passed = isinstance(values[0], (int, float)) and values[0] > 0
        elif kind == "equals" and len(values) == 1:
            passed = values[0] == assertion.get("expected")
        elif kind == "lengths_equal" and len(values) >= 2:
            passed = all(value == values[0] for value in values[1:])
        elif kind == "range" and len(values) == 1 and isinstance(values[0], (int, float)):
            minimum = assertion.get("minimum")
            maximum = assertion.get("maximum")
            passed = (minimum is None or values[0] >= minimum) and (maximum is None or values[0] <= maximum)
        else:
            findings.append(AuditFinding("ERROR", "ASSERTION_INVALID", f"Unsupported or malformed assertion kind {kind!r}.", check_id))
            continue
        if not passed:
            findings.append(AuditFinding("ERROR", "ASSERTION_FAILED", str(assertion.get("description") or f"Assertion {check_id!r} failed."), check_id))
    return findings


def evaluate_audit(evidence: dict[str, Any]) -> dict[str, Any]:
    findings: list[AuditFinding] = []
    if evidence.get("evidence_version") != 1:
        findings.append(AuditFinding("ERROR", "EVIDENCE_VERSION", "Expected evidence_version 1."))

    apply = evidence.get("apply", {})
    requested = apply.get("requested", {})
    result = apply.get("result", {})
    place_errors = result.get("place_errors")
    if not isinstance(place_errors, list):
        findings.append(AuditFinding("ERROR", "APPLY_EVIDENCE", "apply.result.place_errors must be an array."))
    elif place_errors:
        findings.append(AuditFinding("ERROR", "PLACE_ERRORS", f"Graph placement reported {len(place_errors)} error(s)."))

    requested_wires = requested.get("wires")
    wires_ok = result.get("wires_ok")
    if not isinstance(requested_wires, int) or not isinstance(wires_ok, int):
        findings.append(AuditFinding("ERROR", "WIRE_COUNTS", "Requested and successful wire counts must be integers."))
    elif wires_ok != requested_wires:
        findings.append(AuditFinding("ERROR", "WIRE_COUNTS", f"WiresOk={wires_ok}, requested={requested_wires}."))
    wire_results = result.get("wire_results", [])
    if not isinstance(wire_results, list):
        findings.append(AuditFinding("ERROR", "WIRE_RESULTS", "wire_results must be an array."))
    else:
        failed = [item for item in wire_results if not isinstance(item, dict) or item.get("ok") is not True]
        if failed:
            findings.append(AuditFinding("ERROR", "WIRE_RESULTS", f"{len(failed)} wire result(s) are not successful."))

    solve = evidence.get("solve", {})
    if solve.get("ok") is not True:
        findings.append(AuditFinding("ERROR", "SOLVE_FAILED", "The normalized solve result is not successful."))

    canvas = evidence.get("canvas", {})
    requested_objects = requested.get("components", 0) + requested.get("sliders", 0) if all(isinstance(requested.get(key), int) for key in ("components", "sliders")) else None
    object_count = canvas.get("object_count")
    if requested_objects is None or not isinstance(object_count, int):
        findings.append(AuditFinding("ERROR", "OBJECT_COUNTS", "Requested and canvas object counts must be integers."))
    elif object_count != requested_objects:
        findings.append(AuditFinding("ERROR", "OBJECT_COUNTS", f"Canvas objects={object_count}, requested={requested_objects}."))
    canvas_wires = canvas.get("wire_count")
    if isinstance(requested_wires, int) and canvas_wires != requested_wires:
        findings.append(AuditFinding("ERROR", "CANVAS_WIRES", f"Canvas wires={canvas_wires!r}, requested={requested_wires}."))

    objects = canvas.get("objects")
    if not isinstance(objects, list):
        findings.append(AuditFinding("ERROR", "CANVAS_OBJECTS", "canvas.objects must be an array."))
    else:
        for item in objects:
            for message in item.get("messages", []) if isinstance(item, dict) else []:
                level = str(message.get("level", "warning")).casefold() if isinstance(message, dict) else "warning"
                severity = "ERROR" if level == "error" else "WARN"
                text = message.get("text", "Grasshopper message") if isinstance(message, dict) else str(message)
                findings.append(AuditFinding(severity, "GH_MESSAGE", f"{item.get('name', item.get('id', 'object'))}: {text}"))

    findings.extend(_assertion_findings(evidence))
    counts = {severity: sum(item.severity == severity for item in findings) for severity in ("ERROR", "WARN", "INFO")}
    visual = evidence.get("visual_review", {"status": "pending"})
    structural_pass = counts["ERROR"] == 0
    return {
        "audit_report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subject": evidence.get("subject", {}),
        "evidence_captured_at": evidence.get("captured_at"),
        "summary": counts,
        "structural_pass": structural_pass,
        "visual_review": visual,
        "admission_ready": structural_pass and visual.get("status") == "approved",
        "findings": [asdict(item) for item in findings],
    }


def admission_check(
    recipe_id: str,
    recipe_errors: list[str],
    indexed: bool,
    audit_report: dict[str, Any],
) -> dict[str, Any]:
    reasons = list(recipe_errors)
    if not indexed:
        reasons.append("Recipe is absent from recipes/index.json.")
    subject = audit_report.get("subject", {})
    if subject.get("id") != recipe_id:
        reasons.append("Audit subject does not match the Recipe id.")
    if audit_report.get("structural_pass") is not True:
        reasons.append("Dynamic structural audit did not pass.")
    if audit_report.get("visual_review", {}).get("status") != "approved":
        reasons.append("User visual approval is not recorded.")
    return {"recipe_id": recipe_id, "ready": not reasons, "reasons": reasons}

