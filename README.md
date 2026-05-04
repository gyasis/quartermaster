# Quartermaster

Auto-split prints that exceed your build plate, with the right joinery for the stock thickness.

## What it does

Take a model too big for your printer's build plate. Drop a cut-plane helper into the scene, drag it to the seam location, click **Cut Along Plane**. Quartermaster:

1. Bakes the modifier stack of the target so the cut acts on what you see, not the raw mesh
2. Measures the stock thickness and seam length at the cut location
3. Picks the appropriate joint family from a 2-axis decision matrix
4. Generates the joinery (cut surface + alignment pins or a tabled lock step)
5. Splits the model into two halves with the joinery baked in

## Joint matrix

|                          | Short seam (< 100 mm) | Medium (100-300 mm)            | Long (> 300 mm)         |
|--------------------------|-----------------------|--------------------------------|-------------------------|
| **< 3 mm thickness**     | scarf 12:1            | scarf 12:1 + pins              | scarf 12:1 + 3-4 pins   |
| **3-5 mm**               | dovetail              | **scarf 8:1 + pins** _(default)_ | finger joint            |
| **5-8 mm**               | dovetail              | finger / box                   | finger / box            |
| **>= 8 mm**              | box                   | sliding dovetail               | sliding dovetail        |

Optional **tabled (locked) scarf**: adds a perpendicular step at mid-thickness — provides mechanical lock against in-plane pull and self-registers during glue-up.

## Architecture

```
src/quartermaster/
├── joint_strategy.py    # picker brain — the 2-axis matrix above
├── plane.py             # CutPlane abstraction (plane-agnostic; thickness derived from cut orientation)
├── joints/
│   └── scarf.py         # cut-path generation (smooth or tabled), pin distribution
└── blender/
    ├── adapter.py       # Empty-as-cut-plane + evaluated-mesh handling
    ├── cut.py           # pipeline: read empty -> measure -> pick -> cut
    ├── operators.py     # Add Test Block, Add Cut Plane, Cut Along Plane
    ├── panel.py         # N-panel UI ("Quartermaster" tab in 3D Viewport)
    └── fixtures.py      # parametric test-block fixture
```

The `joint_strategy` and `joints/` modules are bpy-free — they import only stdlib and run in plain pytest. Only the `blender/` subpackage imports `bpy`.

## Development

```sh
uv run --with pytest pytest -v
```

## Using inside Blender

```python
import sys
sys.path.insert(0, "/path/to/quartermaster/src")
import quartermaster.blender
quartermaster.blender.register()
```

Look for the **Quartermaster** tab in the 3D viewport's N-panel (press `N` if hidden).

Workflow:

1. **Add Test Block** — drops a clean 300×200×4 mm cuboid (skip if you have your own model)
2. **Add Cut Plane** — places `QM_CutPlane` Empty with transform gizmos active
3. Drag the gizmo arrows or press G/R to position the cut
4. Optional: enable **Locked (tabled) joint** for mechanical lock
5. Select the target mesh, click **Cut Along Plane**

Re-running step 5 cleanly removes prior `_L`/`_R`/`_baked` outputs and re-cuts. Idempotent.

## Status

v0.0.1. Implemented:

- Picker (full 2-axis matrix, viable-set monotonicity, manual override, JSON serialization)
- `CutPlane` abstraction (plane-agnostic — works for any cut orientation)
- Scarf joint (smooth and tabled variants)
- Blender add-on (operators + N-panel + transform gizmos)
- 57 unit tests + Blender smoke test (`scripts/blender_smoke.py`)

Next:

- More joints: `joints/dovetail.py`, `joints/finger.py`, `joints/half_lap.py`
- `table_mm` slider in panel for fine-tuning the lock step
- "Snap cut plane to active object's long axis" button
- Multi-object union before cutting (for assemblies with separate features)
- Headless CI for Blender integration tests
