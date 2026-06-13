# Workflow Tutorials

This chapter walks you through ten complete, self-contained tutorials. Each tutorial builds a real workflow from scratch and shows exactly which nodes to use, how to wire them, and what to expect in the log panel. All examples use the built-in node set unless explicitly noted.

---

## Tutorial 1: Basic File Renaming Workflow

**Goal:** Load a list of filenames from a folder, apply a naming convention (lowercase with underscores), and rename every file on disk. Print a summary when done.

### Nodes Used

| Node | Role |
|------|------|
| Python Script | List all files in a folder |
| ForEach | Iterate over each filename |
| String Lower | Convert each name to lowercase |
| Python Script (inner) | Replace spaces with underscores, rename file |
| Console Print | Report result |

### Step-by-Step Build

**1. Create the entry Python Script node**

Open the Node Library (left panel) and drag a **Python Script** node onto the canvas. This will be the entry point — it fires first when you click Run.

In the node's code editor paste:

```python
import os

folder = inputs.get("data", "")
if not folder or not os.path.isdir(folder):
    result = []
else:
    result = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ]
```

Set the folder path as the default value on the `data` port (in the node's parameter editor). Connect `exec_out` to the ForEach node.

**2. ForEach node**

Drag a **ForEach** node onto the canvas. Connect:
- `result` output → ForEach `items` input
- Python Script `exec_out` → ForEach `exec_in`

ForEach fires its `loop_exec_out` once per item, passing the current item on the `current_item` port.

**3. String Lower node**

Drag **String Lower**. Connect:
- ForEach `current_item` → String Lower `string` input

This converts the full path to lowercase. However, we only want to lowercase the filename, not the whole path. Use a Python Script node instead:

```python
import os

full_path = inputs.get("data", "")
folder = os.path.dirname(full_path)
old_name = os.path.basename(full_path)

new_name = old_name.lower().replace(" ", "_")
new_path = os.path.join(folder, new_name)

result = {"old_path": full_path, "new_path": new_path, "new_name": new_name}
```

**4. Rename Python Script node**

Add another Python Script node. Wire the transform script's `result` → this node's `data` input:

```python
import os

info = inputs.get("data", {})
old_path = info.get("old_path", "")
new_path = info.get("new_path", "")

if old_path and new_path and old_path != new_path:
    try:
        os.rename(old_path, new_path)
        result = f"Renamed: {old_path} -> {new_path}"
    except OSError as e:
        result = f"ERROR: {e}"
else:
    result = f"Skipped (no change): {old_path}"
```

**5. Console Print**

Connect the `result` output to a **Console Print** node. Wire the rename node's `exec_out` back to the ForEach `loop_exec_in` to continue the loop.

**6. Final summary**

Connect ForEach `exec_out` (fires after the loop completes) to a Console Print with the message `"Renaming complete."`.

### Running the Workflow

Set the folder path as the default value on the entry node's `data` port (or wire it from an upstream node). Click **Run**. Watch the log panel — each rename or skip appears in sequence.

---

## Tutorial 2: Data Transformation Pipeline

**Goal:** Read a JSON file containing records (e.g., a list of people with names and birthdates), transform the data (uppercase names, reformat dates), and write the result to a new JSON file. Log a summary.

### Nodes Used

| Node | Role |
|------|------|
| File Load | Read source JSON |
| JSON Parse | Decode file content |
| Python Script | Transform records |
| File Save | Write output JSON |
| Console Print | Log summary |

### Step-by-Step Build

**1. File Load**

Drag **File Load** onto the canvas. Set `file_path` to your source JSON file (e.g., `people.json`). The `content` output carries the raw text.

**2. JSON Parse**

Connect `File Load.content` → `JSON Parse.json_string`. The `data` output is the decoded Python object (list or dict).

**3. Transform Python Script**

```python
import json
from datetime import datetime

records = inputs.get("data", [])
transformed = []

for record in records:
    new_record = dict(record)

    # Uppercase the name field
    if "name" in new_record:
        new_record["name"] = str(new_record["name"]).upper()

    # Reformat birthdate from YYYY-MM-DD to DD/MM/YYYY
    if "birthdate" in new_record:
        try:
            dt = datetime.strptime(new_record["birthdate"], "%Y-%m-%d")
            new_record["birthdate"] = dt.strftime("%d/%m/%Y")
        except ValueError:
            pass  # leave malformed dates untouched

    transformed.append(new_record)

result = json.dumps(transformed, indent=2)
```

**4. File Save**

Connect the transform script's `result` → `File Save.content`. Set `file_path` to `people_transformed.json`. Wire `exec_out` chain through.

**5. Console Print**

Add another **Python Script** node. Wire the transform script's `result` → its `data` input to build a summary:

```python
import json
json_str = inputs.get("data", "[]")
try:
    count = len(json.loads(json_str))
except Exception:
    count = 0
result = f"Transformation complete. {count} records processed."
```

Then connect `result` → Console Print.

### Key Points

- JSON Parse handles both list-of-dicts and plain dicts.
- All transform logic lives in one Python Script node, making it easy to add or remove transformation steps.
- File Save overwrites the target file. To write alongside the original, compute the output path dynamically.

---

## Tutorial 3: Conditional Execution (If/Else Logic)

**Goal:** Check whether a numeric value exceeds a threshold. Route execution to an "above threshold" branch or a "below threshold" branch. Both branches converge at a final log node.

### Nodes Used

| Node | Role |
|------|------|
| Python Script | Compute or receive the value |
| Python Script | Evaluate condition → bool |
| TwoWaySwitch | Route exec based on bool |
| Console Print (×2) | Branch-specific messages |
| Console Print | Final convergence message |

### Step-by-Step Build

**1. Source value**

```python
# Simulated: in practice this could come from a file, API, etc.
result = {"value": 87.3, "threshold": 75.0}
```

**2. Condition evaluator**

Wire the source script's `result` → this node's `data` input:

```python
data = inputs.get("data", {})
value = data.get("value", 0.0)
threshold = data.get("threshold", 0.0)
result = value > threshold
```

**3. TwoWaySwitch**

Connect:
- `result` (bool) → TwoWaySwitch `condition` input
- Condition evaluator `exec_out` → TwoWaySwitch `exec_in`

TwoWaySwitch has two exec outputs:
- `exec_true` — fires when condition is `True`
- `exec_false` — fires when condition is `False`

**4. True branch**

Connect `exec_true` → Console Print A. Set A's message port to a static string `"Value exceeds threshold — triggering alert."` or pipe a dynamic string through.

**5. False branch**

Connect `exec_false` → Console Print B with `"Value is within threshold — no action needed."`.

**6. Convergence**

Both Console Print nodes' `exec_out` pins connect to a shared final Console Print node with the message `"Check complete."`.

> **Note:** In Vibrante-Node, multiple `exec_out` connections into a single `exec_in` are valid. The engine executes the target node once for whichever upstream exec fires. Since TwoWaySwitch fires exactly one branch, the final node runs exactly once.

### Extending to Multi-Branch Logic

For more than two conditions, chain TwoWaySwitches:

```
Condition A → TwoWaySwitch 1
  exec_true  → branch A
  exec_false → Condition B → TwoWaySwitch 2
                 exec_true  → branch B
                 exec_false → branch C (default)
```

---

## Tutorial 4: Loop Over a List

**Goal:** Take a list of names, process each one (title-case), collect the results, and print the final processed list.

### Nodes Used

| Node | Role |
|------|------|
| Create List | Build or receive the input list |
| SetVariable | Initialize the accumulator |
| ForEach | Iterate over items |
| Python Script | Title-case each item |
| GetVariable | Read current accumulator |
| List Append | Add processed item |
| SetVariable | Update accumulator |
| GetVariable | Final read |
| Console Print | Output result |

### Step-by-Step Build

**1. Create List**

Use **Create List** (or a Python Script) to produce your list:

```python
result = ["alice smith", "BOB JONES", "carol WHITE", "david brown"]
```

**2. Initialize accumulator**

Drag **SetVariable**. Set `var_name` = `"processed_names"`, `value` = `[]` (empty list). Connect `exec_out` → ForEach `exec_in`.

**3. ForEach**

Connect `result` → ForEach `items`.

ForEach exposes:
- `current_item` — the value at the current index
- `current_index` — the 0-based index
- `loop_exec_out` — exec pin that fires for each iteration (connect your loop body here)
- `exec_out` — fires once after the loop finishes

**4. Process item**

Wire ForEach `current_item` → this script's `data` input:

```python
item = inputs.get("data", "")
result = item.title()
```

**5. GetVariable → List Append → SetVariable**

Chain:
1. GetVariable: `var_name` = `"processed_names"` → `current_list`
2. List Append: `list` = `current_list`, `item` = `result` (from process script) → `appended_list`
3. SetVariable: `var_name` = `"processed_names"`, `value` = `appended_list`

Wire the loop exec chain: ForEach `loop_exec_out` → Process Script → GetVariable → List Append → SetVariable → ForEach `loop_exec_in` (to continue the loop).

**6. Post-loop**

After ForEach `exec_out`:
1. GetVariable: `"processed_names"` → `final_list`
2. Python Script (wire GetVariable `final_list` → `data`): `result = str(inputs.get("data", []))`
3. Console Print

### Expected Output

```
['Alice Smith', 'Bob Jones', 'Carol White', 'David Brown']
```

---

## Tutorial 5: Maya Automation Workflow

**Goal:** Open a Maya scene headlessly, configure render settings, and export an Alembic cache. Check success or failure.

### Nodes Used

| Node | Role |
|------|------|
| Maya Action: Open Scene | Open .ma/.mb file |
| Maya Action: Set Render Settings | Frame range, renderer |
| Maya Action: Export Alembic | Export specified objects |
| Maya Headless Executor | Run the action list |
| TwoWaySwitch | Branch on success |
| Console Print (×2) | Success / failure messages |

### Understanding the Action-List Pattern

Maya automation in Vibrante-Node uses an **action list** — a Python list of dicts that describes operations to perform. Each action node appends a dict to the list. The **Maya Headless Executor** node consumes the complete list, launches a Maya batch subprocess, and executes each action in order.

This design means:
- No Maya process is opened until the entire list is assembled.
- The action list can be branched, filtered, or modified before execution.
- Execution happens in a single subprocess — fast startup, no repeated Maya launch overhead.

### Step-by-Step Build

**1. Maya Action: Open Scene**

This is a Houdini-style headless action node. If a custom `maya_action_open_scene` node is registered:

```python
# Node python_code equivalent
actions = list(inputs.get("actions_in") or [])
actions.append({
    "type": "open_scene",
    "scene_path": inputs.get("scene_path", "")
})
return {"actions_out": actions, "exec_out": True}
```

Set `scene_path` to your `.mb` file path.

**2. Maya Action: Set Render Settings**

```python
actions = list(inputs.get("actions_in") or [])
actions.append({
    "type": "set_render_settings",
    "renderer": inputs.get("renderer", "arnold"),
    "start_frame": int(inputs.get("start_frame", 1)),
    "end_frame": int(inputs.get("end_frame", 100)),
    "image_output": inputs.get("image_output", "/tmp/render/"),
    "image_prefix": inputs.get("image_prefix", "render")
})
return {"actions_out": actions, "exec_out": True}
```

**3. Maya Action: Export Alembic**

```python
actions = list(inputs.get("actions_in") or [])
actions.append({
    "type": "export_alembic",
    "objects": inputs.get("objects", ""),       # e.g. "|geo_GRP"
    "output_path": inputs.get("output_path", "/tmp/export.abc"),
    "frame_range": [
        int(inputs.get("start_frame", 1)),
        int(inputs.get("end_frame", 100))
    ]
})
return {"actions_out": actions, "exec_out": True}
```

**4. Maya Headless Executor**

This node launches Maya, runs the actions, and outputs:
- `success` (bool)
- `log_output` (string)
- `error_message` (string, empty on success)

**5. Conditional routing**

Connect `success` → TwoWaySwitch `condition`. Route:
- `exec_true` → Console Print: `"Maya export completed successfully."`
- `exec_false` → Python Script that reads `error_message` and prints it.

### Notes

- Ensure `MAYA_LOCATION` and `VIBRANTE_MAYA_EXE` are set in your environment.
- The Maya runner script in `plugins/maya/` must have a handler for every action `type` key.
- `objects` can be a single DAG path or a semicolon-separated list.

---

## Tutorial 6: Houdini Procedural Workflow

**Goal:** Create a Houdini geometry container, add a Box SOP, transform it, cook the network, and store the resulting node path.

### Nodes Used

| Node | Role |
|------|------|
| Houdini: Ping | Verify connection |
| Houdini: Create Node | Create /obj-level geo |
| Houdini: Clear Children | Remove default nodes |
| Houdini: Create Node | Create Box SOP |
| Houdini: Create Node | Create Transform SOP |
| Houdini: Connect Nodes | Wire SOPs |
| Houdini: Set Parm | Position transform |
| Houdini: Set Display/Render | Flag the output SOP |
| Houdini: Cook Node | Force evaluation |
| Houdini: Layout Children | Auto-layout |
| Console Print | Log result path |

### Step-by-Step Build

All Houdini nodes call the JSON-RPC bridge internally. The following Python Script node demonstrates the full flow in a single node (which you can then break into individual nodes as needed):

```python
from src.utils.hou_bridge import get_bridge

async def execute(self, inputs):
    bridge = get_bridge()

    # 1. Ping to verify connection
    ping = bridge.ping()
    if ping.get("status") != "ok":
        self.log_error("Houdini not responding.")
        return {"result_path": "", "exec_out": True}

    # 2. Create /obj-level geo container
    geo_result = bridge.create_node("/obj", "geo", "tutorial_geo")
    geo_path = geo_result["path"]   # e.g. "/obj/tutorial_geo"

    # 3. Clear Houdini's default child nodes
    for child in bridge.children(geo_path):
        bridge.delete_node(child["path"])

    # 4. Create Box SOP
    box_result = bridge.create_node(geo_path, "box", "my_box")
    box_path = box_result["path"]

    # 5. Set box size
    bridge.set_parms(box_path, {"sizex": 2.0, "sizey": 1.0, "sizez": 1.5})

    # 6. Create Transform SOP
    xform_result = bridge.create_node(geo_path, "xform", "my_xform")
    xform_path = xform_result["path"]

    # 7. Wire box → xform
    bridge.connect_nodes(box_path, xform_path, output=0, input_idx=0)

    # 8. Translate the transform
    bridge.set_parms(xform_path, {"tx": 3.0, "ty": 1.0, "tz": 0.0})

    # 9. Set display and render flags on xform
    bridge.set_display_flag(xform_path, True)
    bridge.set_render_flag(xform_path, True)

    # 10. Cook
    bridge.cook_node(xform_path, force=True)

    # 11. Auto-layout
    bridge.layout_children(geo_path)

    self.log_info(f"Geo network created at: {geo_path}")
    return {"result_path": geo_path, "exec_out": True}
```

### Expected Result

In Houdini's Network Editor, `/obj/tutorial_geo` appears with two SOPs (`my_box` → `my_xform`) wired in series, `my_xform` flagged for display and render, and the box visible in the viewport.

### Extending to Export

After cooking, add:

```python
# Save the hip file with the new network
save_result = bridge.save_hip("/path/to/output.hip")
self.log_info(f"Saved: {save_result['saved']}")
```

---

## Tutorial 7: Prism Pipeline Asset Workflow

**Goal:** Initialize PrismCore, retrieve all assets for a project, get the latest export path for each asset, and log the results.

### Nodes Used

| Node | Role |
|------|------|
| prism_core_init | Bootstrap PrismCore |
| prism_get_assets | List project assets |
| ForEach | Iterate over assets |
| prism_get_export_path | Resolve the export path |
| Console Print | Log each path |

### Step-by-Step Build

**Important:** Place `prism_core_init` anywhere in the graph. The engine detects it before execution begins and bootstraps `PrismCore` automatically. You do not need to wire `core` between nodes.

**1. prism_core_init**

Drag onto canvas. Configure `project_path` if your Prism installation requires it. This node has no meaningful output — it exists solely for the bootstrap side effect.

**2. prism_get_assets**

```python
from src.nodes.base import BaseNode
from src.utils.prism_core import resolve_prism_core

class Prism_Get_Assets(BaseNode):
    name = "prism_get_assets"

    async def execute(self, inputs):
        core = resolve_prism_core(inputs)
        if core is None:
            self.log_error("PrismCore not available.")
            return {"assets": [], "exec_out": True}
        try:
            assets = core.getAssets()
            return {"assets": assets, "exec_out": True}
        except Exception as e:
            self.log_error(f"Prism error: {e}")
            return {"assets": [], "exec_out": True}
```

**3. ForEach → prism_get_export_path**

For each asset dict, call:

```python
core = resolve_prism_core(inputs)
asset = inputs.get("current_item", {})
asset_name = asset.get("asset", "")

try:
    paths = core.getExportPaths(asset=asset_name)
    latest = paths[-1] if paths else None
    return {"export_path": latest, "asset_name": asset_name, "exec_out": True}
except Exception as e:
    self.log_error(f"Could not get export path for {asset_name}: {e}")
    return {"export_path": None, "asset_name": asset_name, "exec_out": True}
```

**4. Console Print**

Build message (custom node receiving `asset_name` and `export_path` as named inputs):

```python
async def execute(self, inputs):
    name = inputs.get("asset_name", "")
    path = inputs.get("export_path", None)
    return {"message": f"  {name}: {path or 'No export found'}", "exec_out": True}
```

### Expected Output

```
character_hero: /project/exports/assets/character_hero/model/v003/character_hero.abc
prop_sword:     /project/exports/assets/prop_sword/model/v001/prop_sword.abc
environment_castle: No export found
```

---

## Tutorial 8: Multi-Shot Rendering Workflow

**Goal:** Iterate over a list of shots. For each shot, open the corresponding Houdini scene, set the frame range, trigger a render, and collect the output paths.

### Nodes Used

| Node | Role |
|------|------|
| Python Script | Build shot list |
| SetVariable | Initialize results list |
| ForEach | Loop over shots |
| Python Script | Build hip path from shot name |
| Houdini: Set Playback Range | Set frame range |
| Houdini: Cook Node (render) | Trigger output driver |
| GetVariable + List Append + SetVariable | Collect results |
| GetVariable | Final read |
| Console Print | Summary |

### Shot List Builder

```python
outputs["shots"] = [
    {"name": "sh010", "start": 1001, "end": 1120, "hip": "/project/scenes/sh010.hip"},
    {"name": "sh020", "start": 1001, "end": 1085, "hip": "/project/scenes/sh020.hip"},
    {"name": "sh030", "start": 1001, "end": 1240, "hip": "/project/scenes/sh030.hip"},
]
```

### Per-Shot Processing Script

```python
from src.utils.hou_bridge import get_bridge

async def execute(self, inputs):
    shot = inputs.get("current_item", {})
    bridge = get_bridge()

    hip_path = shot.get("hip", "")
    start = shot.get("start", 1)
    end = shot.get("end", 240)
    name = shot.get("name", "unknown")

    try:
        # Load the hip file
        bridge.run_code(f"hou.hipFile.load('{hip_path}', suppress_save_prompt=True)")

        # Set frame range
        bridge.set_playback_range(start, end)

        # Cook the mantra/karma output driver
        out_path = f"/out/mantra_beauty"
        bridge.cook_node(out_path, force=True)

        self.log_info(f"Rendered {name}: frames {start}-{end}")
        return {"render_result": {"shot": name, "status": "ok", "frames": end - start + 1}, "exec_out": True}

    except Exception as e:
        self.log_error(f"Failed to render {name}: {e}")
        return {"render_result": {"shot": name, "status": "error", "error": str(e)}, "exec_out": True}
```

### Post-Loop Summary

```python
results = inputs.get("data", [])
ok = [r for r in results if r.get("status") == "ok"]
err = [r for r in results if r.get("status") == "error"]

lines = [f"Render complete: {len(ok)} succeeded, {len(err)} failed."]
for r in err:
    lines.append(f"  FAILED: {r['shot']} — {r.get('error', '')}")

result = "\n".join(lines)
```

---

## Tutorial 9: GroupNode (Subgraph) Workflow

**Goal:** Build a reusable "normalize filename" subgraph, collapse it into a GroupNode, and use it in two different workflows without duplicating nodes.

### Step 1: Build the Reusable Logic

Create three nodes on the canvas:

**Trim & Lower:**
```python
s = inputs.get("data", "")  # GroupIn value wired to data port
result = s.strip().lower()
```

**Replace Spaces:**
```python
s = inputs.get("data", "")  # wired from previous script's result
result = s.replace(" ", "_").replace("-", "_")
```

**Remove Special Chars:**
```python
import re
s = inputs.get("data", "")  # wired from previous script's result
result = re.sub(r"[^a-z0-9_.]", "", s)
```

Wire them in sequence: exec_out → exec_in, and data outputs → inputs.

### Step 2: Add GroupIn and GroupOut Nodes

Drag a **GroupIn** node. Set its `port_name` parameter to `"raw_name"`. This exposes an input port on the eventual GroupNode.

Drag a **GroupOut** node. Set its `port_name` to `"final_name"`. Wire the Remove Special Chars `result` output → GroupOut `value` input.

Wire exec: GroupIn → Trim & Lower → Replace Spaces → Remove Special Chars → GroupOut.

### Step 3: Collapse into a GroupNode

Select all five nodes (Ctrl+A or drag-select). Press **Ctrl+Shift+G** (or Edit → Group Selection).

A dialog prompts for a group name. Enter `"normalize_filename"`.

The five nodes collapse into a single **GroupNode** with:
- Input port: `raw_name`
- Output port: `final_name`
- Exec pins: `exec_in`, `exec_out`

### Step 4: Use the GroupNode

The GroupNode behaves identically to any other node:

```
[Python Script: generate raw name]
      |  (raw_name)
      v
[GroupNode: normalize_filename]
      |  (final_name)
      v
[Console Print]
```

### Step 5: Inspect the Subgraph

Double-click the GroupNode to open its subgraph in a new tab. The tab is labeled `[normalize_filename]` and is fully editable — changes sync back to the parent workflow automatically.

### Step 6: Reuse in Another Workflow

Save the workflow containing the GroupNode. In a new workflow, use **File → Import Nodes** (or copy-paste the GroupNode widget). The entire subgraph is embedded — no external dependencies.

---

## Tutorial 10: Debugging a Failing Workflow

**Goal:** A workflow is producing incorrect output. Use Vibrante-Node's debugging tools to find and fix the problem.

### Tool 1: The Log Panel

The log panel (bottom of the window) shows:

- **Node started / finished** with timing: `Node 'Get Asset' finished in 0.34s`
- **Info messages** from `self.log_info()`
- **Error messages** from `self.log_error()` in red
- **Execution order** — nodes appear in the order they ran

Start here. Look for red error lines. Click a log entry to highlight the corresponding node on the canvas.

### Tool 2: Console Print Nodes

Insert a **Console Print** node between any two nodes to inspect the intermediate value:

```
[Source Node] → (data output) → [Console Print] → (passthrough) → [Downstream Node]
```

Console Print has a passthrough so it does not break the exec chain. This is the fastest way to verify that a value is what you expect at each stage.

### Tool 3: Wire Hover Tooltips (Live Value Inspector)

After running the workflow, hover your mouse over any wire (edge) connecting two nodes. A tooltip appears showing:

```
port_name: <repr of last value, capped at 300 chars>
```

This works for both data wires and exec wires. No extra nodes needed — just hover.

Values persist after execution finishes, so you can inspect the entire graph's state at leisure.

### Tool 4: Bypass a Node

Right-click any node → **Bypass**. A bypassed node is skipped during execution; its input data is forwarded directly to its output. This lets you disable a section without deleting it.

Use bypass to isolate which node is causing a problem:

1. Bypass the suspected node → run → does the error disappear?
2. If yes: the problem is in that node's logic.
3. If no: bypass the next node in the chain and repeat.

### Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No output, no error | Entry node not connected to exec chain | Ensure entry node has exec_out wired |
| `None` appearing mid-chain | Missing output key in `return` dict | Check all node return statements |
| Loop runs 0 times | Empty list input to ForEach | Print the list before ForEach |
| Houdini nodes hang | Houdini bridge not connected | Check Houdini console for server startup |
| Values not updating | Shared `parameters` from a previous run | Use `memory` dict for per-run state |
| GroupNode shows wrong result | Subgraph exec chain broken | Double-click to inspect the subgraph |

### Step-by-Step Debug Session

1. Run the workflow. Note which nodes appear in the log.
2. If execution stops early, the last node in the log is the culprit or its immediate successor.
3. Insert Console Print nodes before and after the suspect node.
4. Re-run. Compare actual vs. expected values in the log.
5. Hover wires around the suspect node to see raw values.
6. Bypass the suspect node to confirm it is the source.
7. Open the node's code editor and add `print()` statements for more detail.
8. Fix the logic, remove debug Console Print nodes, re-run to confirm.
