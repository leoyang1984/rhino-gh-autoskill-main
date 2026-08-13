"""Recipe schema compatibility and migration helpers.

The project intentionally uses standard-library validation in the compiler.
The JSON Schema remains the complete machine-readable contract for external
tooling; these helpers enforce the invariants needed by the current runtime.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


CURRENT_SCHEMA_VERSION = 2
PUBLIC_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
ACCESS_VALUES = {"item", "list", "tree"}


def schema_version(recipe: dict[str, Any]) -> int:
    """Return the effective schema version; unversioned legacy Recipes are v1."""
    raw = recipe.get("schema_version", 1)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return -1
    return raw


def public_parameters(recipe: dict[str, Any]) -> dict[str, Any]:
    """Return the public parameter mapping for either supported schema."""
    if schema_version(recipe) == 2:
        interface = recipe.get("interface", {})
        value = interface.get("parameters", {}) if isinstance(interface, dict) else {}
        return value if isinstance(value, dict) else {}
    value = recipe.get("parameters", {})
    return value if isinstance(value, dict) else {}


def validate_recipe_contract(
    recipe: dict[str, Any], wiring: dict[str, Any]
) -> list[str]:
    """Validate schema-version and v2 public-interface invariants."""
    version = schema_version(recipe)
    if version == 1:
        return []
    if version != CURRENT_SCHEMA_VERSION:
        return [f"unsupported schema_version {recipe.get('schema_version')!r}"]

    errors: list[str] = []
    nodes = wiring.get("nodes", [])
    node_ids = {
        node.get("id") for node in nodes if isinstance(node, dict) and node.get("id")
    }
    interface = recipe.get("interface")
    if not isinstance(interface, dict):
        return ["schema v2 requires interface object"]

    parameters = interface.get("parameters")
    inputs = interface.get("inputs")
    outputs = interface.get("outputs")
    for name, value in (
        ("parameters", parameters),
        ("inputs", inputs),
        ("outputs", outputs),
    ):
        if not isinstance(value, dict):
            errors.append(f"interface.{name} must be an object")

    if errors:
        return errors
    assert isinstance(parameters, dict)
    assert isinstance(inputs, dict)
    assert isinstance(outputs, dict)

    if not outputs:
        errors.append("schema v2 requires at least one public output")

    for collection_name, collection in (
        ("parameter", parameters),
        ("input", inputs),
        ("output", outputs),
    ):
        for name in collection:
            if not PUBLIC_NAME_RE.fullmatch(str(name)):
                errors.append(f"invalid public {collection_name} name {name!r}")

    for name, spec in parameters.items():
        if not isinstance(spec, dict):
            errors.append(f"parameter {name} must be an object")
            continue
        if spec.get("node") not in node_ids:
            errors.append(f"parameter {name} targets missing node {spec.get('node')}")
        if spec.get("field") != "value":
            errors.append(f"parameter {name} has unsupported field {spec.get('field')!r}")

    for name, spec in inputs.items():
        if not isinstance(spec, dict):
            errors.append(f"input {name} must be an object")
            continue
        if not str(spec.get("type", "")).strip():
            errors.append(f"input {name} requires type")
        if spec.get("access") not in ACCESS_VALUES:
            errors.append(f"input {name} has invalid access {spec.get('access')!r}")
        bindings = spec.get("bindings")
        if not isinstance(bindings, list) or not bindings:
            errors.append(f"input {name} requires at least one binding")
            continue
        for index, binding in enumerate(bindings):
            if not isinstance(binding, dict):
                errors.append(f"input {name} binding {index} must be an object")
                continue
            if binding.get("node") not in node_ids:
                errors.append(
                    f"input {name} binding {index} targets missing node "
                    f"{binding.get('node')}"
                )
            if not str(binding.get("port", "")).strip():
                errors.append(f"input {name} binding {index} requires port")
            if binding.get("mode") not in {"replace", "append"}:
                errors.append(
                    f"input {name} binding {index} has invalid mode "
                    f"{binding.get('mode')!r}"
                )

    for name, spec in outputs.items():
        if not isinstance(spec, dict):
            errors.append(f"output {name} must be an object")
            continue
        if spec.get("node") not in node_ids:
            errors.append(f"output {name} targets missing node {spec.get('node')}")
        if not str(spec.get("port", "")).strip():
            errors.append(f"output {name} requires port")
        if not str(spec.get("type", "")).strip():
            errors.append(f"output {name} requires type")
        if spec.get("access") not in ACCESS_VALUES:
            errors.append(f"output {name} has invalid access {spec.get('access')!r}")

    rules = recipe.get("composition_rules")
    if not isinstance(rules, list):
        errors.append("schema v2 requires composition_rules array")
    else:
        for rule_index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"composition rule {rule_index} must be an object")
                continue
            bindings = rule.get("bindings")
            if not isinstance(bindings, list) or not bindings:
                errors.append(f"composition rule {rule_index} requires bindings")
                continue
            for binding_index, binding in enumerate(bindings):
                if not isinstance(binding, dict):
                    errors.append(
                        f"composition rule {rule_index} binding {binding_index} "
                        "must be an object"
                    )
                    continue
                output_name = binding.get("from_output")
                if output_name not in outputs:
                    errors.append(
                        f"composition rule {rule_index} references unknown output "
                        f"{output_name!r}"
                    )

    return errors


def _split_legacy_type(value: Any) -> tuple[str, str, int | None]:
    raw = str(value or "").strip()
    if raw.endswith(" pair"):
        return raw[: -len(" pair")], "list", 2
    if raw.endswith(" list"):
        return raw[: -len(" list")], "list", None
    return raw, "item", None


def _public_name(raw: str, fallback: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", raw.casefold()).strip("_")
    if not value or not value[0].isalpha():
        value = fallback
    return value


def migration_preview(
    recipe: dict[str, Any], wiring: dict[str, Any]
) -> dict[str, Any]:
    """Build a non-destructive v2 draft and list every unresolved decision."""
    version = schema_version(recipe)
    if version == 2:
        return {
            "recipe_id": recipe.get("id"),
            "source_version": 2,
            "target_version": 2,
            "ready": not validate_recipe_contract(recipe, wiring),
            "unresolved": validate_recipe_contract(recipe, wiring),
            "draft": deepcopy(recipe),
        }
    if version != 1:
        return {
            "recipe_id": recipe.get("id"),
            "source_version": version,
            "target_version": 2,
            "ready": False,
            "unresolved": ["unsupported source schema version"],
            "draft": None,
        }

    unresolved: list[str] = []
    inputs: dict[str, Any] = {}
    chain_input = recipe.get("chain_input")
    if chain_input:
        input_type, access, cardinality = _split_legacy_type(chain_input)
        inputs["external_input"] = {
            "type": input_type,
            "access": access,
            "cardinality": cardinality,
            "description": "Migrated from legacy chain_input; binding requires review.",
            "bindings": [],
        }
        unresolved.append(
            "public input external_input needs explicit internal bindings and a domain name"
        )

    outputs: dict[str, Any] = {}
    for index, bridge in enumerate(recipe.get("chain_bridges", []), start=1):
        if not isinstance(bridge, dict) or not bridge.get("output_node"):
            unresolved.append(f"legacy chain bridge {index} cannot seed a public output")
            continue
        output_type, access, cardinality = _split_legacy_type(
            bridge.get("output_type")
        )
        base_name = _public_name(str(bridge.get("output_port", "")), f"output_{index}")
        name = base_name
        suffix = 2
        while name in outputs:
            name = f"{base_name}_{suffix}"
            suffix += 1
        outputs[name] = {
            "node": bridge.get("output_node"),
            "port": bridge.get("output_port"),
            "type": output_type,
            "access": access,
            "cardinality": cardinality,
            "description": bridge.get("note", "Migrated legacy chain output."),
        }

    if not outputs:
        unresolved.append("at least one public output must be selected")
    if recipe.get("chain_bridges"):
        unresolved.append(
            "legacy chain_bridges need target public inputs and reviewed adapter pipelines"
        )

    parameters = deepcopy(recipe.get("parameters", {}))
    for spec in parameters.values():
        if isinstance(spec, dict) and "desc" in spec and "description" not in spec:
            spec["description"] = spec.pop("desc")

    draft = {
        "$schema": "../../schemas/recipe-v2.schema.json",
        "schema_version": 2,
        "id": recipe.get("id"),
        "name": recipe.get("name"),
        "description": recipe.get("description", ""),
        "tags": deepcopy(recipe.get("tags", [])),
        "interface": {
            "parameters": parameters,
            "inputs": inputs,
            "outputs": outputs,
        },
        "composable_with": deepcopy(recipe.get("composable_with", [])),
        "composition_rules": [],
        "verified": bool(recipe.get("verified", False)),
        "verified_date": recipe.get("verified_date"),
        "test_case": recipe.get("test_case", ""),
    }
    return {
        "recipe_id": recipe.get("id"),
        "source_version": 1,
        "target_version": 2,
        "ready": not unresolved,
        "unresolved": unresolved,
        "draft": draft,
    }
