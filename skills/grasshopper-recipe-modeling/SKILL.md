---
name: grasshopper-recipe-modeling
description: Build, extend, compose, and audit editable Grasshopper 1 definitions in Rhino 8 through Rhino MCP by reusing this project's verified Recipe library and wiring JSON. Use when Codex needs to turn a natural-language request into a parameterized GH canvas, apply one or more existing massing, facade, array, attractor, or terrain recipes, adapt a near-match recipe, inspect GH solution data, or prepare a newly verified topology for Recipe admission. Do not use for Grasshopper 2, purely manual canvas editing, or RhinoCommon-only models that do not need an editable GH definition.
---

# Grasshopper Recipe Modeling

Treat the project Recipe library as the geometry knowledge layer and Rhino MCP as the execution layer. Reuse verified topology before planning a new graph.

## Locate the project

Find the nearest ancestor containing `recipes/index.json`. Treat it as `PROJECT_ROOT`. Read project files relative to that root; never rely on hard-coded `/Users/...` paths.

Use the bundled compiler without reading its source:

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py search "<intent words>"
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py compile <recipe-id> \
  --set parameter=value
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py compose \
  <source-recipe-id> <target-recipe-id>
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py health \
  --snapshot data/component_library.json
```

The compile command prints a `g1_apply_graph` argument object. It validates parameter names and slider ranges before emitting the payload.
The health command only validates a previously collected snapshot; it never
claims access to the live Grasshopper runtime from ordinary Python.

## Choose the topology path

1. Search the compact index before opening any wiring files.
2. For one strong match, read only that Recipe's `recipe.json` and compile its `wiring.json`.
3. For a partial match, compile the closest Recipe, then describe the intended delta before adding, removing, or rewiring nodes.
4. For multiple causally related intents, read both Recipe v2 public interfaces and the source Recipe's `composition_rules`. Use the compiler's `compose` command instead of manually referencing internal node ids. Read [references/project-contract.md](references/project-contract.md) for composition rules.
5. When no Recipe is close, search the live GH component library with MCP and plan the smallest complete graph. Do not invent GUIDs or port names.

Prefer geometric chaining over parallel, visually unrelated graphs. Share a parameter once and fan it out when two branches must stay coordinated.

## Ground the Rhino session

1. List Rhino slots.
2. If no slot exists, spawn a Rhino 8 scratch slot. If several exist, identify the target explicitly instead of assuming the active window.
3. Get context, start Grasshopper, and inspect the existing canvas graph.
4. Pass the same explicit `slot` to every subsequent Rhino MCP call.
5. Never clear a non-empty canvas unless the user explicitly asked to replace it. In an existing canvas, offset new nodes beyond its current bounds.

Compare slot process IDs. Multiple router slots backed by the same Rhino PID may share one Grasshopper canvas; a newly spawned slot is not an isolated GH sandbox in that case. Do not start or clear Grasshopper in one such slot while preserving another slot's canvas matters.

Maintain one writer per GH canvas. Do not mutate unrelated Rhino document objects.

## Build through MCP

For an unchanged single Recipe:

1. Compile it with any user parameter overrides.
2. Pass `components`, `sliders`, `wires`, and `solve` to `g1_apply_graph` in one call.
3. Treat `PlaceErrors`, failed per-wire results, or a lower `WiresOk` count as build failures even if the tool call itself succeeded.

For a partial match, composition, or new graph:

1. Use Recipe GUIDs and ports for the reused subgraph.
2. Use `g1_search_components` for missing components.
3. Use `g1_describe_component` before wiring an unfamiliar component. If a name is ambiguous, place it by GUID.
4. Build in one `g1_apply_graph` call when possible. Use `g1_connect_many` only for a small corrective batch.
5. Solve once after the batch.

Read [references/mcp-execution.md](references/mcp-execution.md) before adapting topology, composing Recipes, or diagnosing a failed graph.

## Audit the solved graph

Always call `g1_solve_graph`, then call `g1_get_canvas_graph` with `include_data=true`. Do not accept successful placement as proof of successful geometry.

Check:

- actual component and wire counts against the requested payload;
- every object's `Messages` for errors or warnings;
- required outputs for nonzero branch and item counts;
- list lengths at paired geometry/parameter inputs;
- expected numerical domains and sample values;
- tree shape before `Bounds`, `Remap Numbers`, list matching, or per-module transforms.

Use one global branch when the design requires a global min/max. Insert `Flatten Tree` before `Bounds` and keep paired geometry in the same flattened order. Preserve branches when row-by-row or panel-by-panel behavior is intentional. Never flatten merely to silence an error.

Run a parameter-only change test when propagation is important: change at least one independent slider, solve again, and confirm the dependent output changes while unrelated invariants remain stable.

Report structural evidence compactly: object/wire counts, warnings, key output item counts, value ranges, and any unresolved external geometry inputs.

Normalize the live apply/solve/canvas responses according to
`schemas/audit-evidence-v1.schema.json`, keeping raw responses in its `raw`
field, then run `compile_recipe.py audit --evidence <path>`. A structurally
passing audit still has `visual_review.status: pending` until the user approves.

## Hand visual review to the user

After MCP/data validation, ask the user to inspect the Rhino and Grasshopper views. Do not use Computer Use for visual confirmation unless the user explicitly requests it. Do not claim visual correctness from data alone.

## Admit new knowledge deliberately

Do not modify `recipes/`, `knowledge/`, `planning/`, or `logs/` merely because a graph solved.

Only after the user visually approves the result and asks to retain it:

1. Save a stable `recipe.json` parameter contract and `wiring.json` topology.
2. Add a compact entry to `recipes/index.json`.
3. Record reusable type or chain behavior in the existing knowledge files.
4. Mark `verified: true` only for the exact topology and parameter behavior that were tested.
5. Re-run the compiler's `validate` command.

Before those writes, run the read-only readiness gate:

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py admit \
  <recipe-id> --audit <audit-report.json>
```

See [references/curve-attractor-case.md](references/curve-attractor-case.md) for the first MCP adaptation and the data-tree issue it exposed.

## Boundaries

- Build editable GH1 definitions; do not silently replace them with opaque RhinoCommon scripts.
- Treat external `Curve` and `Surface` parameter nodes as unresolved until referenced or supplied by an upstream Recipe.
- Do not claim `.gh` persistence unless a save operation actually succeeds.
- Do not claim structural adequacy, code compliance, fabrication readiness, or visual design quality.
