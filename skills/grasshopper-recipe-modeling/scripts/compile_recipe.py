#!/usr/bin/env python3
"""Inspect, validate, compose, and compile Grasshopper Recipe graphs for Rhino MCP.

The `compile` command emits an argument object accepted by `g1_apply_graph`.
The script uses only the Python standard library and does not call Rhino itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Direct execution puts this directory on sys.path, while importlib-based tests
# do not. Keep sibling helper imports stable in both modes without requiring the
# skill directory (whose parent contains a hyphen) to become a Python package.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from recipe_schema import (
    migration_preview,
    public_parameters,
    schema_version,
    validate_recipe_contract,
)
from graph_ir import (
    GraphIR,
    GraphIRError,
    emit_legacy_wiring,
    emit_mcp_payload,
    validate_graph_structure,
)
from type_check import (
    ComponentCatalog,
    ConnectionTypeResult,
    TypeRules,
    blocking_type_results,
    check_graph_types,
    summarize_types,
)
from composition import CompositionError, compose_recipe_pair
from health_check import validate_environment
from audit import admission_check, evaluate_audit


class RecipeError(ValueError):
    pass


def find_project_root(explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not (root / "recipes" / "index.json").is_file():
            raise RecipeError(f"No recipes/index.json under project root: {root}")
        return root

    starts = [Path.cwd().resolve(), Path(__file__).resolve()]
    for start in starts:
        for candidate in (start, *start.parents):
            if (candidate / "recipes" / "index.json").is_file():
                return candidate
    raise RecipeError("Could not locate a project root containing recipes/index.json")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RecipeError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RecipeError(f"Invalid JSON in {path}: {exc}") from exc


def load_index(root: Path) -> list[dict[str, Any]]:
    data = read_json(root / "recipes" / "index.json")
    if not isinstance(data, list):
        raise RecipeError("recipes/index.json must contain a JSON array")
    return data


def load_recipe(root: Path, recipe_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    known = {entry.get("id") for entry in load_index(root)}
    if recipe_id not in known:
        raise RecipeError(f"Unknown recipe id: {recipe_id}")
    folder = root / "recipes" / recipe_id
    recipe = read_json(folder / "recipe.json")
    wiring = read_json(folder / "wiring.json")
    return recipe, wiring


def parse_scalar(raw: str) -> int | float:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RecipeError(f"Parameter value must be a JSON number: {raw}") from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecipeError(f"Parameter value must be numeric: {raw}")
    return value


def parse_overrides(items: list[str]) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    for item in items:
        if "=" not in item:
            raise RecipeError(f"Expected --set name=value, received: {item}")
        name, raw = item.split("=", 1)
        name = name.strip()
        if not name:
            raise RecipeError(f"Empty parameter name in: {item}")
        result[name] = parse_scalar(raw.strip())
    return result


def compile_payload(
    recipe: dict[str, Any],
    wiring: dict[str, Any],
    overrides: dict[str, int | float],
    x_offset: float = 0,
    y_offset: float = 0,
    solve: bool = True,
) -> dict[str, Any]:
    try:
        graph = GraphIR.from_wiring(wiring)
        return emit_mcp_payload(
            graph,
            public_parameters(recipe),
            overrides,
            x_offset=x_offset,
            y_offset=y_offset,
            solve=solve,
        )
    except GraphIRError as exc:
        raise RecipeError(str(exc)) from exc


def validate_one(root: Path, recipe_id: str) -> list[str]:
    recipe, wiring = load_recipe(root, recipe_id)
    errors: list[str] = validate_recipe_contract(recipe, wiring)
    if recipe.get("id") != recipe_id:
        errors.append(f"recipe.json id is {recipe.get('id')!r}")
    try:
        graph = GraphIR.from_wiring(wiring)
        issues = validate_graph_structure(graph)
        errors.extend(issue.message for issue in issues if issue.severity == "error")
        if not any(issue.severity == "error" for issue in issues):
            emit_mcp_payload(graph, public_parameters(recipe), {})
    except (RecipeError, GraphIRError) as exc:
        errors.append(str(exc))
    return errors


def command_list(root: Path, query: str | None) -> int:
    terms = [term.casefold() for term in (query or "").split() if term]
    for entry in load_index(root):
        haystack = " ".join(
            [
                str(entry.get("id", "")),
                str(entry.get("name", "")),
                str(entry.get("description", "")),
                " ".join(map(str, entry.get("tags", []))),
            ]
        ).casefold()
        if terms and not all(term in haystack for term in terms):
            continue
        recipe, _ = load_recipe(root, str(entry["id"]))
        params = ",".join(public_parameters(recipe).keys()) or "-"
        print(f"{entry['id']}\t{entry.get('name', '')}\tparams={params}")
    return 0


def command_compile(root: Path, args: argparse.Namespace) -> int:
    recipe, wiring = load_recipe(root, args.recipe_id)
    overrides = parse_overrides(args.set)
    try:
        graph = GraphIR.from_wiring(wiring)
    except GraphIRError as exc:
        raise RecipeError(str(exc)) from exc
    type_results, catalog = type_check_graph(root, graph)
    blocked = blocking_type_results(type_results, strict=args.strict_types)
    if blocked:
        first = blocked[0]
        raise RecipeError(
            f"type check {first.status} at connection {first.index}: "
            f"{first.source_type or '?'} -> {first.target_type or '?'}; {first.reason}"
        )
    if args.type_report:
        print_type_report(type_results, catalog, stream=sys.stderr, details=True)
    if args.emit == "mcp":
        payload = compile_payload(
            recipe,
            wiring,
            overrides,
            x_offset=args.x_offset,
            y_offset=args.y_offset,
            solve=not args.no_solve,
        )
    else:
        try:
            payload = emit_legacy_wiring(
                graph,
                public_parameters(recipe),
                overrides,
                x_offset=args.x_offset,
                y_offset=args.y_offset,
            )
        except GraphIRError as exc:
            raise RecipeError(str(exc)) from exc
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


def type_check_graph(
    root: Path, graph: GraphIR
) -> tuple[list[ConnectionTypeResult], ComponentCatalog]:
    catalog = ComponentCatalog.load(root)
    rules = TypeRules.load(root)
    return check_graph_types(graph, catalog, rules), catalog


def print_type_report(
    results: list[ConnectionTypeResult],
    catalog: ComponentCatalog,
    stream: Any = sys.stdout,
    details: bool = False,
) -> None:
    summary = summarize_types(results)
    counts = ", ".join(f"{name}={count}" for name, count in summary.items())
    known = len(results) - summary["UNKNOWN"]
    coverage = 100.0 if not results else known * 100.0 / len(results)
    print(
        f"types[{catalog.source}; complete={str(catalog.complete).lower()}]: "
        f"{counts}; coverage={coverage:.1f}%",
        file=stream,
    )
    if details:
        for result in results:
            if result.status in {"EXACT", "KNOWN_CAST"}:
                continue
            print(
                f"  {result.status:12} connection {result.index}: "
                f"{result.source_node}.{result.source_port} "
                f"({result.source_type or '?'}) -> "
                f"{result.target_node}.{result.target_port} "
                f"({result.target_type or '?'}): {result.reason}",
                file=stream,
            )


def command_validate_wiring(root: Path, args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    if not path.is_absolute():
        path = root / path
    try:
        graph = GraphIR.from_wiring(read_json(path))
    except GraphIRError as exc:
        raise RecipeError(str(exc)) from exc
    issues = validate_graph_structure(graph)
    for issue in issues:
        print(f"{issue.severity.upper():7} {issue.code}: {issue.message} [{issue.path}]")
    type_results, catalog = type_check_graph(root, graph)
    type_blocked = blocking_type_results(type_results, strict=args.strict_types)
    errors = sum(issue.severity == "error" for issue in issues) + len(type_blocked)
    warnings = sum(issue.severity == "warning" for issue in issues)
    print_type_report(
        type_results,
        catalog,
        details=args.type_details or bool(type_blocked),
    )
    print(
        f"Validated wiring: {len(graph.nodes)} nodes, "
        f"{len(graph.connections)} connections; errors={errors}, warnings={warnings}"
    )
    return 1 if errors else 0


def command_migrate(root: Path, args: argparse.Namespace) -> int:
    if not args.dry_run:
        raise RecipeError(
            "Migration is preview-only in this phase; pass --dry-run. "
            "No Recipe files will be modified."
        )
    ids = (
        [args.recipe_id]
        if args.recipe_id
        else [str(entry["id"]) for entry in load_index(root)]
    )
    previews = []
    for recipe_id in ids:
        recipe, wiring = load_recipe(root, recipe_id)
        previews.append(migration_preview(recipe, wiring))
    result: Any = previews[0] if args.recipe_id else previews
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


def command_compose(root: Path, args: argparse.Namespace) -> int:
    try:
        wiring = compose_recipe_pair(
            root, args.source_recipe, args.target_recipe, rule_id=args.rule
        )
        graph = GraphIR.from_wiring(wiring)
    except (CompositionError, GraphIRError, KeyError) as exc:
        raise RecipeError(str(exc)) from exc
    type_results, catalog = type_check_graph(root, graph)
    blocked = blocking_type_results(type_results, strict=args.strict_types)
    if blocked:
        first = blocked[0]
        raise RecipeError(
            f"composed graph type check {first.status} at connection {first.index}: "
            f"{first.source_type or '?'} -> {first.target_type or '?'}; {first.reason}"
        )
    if args.type_report:
        print_type_report(type_results, catalog, stream=sys.stderr, details=True)
    if args.emit == "wiring":
        payload = wiring
    else:
        try:
            payload = emit_mcp_payload(graph, {}, {}, solve=not args.no_solve)
        except GraphIRError as exc:
            raise RecipeError(str(exc)) from exc
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


def resolve_project_path(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else root / path


def command_health(root: Path, args: argparse.Namespace) -> int:
    snapshot_path = resolve_project_path(root, args.snapshot)
    snapshot = read_json(snapshot_path)
    baseline_path: Path | None = None
    if args.baseline:
        baseline_path = resolve_project_path(root, args.baseline)
    else:
        default_baseline = root / "data" / "reference" / "component_snapshot.json"
        if default_baseline.is_file():
            baseline_path = default_baseline
    baseline = read_json(baseline_path) if baseline_path else None

    indexed_ids = [str(entry["id"]) for entry in load_index(root)]
    recipe_ids = args.recipe or indexed_ids
    unknown = sorted(set(recipe_ids) - set(indexed_ids))
    if unknown:
        raise RecipeError(f"Unknown recipe id(s): {', '.join(unknown)}")
    try:
        report = validate_environment(root, snapshot, recipe_ids, baseline)
    except (GraphIRError, KeyError, TypeError, ValueError) as exc:
        raise RecipeError(f"Health validation failed: {exc}") from exc

    output_path: Path | None = None
    if not args.no_write:
        if args.output:
            output_path = resolve_project_path(root, args.output)
        else:
            stamp = report["generated_at"].replace(":", "-").replace("+", "_")
            output_path = root / "logs" / "health" / f"health-{stamp}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report["report_path"] = str(output_path)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 1 if report["summary"]["ERROR"] else 0


def write_generated_report(
    root: Path,
    report: dict[str, Any],
    output: str | None,
    no_write: bool,
    folder: str,
    prefix: str,
) -> None:
    if no_write:
        return
    if output:
        path = resolve_project_path(root, output)
    else:
        stamp = report["generated_at"].replace(":", "-").replace("+", "_")
        path = root / "logs" / folder / f"{prefix}-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_audit(root: Path, args: argparse.Namespace) -> int:
    evidence = read_json(resolve_project_path(root, args.evidence))
    if not isinstance(evidence, dict):
        raise RecipeError("Audit evidence must be a JSON object")
    try:
        report = evaluate_audit(evidence)
    except (KeyError, TypeError, ValueError) as exc:
        raise RecipeError(f"Audit evidence is malformed: {exc}") from exc
    write_generated_report(root, report, args.output, args.no_write, "audits", "audit")
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 1 if not report["structural_pass"] else 0


def command_admit(root: Path, args: argparse.Namespace) -> int:
    report = read_json(resolve_project_path(root, args.audit))
    if not isinstance(report, dict) or report.get("audit_report_version") != 1:
        raise RecipeError("--audit must point to an audit report v1")
    indexed = args.recipe_id in {str(item.get("id")) for item in load_index(root)}
    errors = validate_one(root, args.recipe_id) if indexed else []
    result = admission_check(args.recipe_id, errors, indexed, report)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0 if result["ready"] else 1


def command_validate(root: Path, args: argparse.Namespace) -> int:
    ids = [args.recipe_id] if args.recipe_id else [str(e["id"]) for e in load_index(root)]
    failed = 0
    for current in ids:
        errors = validate_one(root, current)
        recipe, wiring = load_recipe(root, current)
        try:
            graph = GraphIR.from_wiring(wiring)
            type_results, catalog = type_check_graph(root, graph)
            blocked = blocking_type_results(type_results, strict=args.strict_types)
            errors.extend(
                f"type {result.status} at connection {result.index}: "
                f"{result.source_type or '?'} -> {result.target_type or '?'}"
                for result in blocked
            )
        except (GraphIRError, FileNotFoundError, json.JSONDecodeError) as exc:
            type_results = []
            blocked = []
            catalog = ComponentCatalog("none", False, {})
            errors.append(f"type check unavailable: {exc}")
        if errors:
            failed += 1
            print(f"FAIL {current}: {'; '.join(errors)}")
        else:
            payload = compile_payload(recipe, wiring, {})
            print(
                f"OK   {current}: {len(payload['sliders'])} sliders, "
                f"{len(payload['components'])} components, {len(payload['wires'])} wires"
            )
        print_type_report(
            type_results,
            catalog,
            details=args.type_details or bool(blocked),
        )
    print(f"Validated {len(ids)} recipe(s); failures={failed}")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and compile Grasshopper Recipes for Rhino MCP"
    )
    parser.add_argument(
        "--project-root",
        help="Project root containing recipes/index.json (normally auto-detected)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List all Recipe summaries")
    list_parser.add_argument("query", nargs="?", help="Optional all-terms text filter")

    search_parser = subparsers.add_parser("search", help="Search Recipe summaries")
    search_parser.add_argument("query", help="All-terms text filter")

    compile_parser = subparsers.add_parser(
        "compile", help="Emit a g1_apply_graph argument object"
    )
    compile_parser.add_argument("recipe_id")
    compile_parser.add_argument(
        "--set", action="append", default=[], metavar="NAME=VALUE"
    )
    compile_parser.add_argument("--x-offset", type=float, default=0)
    compile_parser.add_argument("--y-offset", type=float, default=0)
    compile_parser.add_argument("--no-solve", action="store_true")
    compile_parser.add_argument(
        "--emit",
        choices=("mcp", "wiring"),
        default="mcp",
        help="Output an MCP payload (default) or validated legacy wiring JSON",
    )
    compile_parser.add_argument("--strict-types", action="store_true")
    compile_parser.add_argument(
        "--type-report",
        action="store_true",
        help="Write advisory type details to stderr while keeping stdout valid JSON",
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Validate one Recipe or the full indexed library"
    )
    validate_parser.add_argument("recipe_id", nargs="?")
    validate_parser.add_argument("--strict-types", action="store_true")
    validate_parser.add_argument("--type-details", action="store_true")

    validate_wiring_parser = subparsers.add_parser(
        "validate-wiring", help="Validate a standalone or AI-planned wiring JSON file"
    )
    validate_wiring_parser.add_argument("path")
    validate_wiring_parser.add_argument("--strict-types", action="store_true")
    validate_wiring_parser.add_argument("--type-details", action="store_true")

    migrate_parser = subparsers.add_parser(
        "migrate", help="Preview a Recipe schema v2 migration without writing files"
    )
    migrate_parser.add_argument("recipe_id", nargs="?")
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required safety flag; print the migration draft and unresolved decisions",
    )

    compose_parser = subparsers.add_parser(
        "compose", help="Compose two Recipe v2 graphs through a public rule"
    )
    compose_parser.add_argument("source_recipe")
    compose_parser.add_argument("target_recipe")
    compose_parser.add_argument("--rule")
    compose_parser.add_argument(
        "--emit", choices=("mcp", "wiring"), default="mcp"
    )
    compose_parser.add_argument("--no-solve", action="store_true")
    compose_parser.add_argument("--strict-types", action="store_true")
    compose_parser.add_argument("--type-report", action="store_true")

    health_parser = subparsers.add_parser(
        "health",
        help="Validate a saved Grasshopper environment snapshot offline",
    )
    health_parser.add_argument(
        "--snapshot",
        required=True,
        help="Current snapshot exported by scripts/scan_gh_components.py",
    )
    health_parser.add_argument(
        "--baseline",
        help="Optional reviewed reference snapshot (defaults to data/reference when present)",
    )
    health_parser.add_argument(
        "--recipe",
        action="append",
        help="Limit validation to one Recipe id; repeat for several",
    )
    health_parser.add_argument(
        "--output",
        help="Report path (default: timestamped JSON under logs/health)",
    )
    health_parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the report without writing a machine-local JSON file",
    )

    audit_parser = subparsers.add_parser(
        "audit", help="Evaluate normalized evidence from a live MCP solve"
    )
    audit_parser.add_argument("--evidence", required=True)
    audit_parser.add_argument(
        "--output", help="Report path (default: timestamped JSON under logs/audits)"
    )
    audit_parser.add_argument("--no-write", action="store_true")

    admit_parser = subparsers.add_parser(
        "admit", help="Check whether a Recipe has static, dynamic, and visual evidence"
    )
    admit_parser.add_argument("recipe_id")
    admit_parser.add_argument("--audit", required=True, help="Audit report v1 JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        root = find_project_root(args.project_root)
        if args.command in {"list", "search"}:
            return command_list(root, getattr(args, "query", None))
        if args.command == "compile":
            return command_compile(root, args)
        if args.command == "validate":
            return command_validate(root, args)
        if args.command == "migrate":
            return command_migrate(root, args)
        if args.command == "validate-wiring":
            return command_validate_wiring(root, args)
        if args.command == "compose":
            return command_compose(root, args)
        if args.command == "health":
            return command_health(root, args)
        if args.command == "audit":
            return command_audit(root, args)
        if args.command == "admit":
            return command_admit(root, args)
        parser.error(f"Unknown command: {args.command}")
    except RecipeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
