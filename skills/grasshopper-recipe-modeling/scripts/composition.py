"""Compose two Recipe v2 graphs through stable public interfaces."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from graph_ir import GraphIR, SLIDER_GUID, graph_error_messages


class CompositionError(ValueError):
    pass


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _namespace_wiring(
    wiring: dict[str, Any], prefix: str, x_offset: float = 0
) -> dict[str, Any]:
    result = deepcopy(wiring)
    mapping = {node["id"]: f"{prefix}__{node['id']}" for node in result["nodes"]}
    for node in result["nodes"]:
        node["id"] = mapping[node["id"]]
        if x_offset:
            node["position"]["x"] = float(node["position"].get("x", 0)) + x_offset
    for wire in result["connections"]:
        wire["from"]["node"] = mapping[wire["from"]["node"]]
        wire["to"]["node"] = mapping[wire["to"]["node"]]
    return result


def _wire_key(wire: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        wire["from"]["node"],
        wire["from"]["port"],
        wire["to"]["node"],
        wire["to"]["port"],
    )


def _prune_replaced_input_prefix(
    wiring: dict[str, Any], targets: set[tuple[str, str]]
) -> dict[str, Any]:
    result = deepcopy(wiring)
    removed_wires = {
        _wire_key(wire)
        for wire in result["connections"]
        if (wire["to"]["node"], wire["to"]["port"]) in targets
    }
    seeds = {key[0] for key in removed_wires}
    incoming: dict[str, set[str]] = {}
    for wire in result["connections"]:
        incoming.setdefault(wire["to"]["node"], set()).add(wire["from"]["node"])
    candidates = set(seeds)
    queue = list(seeds)
    while queue:
        current = queue.pop()
        for parent in incoming.get(current, set()):
            if parent not in candidates:
                candidates.add(parent)
                queue.append(parent)

    removable = set(candidates)
    changed = True
    while changed:
        changed = False
        for node_id in list(removable):
            external_use = any(
                wire["from"]["node"] == node_id
                and _wire_key(wire) not in removed_wires
                and wire["to"]["node"] not in removable
                for wire in result["connections"]
            )
            if external_use:
                removable.remove(node_id)
                changed = True

    result["nodes"] = [node for node in result["nodes"] if node["id"] not in removable]
    result["connections"] = [
        wire
        for wire in result["connections"]
        if _wire_key(wire) not in removed_wires
        and wire["from"]["node"] not in removable
        and wire["to"]["node"] not in removable
    ]
    return result


def _remove_parameter_node(
    wiring: dict[str, Any], node_id: str
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    targets = [
        (wire["to"]["node"], wire["to"]["port"])
        for wire in wiring["connections"]
        if wire["from"]["node"] == node_id
    ]
    result = deepcopy(wiring)
    result["nodes"] = [node for node in result["nodes"] if node["id"] != node_id]
    result["connections"] = [
        wire
        for wire in result["connections"]
        if wire["from"]["node"] != node_id and wire["to"]["node"] != node_id
    ]
    return result, targets


def _catalog_name(root: Path, selector: str) -> str:
    for path in (root / "data" / "component_library.json", root / "data" / "hot_components.json"):
        if not path.is_file():
            continue
        data = _read_json(path)
        components = data.get("components", []) if isinstance(data, dict) else data
        for component in components:
            if str(component.get("guid", "")).lower() == selector.lower():
                return str(component.get("name") or selector)
    return selector


def _build_adapters(
    root: Path,
    binding_index: int,
    adapters: list[dict[str, Any]],
    source_endpoint: tuple[str, str],
    start_x: float,
    y: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[str, str]]:
    nodes: list[dict[str, Any]] = []
    wires: list[dict[str, Any]] = []
    current = source_endpoint
    for step_index, adapter in enumerate(adapters):
        adapter_id = f"bridge__b{binding_index}__s{step_index}"
        selector = str(adapter["selector"])
        x = start_x + step_index * 200
        nodes.append(
            {
                "id": adapter_id,
                "guid": selector,
                "name": _catalog_name(root, selector),
                "position": {"x": x, "y": y},
            }
        )
        wires.append(
            {
                "from": {"node": current[0], "port": current[1]},
                "to": {"node": adapter_id, "port": adapter["input_port"]},
            }
        )
        for parameter_index, (port, spec) in enumerate(
            adapter.get("parameters", {}).items()
        ):
            if spec.get("kind") != "slider":
                raise CompositionError(
                    f"adapter parameter {port} requires supported kind=slider"
                )
            slider_id = (
                f"bridge__b{binding_index}__s{step_index}__p{parameter_index}"
            )
            nodes.append(
                {
                    "id": slider_id,
                    "guid": SLIDER_GUID,
                    "name": "Number Slider",
                    "nickname": spec.get("name", port),
                    "position": {"x": x - 120, "y": y + 100 + parameter_index * 80},
                    "preset": {
                        "value": spec["value"],
                        "min": spec["min"],
                        "max": spec["max"],
                    },
                }
            )
            wires.append(
                {
                    "from": {"node": slider_id, "port": "Value"},
                    "to": {"node": adapter_id, "port": port},
                }
            )
        current = (adapter_id, str(adapter["output_port"]))
    return nodes, wires, current


def compose_recipe_pair(
    root: Path,
    source_id: str,
    target_id: str,
    rule_id: str | None = None,
) -> dict[str, Any]:
    source_recipe = _read_json(root / "recipes" / source_id / "recipe.json")
    target_recipe = _read_json(root / "recipes" / target_id / "recipe.json")
    source_wiring = _read_json(root / "recipes" / source_id / "wiring.json")
    target_wiring = _read_json(root / "recipes" / target_id / "wiring.json")

    candidates = [
        rule
        for rule in source_recipe.get("composition_rules", [])
        if rule.get("target_recipe") == target_id
        and (rule_id is None or rule.get("id") == rule_id)
    ]
    if not candidates:
        raise CompositionError(
            f"No composition rule from {source_id} to {target_id}"
            + (f" with id {rule_id}" if rule_id else "")
        )
    if len(candidates) > 1 and rule_id is None:
        raise CompositionError(
            f"Several rules match {source_id} -> {target_id}; select --rule"
        )
    rule = candidates[0]

    resolved_targets: list[list[tuple[str, str]]] = []
    public_input_targets: set[tuple[str, str]] = set()
    parameter_nodes: set[str] = set()
    for binding in rule["bindings"]:
        target = binding["to"]
        if "input" in target:
            input_name = target["input"]
            input_spec = target_recipe["interface"]["inputs"].get(input_name)
            if input_spec is None:
                raise CompositionError(
                    f"Target Recipe {target_id} has no public input {input_name}"
                )
            endpoints = [
                (item["node"], item["port"]) for item in input_spec["bindings"]
            ]
            public_input_targets.update(endpoints)
            resolved_targets.append(endpoints)
        else:
            parameter_name = target.get("parameter")
            parameter_spec = target_recipe["interface"]["parameters"].get(parameter_name)
            if parameter_spec is None:
                raise CompositionError(
                    f"Target Recipe {target_id} has no public parameter {parameter_name}"
                )
            node_id = parameter_spec["node"]
            parameter_nodes.add(node_id)
            endpoints = [
                (wire["to"]["node"], wire["to"]["port"])
                for wire in target_wiring["connections"]
                if wire["from"]["node"] == node_id
            ]
            if not endpoints:
                raise CompositionError(
                    f"Target parameter {target_id}.{parameter_name} has no consumers"
                )
            resolved_targets.append(endpoints)

    target_working = _prune_replaced_input_prefix(
        target_wiring, public_input_targets
    )
    for node_id in parameter_nodes:
        target_working, _ = _remove_parameter_node(target_working, node_id)

    source_max_x = max(float(node["position"].get("x", 0)) for node in source_wiring["nodes"])
    target_min_x = min(float(node["position"].get("x", 0)) for node in target_working["nodes"])
    max_adapters = max((len(binding.get("adapters", [])) for binding in rule["bindings"]), default=0)
    target_offset = source_max_x + (max_adapters + 2) * 200 - target_min_x
    source_ns = _namespace_wiring(source_wiring, source_id)
    target_ns = _namespace_wiring(target_working, target_id, target_offset)

    nodes = source_ns["nodes"] + target_ns["nodes"]
    wires = source_ns["connections"] + target_ns["connections"]
    for index, (binding, endpoints) in enumerate(
        zip(rule["bindings"], resolved_targets)
    ):
        output_name = binding["from_output"]
        output = source_recipe["interface"]["outputs"].get(output_name)
        if output is None:
            raise CompositionError(
                f"Source Recipe {source_id} has no public output {output_name}"
            )
        current = (f"{source_id}__{output['node']}", output["port"])
        adapter_nodes, adapter_wires, current = _build_adapters(
            root,
            index,
            binding.get("adapters", []),
            current,
            start_x=source_max_x + 180,
            y=index * 260,
        )
        nodes.extend(adapter_nodes)
        wires.extend(adapter_wires)
        for node_id, port in endpoints:
            wires.append(
                {
                    "from": {"node": current[0], "port": current[1]},
                    "to": {"node": f"{target_id}__{node_id}", "port": port},
                }
            )

    result = {
        "description": f"{source_recipe['name']} → {target_recipe['name']}",
        "_composition": {
            "source_recipe": source_id,
            "target_recipe": target_id,
            "rule": rule["id"],
        },
        "nodes": nodes,
        "connections": wires,
    }
    graph = GraphIR.from_wiring(result)
    errors = graph_error_messages(graph)
    if errors:
        raise CompositionError("; ".join(errors))
    return result
