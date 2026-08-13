"""Advisory Grasshopper connection type checking."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from graph_ir import GraphIR


TYPE_STATUSES = ("EXACT", "KNOWN_CAST", "WARN", "UNKNOWN", "INCOMPATIBLE")


def normalize_type(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or raw.casefold() == "unknown":
        return ""
    return raw.split(".")[-1]


@dataclass(frozen=True)
class ComponentCatalog:
    source: str
    complete: bool
    by_guid: dict[str, dict[str, Any]]

    @classmethod
    def load(cls, root: Path) -> "ComponentCatalog":
        full_path = root / "data" / "component_library.json"
        hot_path = root / "data" / "hot_components.json"
        if full_path.is_file():
            data = json.loads(full_path.read_text(encoding="utf-8"))
            components = data.get("components", []) if isinstance(data, dict) else data
            source = str(full_path.relative_to(root))
            complete = True
        elif hot_path.is_file():
            data = json.loads(hot_path.read_text(encoding="utf-8"))
            components = data.get("components", []) if isinstance(data, dict) else data
            source = str(hot_path.relative_to(root))
            complete = False
        else:
            components = []
            source = "none"
            complete = False
        by_guid = {
            str(item.get("guid", "")).lower(): item
            for item in components
            if isinstance(item, dict) and item.get("guid")
        }
        return cls(source, complete, by_guid)


@dataclass(frozen=True)
class TypeRules:
    data: dict[str, Any]

    @classmethod
    def load(cls, root: Path) -> "TypeRules":
        path = root / "knowledge" / "type-compat.json"
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def classify(self, source_type: str, target_type: str) -> tuple[str, str]:
        if not source_type or not target_type:
            return "UNKNOWN", "A source or target type is missing from the component snapshot."
        if source_type == target_type:
            return self.data.get("same_type_status", "EXACT"), "Declared types match."

        for rule in self.data.get("rules", []):
            if rule.get("from") == source_type and rule.get("to") == target_type:
                reason = str(rule.get("reason", "Reviewed compatibility rule."))
                if rule.get("adapter"):
                    reason += f" Adapter: {rule['adapter']}."
                return str(rule["status"]), reason

        for rule in self.data.get("broad_targets", []):
            sources = rule.get("from", [])
            if rule.get("to") == target_type and (
                "*" in sources or source_type in sources
            ):
                return str(rule["status"]), str(rule.get("reason", "Broad target."))

        for rule in self.data.get("generic_source_fallbacks", []):
            if rule.get("from") == source_type:
                return str(rule["status"]), str(rule.get("reason", "Generic source."))
        return str(self.data.get("default_status", "UNKNOWN")), "No reviewed compatibility rule matches this pair."


@dataclass(frozen=True)
class ConnectionTypeResult:
    index: int
    status: str
    source_node: str
    source_port: str
    source_type: str
    target_node: str
    target_port: str
    target_type: str
    reason: str


def _port_type(
    component: dict[str, Any] | None, side: str, port_name: Any
) -> tuple[str, str]:
    if component is None:
        return "", "component is absent from the available snapshot"
    ports = component.get("outputs" if side == "source" else "inputs", [])
    for port in ports:
        if port.get("name") == port_name:
            return normalize_type(port.get("type")), ""
    return "", f"port {port_name!r} is absent from the available snapshot"


def check_graph_types(
    graph: GraphIR, catalog: ComponentCatalog, rules: TypeRules
) -> list[ConnectionTypeResult]:
    nodes = graph.node_by_id
    results: list[ConnectionTypeResult] = []
    for index, connection in enumerate(graph.connections):
        source_node = nodes.get(connection.source.node)
        target_node = nodes.get(connection.target.node)
        source_component = (
            catalog.by_guid.get(str(source_node.guid).lower()) if source_node else None
        )
        target_component = (
            catalog.by_guid.get(str(target_node.guid).lower()) if target_node else None
        )
        source_type, source_problem = _port_type(
            source_component, "source", connection.source.port
        )
        target_type, target_problem = _port_type(
            target_component, "target", connection.target.port
        )
        if source_problem or target_problem:
            status = "UNKNOWN"
            reason = "; ".join(
                problem for problem in (source_problem, target_problem) if problem
            )
        else:
            status, reason = rules.classify(source_type, target_type)
        results.append(
            ConnectionTypeResult(
                index=index,
                status=status,
                source_node=str(connection.source.node),
                source_port=str(connection.source.port),
                source_type=source_type,
                target_node=str(connection.target.node),
                target_port=str(connection.target.port),
                target_type=target_type,
                reason=reason,
            )
        )
    return results


def summarize_types(results: list[ConnectionTypeResult]) -> dict[str, int]:
    return {
        status: sum(result.status == status for result in results)
        for status in TYPE_STATUSES
    }


def blocking_type_results(
    results: list[ConnectionTypeResult], strict: bool = False
) -> list[ConnectionTypeResult]:
    blocked = {"INCOMPATIBLE"}
    if strict:
        blocked.update({"WARN", "UNKNOWN"})
    return [result for result in results if result.status in blocked]
