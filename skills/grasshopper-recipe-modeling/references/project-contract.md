# Project and Recipe contract

## Source hierarchy

Use these files in this order:

1. `recipes/index.json` — compact intent catalogue; read or search first.
2. `recipes/<id>/recipe.json` — schema v2 public interface, verified status, and composition metadata.
3. `recipes/<id>/wiring.json` — verified node and connection topology.
4. `knowledge/composition-patterns.md` — rationale and historical evidence behind public composition rules.
5. `knowledge/geometry-type-guide.md` — GH type compatibility and bridge components.
6. `data/hot_components.json` — fallback cache for common stock components.

The old `scripts/build_gh_file.py` and `scripts/scan_gh_components.py` implement the pre-MCP workflow. Keep them for compatibility; do not use them as the primary MCP execution path.

`scan_gh_components.py` is also the environment collector: run it inside a real
Rhino/Grasshopper process to produce `data/component_library.json`. Ordinary
Python never scans the GH runtime. Validate the saved snapshot offline with
`compile_recipe.py health --snapshot data/component_library.json`; machine
reports belong in `logs/health/`, while an intentionally reviewed shared
baseline belongs in `data/reference/component_snapshot.json`.

## Wiring schema

Each wiring file contains:

```json
{
  "description": "...",
  "nodes": [
    {
      "id": "n1",
      "guid": "component-guid",
      "name": "Number Slider",
      "nickname": "Width",
      "position": {"x": 0, "y": 0},
      "preset": {"value": 20000, "min": 5000, "max": 60000}
    }
  ],
  "connections": [
    {
      "from": {"node": "n1", "port": "Value"},
      "to": {"node": "n2", "port": "X Size"}
    }
  ]
}
```

## Recipe schema v2

Every Recipe declares a stable public interface independently from its internal
node ids:

```json
{
  "schema_version": 2,
  "interface": {
    "parameters": {
      "u_count": {
        "type": "integer",
        "default": 10,
        "node": "n3",
        "field": "value"
      }
    },
    "inputs": {
      "surface": {
        "type": "GH_Surface",
        "access": "item",
        "bindings": [
          {"node": "n8", "port": "Domain", "mode": "replace"},
          {"node": "n9", "port": "Surface", "mode": "replace"}
        ]
      }
    },
    "outputs": {
      "panels": {
        "node": "n11",
        "port": "Geometry",
        "type": "IGH_GeometricGoo",
        "access": "tree"
      }
    }
  }
}
```

Public names such as `surface` and `panels` are the cross-Recipe API. The
`node` and `port` values inside a Recipe are private bindings and may change as
long as the public contract and behavior remain stable.

An input with `mode: "replace"` tells the future composer to remove the
Recipe's self-generated source wire at that target before connecting upstream
data. One public input may bind to several internal targets.

The compiler supports `field: "value"` for public parameters. Unversioned
legacy Recipe documents are still readable as v1, but the checked-in library
uses schema v2 and `composition_rules` exclusively.

## Composition rule

A rule binds stable public outputs to stable target inputs or parameters:

```json
{
  "id": "profiles_to_facade_grid",
  "target_recipe": "facade-grid",
  "bindings": [
    {
      "from_output": "profile_curves",
      "to": {"input": "surface"},
      "adapters": [
        {
          "selector": "a7a41d0a-2188-4f7a-82cc-1a2c4e4ec850",
          "input_port": "Curves",
          "output_port": "Loft",
          "parameters": {}
        }
      ]
    }
  ]
}
```

The composer namespaces both graphs, removes the target Recipe's replaced
self-generated prefix, inserts the adapter pipeline, replaces public parameter
Sliders when requested, and validates the combined graph before emitting MCP or
legacy wiring JSON.

## Recipe selection

- Match the user's nouns and operations against `name`, `description`, and `tags`.
- Prefer one verified Recipe that covers the causal core over several loosely related Recipes.
- Treat parameter differences as overrides, not new topology.
- Treat a different attractor type, bridge, input geometry, or final operation as a topology delta.
- When the request contains "first A, then apply B to it", prefer a chain rather than two independent graphs.

## Composition rules

### Geometric chains

- Curve list → `Loft` → Surface.
- Brep → `Deconstruct Brep` → `List Item` → Surface.
- Brep list → `List Item` → `Deconstruct Brep` → `List Item` → Surface.
- Surface → Surface may connect directly.

Remove the downstream Recipe's self-generated input prefix when an upstream Recipe supplies that geometry. Preserve the downstream processing core. Expose face, tier, or item selection as a slider rather than hard-coding it.

### Parameter chains

- Number list → a geometry factor can connect directly when list lengths match.
- Shared dimensions should use one slider feeding both branches.
- Match tree paths and item counts, not only total counts.

### Collision rules when merging graphs

- Prefix node keys with the Recipe ID or another short namespace.
- Offset downstream nodes to the right of upstream nodes.
- Deduplicate shared sliders deliberately.
- Rewrite every connection to the new namespaced keys.
- Use the recorded `composition_rules` before inventing a new bridge.

## External geometry

Some Recipes contain `Curve` or `Surface` parameter nodes. Placement succeeds without referenced Rhino geometry, but solving may produce warnings or zero output. Report these as required user/upstream inputs rather than topology failures.

When an upstream Recipe supplies the required type, replace the external parameter node with the upstream connection. Otherwise ask the user to reference the geometry in Grasshopper.

## Verification status

`verified: true` means the legacy topology was visually tested in its recorded environment. It does not prove:

- every plugin exists on the current machine;
- MCP port selectors still match the installed GH build;
- external geometry has been supplied;
- data-tree behavior is correct for a new composition;
- visual intent is satisfied for new parameters.

Always perform a live MCP audit.
