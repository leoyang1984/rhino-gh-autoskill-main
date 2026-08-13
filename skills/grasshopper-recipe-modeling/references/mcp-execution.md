# Rhino MCP execution and audit

## Tool sequence

Use the current Rhino MCP equivalents of this sequence:

1. `list_slots`
2. `get_context`
3. `g1_start`
4. `g1_get_canvas_graph(include_data=false)`
5. `g1_apply_graph`
6. `g1_solve_graph`
7. `g1_get_canvas_graph(include_data=true)`

Use the exact slot ID throughout.

Router slots are not proof of Grasshopper isolation. If two slots report the same Rhino PID, assume they may share the single GH1 editor and canvas until verified otherwise. Starting Grasshopper from the second slot can replace the first slot's active canvas. Prefer the already-grounded slot or a truly separate Rhino process.

## Recipe-to-MCP mapping

| Wiring node | MCP descriptor |
|---|---|
| `Number Slider` | `{Key, Min, Value, Max, Type, Name, X, Y}` in `sliders` |
| Other node | `{Key, Selector: guid, X, Y}` in `components` |
| Connection | `{SrcKey, Src, DstKey, Dst}` in `wires` |

For a Number Slider or a pure GH parameter such as `Curve` or `Surface`, use an empty source selector (`Src: ""`). For regular components use the recorded output port name. Port matching is case-sensitive enough to treat the Recipe spelling as authoritative.

Prefer GUID selectors because names such as `Rectangle`, `Circle`, and `Surface` can be ambiguous.

## Bridge pitfalls (verified 2026-08-13 on router 0.2.1-wip)

- **`g1_apply_graph` numeric fields must be JSON floats.** An `X`/`Y`/`Min`/`Value`
  sent as an integer (e.g. `0` instead of `0.0`) raises
  `JsonException ... System.Single`. Always emit floats for positions and slider bounds.
- **`g1_connect_many` uses `SrcId`/`DstId` (object Guids), not the `Key` strings
  from `g1_apply_graph`.** Keys work only inside one `apply` call; connecting
  already-placed objects requires the returned `Id` per object.
- **A Number Slider or pure param is an `IGH_Param`: use empty `Src` (or `''`/`0`).**
  Passing a port name like `Number Slider` fails with
  `is a Param; expected '' or '0' for src`.
- **`g1_describe_component` is broken on this router build**
  (`An error occurred invoking ...` for both names and Guids). Fall back to
  `g1_place_component` (or `g1_apply_graph`) then read ports back from
  `g1_get_canvas_graph`.
- **GH previews are not Rhino document objects.** `get_viewport_image` reports
  an empty scene until the solved mesh is baked into the Rhino doc
  (e.g. via `run_python` + `RhinoDoc.Objects.AddMesh`). The image itself is in
  `content[1]` (`type: image`), while `content[0]` carries only metadata JSON.
- **`g1_clear_canvas` requires `confirm: true`** and is per active GH document;
  use it only when the whole canvas is owned by the current task.
- **Runtime slider writes from `run_python`:** `obj.Value` is not writable on a
  placed `GH_NumberSlider`; use `obj.Slider.Value = System.Decimal(...)` (see
  `docs/rhino8_python_rules.md` R7).

## Numerical audit (physics-style graphs)

Structural checks alone miss divergence. For Kangaroo/physics graphs also record:

- particle coordinate bounds (`Zmin/Zmax/Zmean` from `Solver.V` volatile data,
  not just the first sample rows — the first points are usually near anchors);
- solver iteration counter (`I`) — must stop growing at convergence;
- anchors pinned (corner particles within tolerance of their targets);
- deformation magnitude (e.g. cloth sag vs cloth size) matching parameter intent.


## Failure interpretation

`g1_apply_graph` is batch tolerant. One failure does not abort later operations. Inspect:

- `PlaceErrors` must be empty;
- every wire result must have `Ok: true`;
- `WiresOk` must equal the requested wire count.

After solving, inspect every object's `Messages`. Separate:

- placement or port failures;
- missing external inputs;
- type conversion failures;
- valid empty results caused by parameters;
- data-tree mismatches.

Do not repeatedly add corrective nodes on top of a partial scratch graph. When the graph is entirely owned by the current task, clear and rebuild it once. Never clear unrelated user work.

## Data-tree audit

For each critical lane, record `{Branches, Items, Sample}` from volatile data.

Check these invariants:

- geometry count equals factor/vector/plane count for one-to-one operations;
- a global domain has exactly one branch and one interval;
- paired inputs use compatible paths, not merely equal totals;
- a chain does not accidentally cross-product two lists;
- integer counts actually arrive as integers;
- remapped values stay within the target domain.

Also inspect geometry descriptions. An `Extrude` output reported as `Open Brep` is not a closed solid. If the request requires physical solids or volumes, add and verify `Cap Holes` rather than inheriting the Recipe's wording.

### Global versus per-branch mapping

`Bounds` computes independently per branch. If `Divide Surface` produces 13 branches and its distances reach `Bounds` unchanged, the result is 13 domains. This normalizes each row separately.

For a global attractor field:

```text
Divide Surface.Points
  → Flatten Tree
  → Curve Closest Point.Distance
  → Bounds (one domain)
  → Remap Numbers
```

Feed the same flattened point order to the module planes so the 169 values still align with the 169 modules.

For a row-relative field, preserve the branches and state that behavior explicitly.

## Change test

When parameter propagation matters:

1. capture baseline counts and representative samples;
2. change one dimension/count and one field parameter;
3. solve again;
4. verify expected outputs changed;
5. verify unrelated anchors and graph topology stayed fixed.

Use data evidence for structural validation and leave visual judgment to the user unless they explicitly request another method.

## Persist normalized audit evidence

Keep the raw `g1_apply_graph`, `g1_solve_graph`, and
`g1_get_canvas_graph(include_data=true)` responses, but normalize the fields
needed for decisions into `schemas/audit-evidence-v1.schema.json`. Record
requested and actual counts, place errors, every wire result, solve status,
object Messages, output metrics, and explicit assertions. Store session-local
JSON under `logs/audits/`, then run:

```bash
python3 skills/grasshopper-recipe-modeling/scripts/compile_recipe.py audit \
  --evidence <evidence.json> --output <audit.json>
```

Structural success does not set visual approval. Update
`visual_review.status` to `approved` only after the user actually approves the
Rhino/GH result, regenerate the audit, and use `admit` as a read-only readiness
check before changing Recipe knowledge.
