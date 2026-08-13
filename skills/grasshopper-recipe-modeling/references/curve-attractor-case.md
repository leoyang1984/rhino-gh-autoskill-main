# MCP case: curve-attractor modules

## User intent

Create a field of square modules whose size responds continuously to distance from an attractor curve.

## Reused knowledge

Start from `attractor-remap` rather than planning from zero. Reuse:

- site `Rectangle → Boundary Surfaces → Divide Surface`;
- `Bounds → Construct Domain → Remap Numbers`;
- the public grid, size, and remap parameters;
- existing component GUIDs and recorded port names.

## Topology delta

Replace the point attractor lane:

```text
AttrX + AttrY → Construct Point → Distance
```

with a curve lane:

```text
CurveCenterX + CurveCenterY
  → Construct Point
  → XY Plane
  → Circle

Flattened grid points + Circle
  → Curve Closest Point.Distance
```

Add the output lane:

```text
Remap Numbers.Mapped
  → module Rectangle.X Size
  → module Rectangle.Y Size

Flattened grid points
  → XY Plane
  → module Rectangle.Plane
```

Useful stock component GUIDs from the tested Rhino 8 environment:

| Component | GUID |
|---|---|
| XY Plane | `17b7152b-d30d-4d50-b9ef-c9fe25576fc2` |
| Circle | `807b86e3-be8d-4970-92b5-f8cdcb45b06b` |
| Curve Closest Point | `2dc44b22-b1dd-460a-a704-6462d6e91096` |
| Flatten Tree | `f80cfe18-9510-4b89-8301-8e58faf423bb` |

Search the live component library if any GUID fails on another installation.

## Tested baseline

- Site: `20000 × 20000 mm`
- Grid count: `12 × 12` divisions, yielding `(12 + 1)² = 169` points
- Attractor: circle centered at `(10000, 10000)` with radius `6000 mm`
- Near module size: `1200 mm`
- Far module size: `180 mm`
- Final graph: 20 objects and 24 wires

## Structural result

After adding `Flatten Tree`:

- flattened points: 1 branch, 169 items;
- curve distances: 1 branch, 169 items;
- global source domain: 1 branch, `9.252126 to 8142.135624 mm`;
- mapped sizes: 1 branch, 169 items within `1200 to 180 mm`;
- output modules: 1 branch, 169 rectangles;
- component messages: empty.

## Lesson promoted into the Skill

The original Recipe reached `Bounds` with 13 branches, producing 13 row-relative domains. The graph solved and produced 169 modules, so placement success and output count alone did not reveal the semantic error. Always audit branch shape around `Bounds`, remapping, and list matching.
