"""Shared graph intermediate representation, validation, and emitters."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


SLIDER_GUID = "57da07bd-ecab-415d-9d86-af36d7073abc"
PURE_PARAM_GUIDS = {
    SLIDER_GUID,
    "deaf8653-5528-4286-807c-3de8b8dad781",  # Surface parameter
    "d5967b9f-e8ee-436b-a8ad-29fdcecf32d5",  # Curve parameter
}
INTEGER_TOKENS = {"count", "floors", "tier", "tiers", "degree", "spans"}


class GraphIRError(ValueError):
    pass


@dataclass(frozen=True)
class Endpoint:
    node: Any
    port: Any


@dataclass(frozen=True)
class GraphNode:
    id: Any
    guid: Any
    raw: dict[str, Any]


@dataclass(frozen=True)
class GraphConnection:
    source: Endpoint
    target: Endpoint
    raw: dict[str, Any]


@dataclass(frozen=True)
class GraphIssue:
    severity: str
    code: str
    message: str
    path: str


@dataclass(frozen=True)
class GraphIR:
    metadata: dict[str, Any]
    nodes: tuple[GraphNode, ...]
    connections: tuple[GraphConnection, ...]

    @classmethod
    def from_wiring(cls, wiring: dict[str, Any]) -> "GraphIR":
        if not isinstance(wiring, dict):
            raise GraphIRError("wiring must be a JSON object")
        raw_nodes = wiring.get("nodes")
        raw_connections = wiring.get("connections")
        if not isinstance(raw_nodes, list) or not isinstance(raw_connections, list):
            raise GraphIRError("wiring.json requires nodes[] and connections[]")

        nodes: list[GraphNode] = []
        for index, raw in enumerate(raw_nodes):
            if not isinstance(raw, dict):
                raise GraphIRError(f"node {index} must be an object")
            nodes.append(GraphNode(raw.get("id"), raw.get("guid"), deepcopy(raw)))

        connections: list[GraphConnection] = []
        for index, raw in enumerate(raw_connections):
            if not isinstance(raw, dict):
                raise GraphIRError(f"connection {index} must be an object")
            source = raw.get("from")
            target = raw.get("to")
            if not isinstance(source, dict) or not isinstance(target, dict):
                raise GraphIRError(
                    f"connection {index} requires from and to endpoint objects"
                )
            connections.append(
                GraphConnection(
                    Endpoint(source.get("node"), source.get("port")),
                    Endpoint(target.get("node"), target.get("port")),
                    deepcopy(raw),
                )
            )

        metadata = {
            key: deepcopy(value)
            for key, value in wiring.items()
            if key not in {"nodes", "connections"}
        }
        return cls(metadata, tuple(nodes), tuple(connections))

    def to_wiring(self) -> dict[str, Any]:
        result = deepcopy(self.metadata)
        result["nodes"] = [deepcopy(node.raw) for node in self.nodes]
        result["connections"] = [
            deepcopy(connection.raw) for connection in self.connections
        ]
        return result

    @property
    def node_by_id(self) -> dict[Any, GraphNode]:
        return {node.id: node for node in self.nodes}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_graph_structure(graph: GraphIR) -> list[GraphIssue]:
    issues: list[GraphIssue] = []
    ids = [node.id for node in graph.nodes]
    if any(node_id is None or str(node_id).strip() == "" for node_id in ids):
        issues.append(
            GraphIssue("error", "node_id_empty", "Every wiring node needs a non-empty id", "nodes")
        )
    if len(ids) != len(set(ids)):
        issues.append(
            GraphIssue("error", "node_id_duplicate", "Every wiring node must have a unique non-empty id", "nodes")
        )

    for index, node in enumerate(graph.nodes):
        try:
            uuid.UUID(str(node.guid))
        except (ValueError, AttributeError, TypeError):
            issues.append(
                GraphIssue(
                    "error",
                    "guid_invalid",
                    f"node {node.id} has invalid guid {node.guid!r}",
                    f"nodes[{index}].guid",
                )
            )
        position = node.raw.get("position", {})
        if not isinstance(position, dict) or not all(
            _is_number(position.get(axis, 0)) for axis in ("x", "y")
        ):
            issues.append(
                GraphIssue(
                    "error",
                    "position_invalid",
                    f"node {node.id} position x/y must be numeric",
                    f"nodes[{index}].position",
                )
            )

    known_ids = set(ids)
    seen_connections: set[tuple[Any, Any, Any, Any]] = set()
    for index, connection in enumerate(graph.connections):
        source = connection.source
        target = connection.target
        if source.node not in known_ids or target.node not in known_ids:
            issues.append(
                GraphIssue(
                    "error",
                    "connection_node_missing",
                    f"Connection {index} references a missing node",
                    f"connections[{index}]",
                )
            )
        for side, endpoint in (("from", source), ("to", target)):
            if not isinstance(endpoint.port, str) or not endpoint.port.strip():
                issues.append(
                    GraphIssue(
                        "error",
                        "connection_port_empty",
                        f"Connection {index} {side} port must be a non-empty string",
                        f"connections[{index}].{side}.port",
                    )
                )
        key = (source.node, source.port, target.node, target.port)
        if key in seen_connections:
            issues.append(
                GraphIssue(
                    "warning",
                    "connection_duplicate",
                    f"Connection {index} duplicates an earlier wire",
                    f"connections[{index}]",
                )
            )
        seen_connections.add(key)
    return issues


def graph_error_messages(graph: GraphIR) -> list[str]:
    return [
        issue.message
        for issue in validate_graph_structure(graph)
        if issue.severity == "error"
    ]


def _split_identifier(value: str) -> set[str]:
    expanded = ""
    for index, char in enumerate(value):
        if index and char.isupper() and value[index - 1].islower():
            expanded += " "
        expanded += char
    return {
        part.casefold()
        for part in expanded.replace("_", " ").replace("-", " ").split()
    }


def _is_integer_slider(node: dict[str, Any], parameter_type: str | None) -> bool:
    if parameter_type == "integer":
        return True
    return bool(INTEGER_TOKENS.intersection(_split_identifier(str(node.get("nickname", "")))))


def _resolve_parameters(
    graph: GraphIR,
    parameters: dict[str, Any],
    overrides: dict[str, int | float],
) -> tuple[dict[str, str], dict[str, int | float]]:
    unknown = sorted(set(overrides) - set(parameters))
    if unknown:
        raise GraphIRError(
            f"Unknown parameter(s): {', '.join(unknown)}. "
            f"Available: {', '.join(sorted(parameters)) or '(none)'}"
        )
    node_ids = {node.id for node in graph.nodes}
    parameter_type_by_node: dict[str, str] = {}
    effective_values: dict[str, int | float] = {}
    for name, spec in parameters.items():
        if not isinstance(spec, dict):
            raise GraphIRError(f"Parameter {name} must be an object")
        node_id = spec.get("node")
        field = spec.get("field")
        if node_id not in node_ids:
            raise GraphIRError(f"Parameter {name} targets missing node {node_id}")
        if field != "value":
            raise GraphIRError(f"Unsupported parameter field for {name}: {field}")
        parameter_type_by_node[str(node_id)] = str(spec.get("type", "number"))
        effective_values[str(node_id)] = overrides.get(name, spec.get("default"))
    return parameter_type_by_node, effective_values


def emit_mcp_payload(
    graph: GraphIR,
    parameters: dict[str, Any],
    overrides: dict[str, int | float],
    x_offset: float = 0,
    y_offset: float = 0,
    solve: bool = True,
) -> dict[str, Any]:
    errors = graph_error_messages(graph)
    if errors:
        raise GraphIRError(errors[0])
    parameter_type_by_node, effective_values = _resolve_parameters(
        graph, parameters, overrides
    )

    sliders: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    pure_param_ids: set[str] = set()

    for graph_node in graph.nodes:
        node = graph_node.raw
        node_id = str(graph_node.id)
        guid = str(graph_node.guid or "").lower()
        position = node.get("position", {})
        x = float(position.get("x", 0)) + x_offset
        y = float(position.get("y", 0)) + y_offset

        if guid == SLIDER_GUID or node.get("name") == "Number Slider":
            preset = node.get("preset")
            if not isinstance(preset, dict):
                raise GraphIRError(f"Slider {node_id} is missing preset data")
            minimum = preset.get("min")
            maximum = preset.get("max")
            value = effective_values.get(node_id, preset.get("value"))
            if not all(_is_number(v) for v in (minimum, value, maximum)):
                raise GraphIRError(f"Slider {node_id} min/value/max must be numeric")
            if minimum > maximum or not minimum <= value <= maximum:
                raise GraphIRError(
                    f"Slider {node_id} value {value} is outside [{minimum}, {maximum}]"
                )
            slider_type = (
                "int"
                if _is_integer_slider(node, parameter_type_by_node.get(node_id))
                else "float"
            )
            if slider_type == "int" and any(
                float(v) != int(v) for v in (minimum, value, maximum)
            ):
                raise GraphIRError(
                    f"Integer slider {node_id} has a non-integer range or value"
                )
            sliders.append(
                {
                    "Key": node_id,
                    "Min": int(minimum) if slider_type == "int" else minimum,
                    "Value": int(value) if slider_type == "int" else value,
                    "Max": int(maximum) if slider_type == "int" else maximum,
                    "Type": slider_type,
                    "Name": node.get("nickname") or node.get("name") or node_id,
                    "X": x,
                    "Y": y,
                }
            )
            pure_param_ids.add(node_id)
        else:
            selector = graph_node.guid or node.get("name")
            if not selector:
                raise GraphIRError(f"Node {node_id} has neither guid nor name")
            components.append(
                {"Key": node_id, "Selector": selector, "X": x, "Y": y}
            )
            if guid in PURE_PARAM_GUIDS:
                pure_param_ids.add(node_id)

    wires: list[dict[str, Any]] = []
    for connection in graph.connections:
        source_id = str(connection.source.node)
        target_id = str(connection.target.node)
        wires.append(
            {
                "SrcKey": source_id,
                "Src": "" if source_id in pure_param_ids else connection.source.port,
                "DstKey": target_id,
                "Dst": "" if target_id in pure_param_ids else connection.target.port,
            }
        )
    return {
        "components": components,
        "sliders": sliders,
        "wires": wires,
        "solve": solve,
    }


def emit_legacy_wiring(
    graph: GraphIR,
    parameters: dict[str, Any],
    overrides: dict[str, int | float],
    x_offset: float = 0,
    y_offset: float = 0,
) -> dict[str, Any]:
    # Run the same validation and parameter checks used by the MCP backend.
    emit_mcp_payload(
        graph,
        parameters,
        overrides,
        x_offset=x_offset,
        y_offset=y_offset,
        solve=False,
    )
    _, effective_values = _resolve_parameters(graph, parameters, overrides)
    wiring = graph.to_wiring()
    for node in wiring["nodes"]:
        node_id = str(node["id"])
        if node_id in effective_values:
            node["preset"]["value"] = effective_values[node_id]
        if x_offset or y_offset:
            position = node.setdefault("position", {})
            position["x"] = float(position.get("x", 0)) + x_offset
            position["y"] = float(position.get("y", 0)) + y_offset
    return wiring
