"""Offline validation for Grasshopper component-environment snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from graph_ir import GraphIR
from type_check import normalize_type


@dataclass(frozen=True)
class HealthIssue:
    severity: str
    code: str
    message: str
    recipe: str | None = None
    node: str | None = None
    guid: str | None = None
    port: str | None = None


def snapshot_components(snapshot: Any) -> list[dict[str, Any]]:
    if isinstance(snapshot, dict):
        components = snapshot.get("components", [])
    else:
        components = snapshot
    return [item for item in components if isinstance(item, dict)] if isinstance(components, list) else []


def component_map(snapshot: Any) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("guid", "")).lower(): item
        for item in snapshot_components(snapshot)
        if item.get("guid")
    }


def _port(component: dict[str, Any], side: str, name: str) -> dict[str, Any] | None:
    key = "outputs" if side == "output" else "inputs"
    return next((item for item in component.get(key, []) if item.get("name") == name), None)


def _snapshot_issues(snapshot: Any) -> list[HealthIssue]:
    issues: list[HealthIssue] = []
    if not isinstance(snapshot, dict):
        return [HealthIssue("ERROR", "SNAPSHOT_SHAPE", "Snapshot must be a JSON object.")]
    if snapshot.get("snapshot_version") != 2:
        issues.append(HealthIssue("ERROR", "SNAPSHOT_VERSION", "Expected snapshot_version 2."))
    components = snapshot.get("components")
    if not isinstance(components, list):
        issues.append(HealthIssue("ERROR", "SNAPSHOT_COMPONENTS", "Snapshot components must be an array."))
        return issues
    scope = snapshot.get("scope")
    if scope != "full_component_server":
        issues.append(
            HealthIssue(
                "WARN",
                "SNAPSHOT_SCOPE",
                "Snapshot is not marked as a complete Grasshopper ComponentServer scan.",
            )
        )
    seen: set[str] = set()
    for component in components:
        guid = str(component.get("guid", "")).lower() if isinstance(component, dict) else ""
        if not guid:
            issues.append(HealthIssue("ERROR", "COMPONENT_GUID", "A component has no GUID."))
        elif guid in seen:
            issues.append(HealthIssue("ERROR", "DUPLICATE_GUID", f"Duplicate component GUID: {guid}", guid=guid))
        seen.add(guid)
    return issues


def _environment_drift(snapshot: dict[str, Any], baseline: dict[str, Any]) -> list[HealthIssue]:
    issues: list[HealthIssue] = []
    current = snapshot.get("environment", {})
    reference = baseline.get("environment", {})
    for key in ("rhino_version", "grasshopper_version"):
        if current.get(key) != reference.get(key):
            issues.append(
                HealthIssue(
                    "WARN",
                    "ENVIRONMENT_DRIFT",
                    f"{key} changed from {reference.get(key)!r} to {current.get(key)!r}.",
                )
            )
    return issues


def validate_environment(
    root: Path,
    snapshot: dict[str, Any],
    recipe_ids: Iterable[str],
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues = _snapshot_issues(snapshot)
    current = component_map(snapshot)
    reference = component_map(baseline) if baseline is not None else {}
    if baseline is not None:
        issues.extend(_snapshot_issues(baseline))
        issues.extend(_environment_drift(snapshot, baseline))

    used_guids: set[str] = set()
    checked_recipes = list(recipe_ids)
    for recipe_id in checked_recipes:
        folder = root / "recipes" / recipe_id
        import json

        recipe = json.loads((folder / "recipe.json").read_text(encoding="utf-8"))
        wiring = json.loads((folder / "wiring.json").read_text(encoding="utf-8"))
        graph = GraphIR.from_wiring(wiring)
        nodes = graph.node_by_id
        for node in graph.nodes:
            guid = str(node.guid).lower()
            used_guids.add(guid)
            if guid not in current:
                issues.append(
                    HealthIssue(
                        "ERROR",
                        "MISSING_COMPONENT",
                        f"Component {node.raw.get('name', node.id)!r} is absent from the snapshot.",
                        recipe_id,
                        node.id,
                        guid,
                    )
                )

        checks: set[tuple[str, str, str]] = set()
        for connection in graph.connections:
            checks.add((connection.source.node, "output", str(connection.source.port)))
            checks.add((connection.target.node, "input", str(connection.target.port)))
        interface = recipe.get("interface", {})
        for item in interface.get("inputs", {}).values():
            for binding in item.get("bindings", []):
                checks.add((str(binding.get("node")), "input", str(binding.get("port"))))
        for item in interface.get("outputs", {}).values():
            checks.add((str(item.get("node")), "output", str(item.get("port"))))

        for node_id, side, port_name in sorted(checks):
            node = nodes.get(node_id)
            if node is None:
                continue
            guid = str(node.guid).lower()
            component = current.get(guid)
            if component is not None and _port(component, side, port_name) is None:
                issues.append(
                    HealthIssue("ERROR", "MISSING_PORT", f"{side} port {port_name!r} is absent from the installed component.", recipe_id, node_id, guid, port_name)
                )

    if baseline is not None:
        for guid in sorted(used_guids & current.keys() & reference.keys()):
            for side in ("input", "output"):
                key = "inputs" if side == "input" else "outputs"
                old_ports = {str(p.get("name")): p for p in reference[guid].get(key, [])}
                new_ports = {str(p.get("name")): p for p in current[guid].get(key, [])}
                for name in sorted(old_ports.keys() & new_ports.keys()):
                    old_type = normalize_type(old_ports[name].get("type"))
                    new_type = normalize_type(new_ports[name].get("type"))
                    if old_type != new_type:
                        issues.append(HealthIssue("WARN", "PORT_TYPE_DRIFT", f"{side} port {name!r} type changed from {old_type!r} to {new_type!r}.", guid=guid, port=name))
                    old_access = str(old_ports[name].get("access", ""))
                    new_access = str(new_ports[name].get("access", ""))
                    if old_access != new_access:
                        issues.append(HealthIssue("WARN", "PORT_ACCESS_DRIFT", f"{side} port {name!r} access changed from {old_access!r} to {new_access!r}.", guid=guid, port=name))

    counts = {severity: sum(issue.severity == severity for issue in issues) for severity in ("ERROR", "WARN", "INFO")}
    return {
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": {
            "snapshot_version": snapshot.get("snapshot_version"),
            "captured_at": snapshot.get("captured_at"),
            "scope": snapshot.get("scope"),
            "environment": snapshot.get("environment", {}),
            "component_count": len(snapshot_components(snapshot)),
        },
        "baseline_compared": baseline is not None,
        "recipes": checked_recipes,
        "summary": counts,
        "issues": [asdict(issue) for issue in issues],
    }
