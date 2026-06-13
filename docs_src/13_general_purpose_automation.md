# General-Purpose Automation with Vibrante-Node

Vibrante-Node is often introduced through its VFX integrations — Houdini, Maya, Prism. But those integrations are optional plugins that extend a general-purpose automation engine. At its core, Vibrante-Node is a visual, async, node-based Python execution framework that can orchestrate any automation task: file processing, API orchestration, data transformation, AI pipelines, database operations, DevOps workflows, and more.

This chapter covers twelve practical automation domains, explains why a node-based approach outperforms linear scripts, and teaches you to decompose any problem into nodes.

---

## Why Node-Based Logic Beats Linear Scripts

A linear Python script does one thing at a time, top to bottom. It is easy to write for simple problems and increasingly painful to maintain as complexity grows.

Consider a script that: reads a folder, renames files, resizes images, calls an API to log the results, and sends an email on completion. When the resize step fails halfway through, the script has already renamed some files and called the API for none. Recovery requires careful manual state tracking. Adding a new step — say, compressing the output — means editing the script, re-testing the whole thing, and hoping you didn't break the rename step.

Node-based automation addresses these pain points structurally:

**Visibility.** Each step is a named box on the canvas. You can see the entire pipeline at once, understand what it does before running it, and identify which step failed from the log panel without reading code.

**Modularity.** Nodes are self-contained. Changing the resize node doesn't risk breaking the rename node. You can swap out the email node for a Slack notification node without touching anything else.

**Reusability.** A "normalize filename" subgraph can be collapsed into a GroupNode and dropped into any other workflow. No copy-paste, no diverging implementations.

**Conditional routing.** TwoWaySwitch lets you visually route execution to different branches based on a condition — success vs. failure, above threshold vs. below, file exists vs. missing. In a linear script this is if/else buried in indentation.

**Live debugging.** Hover any wire after a run to see the last value that flowed through it. Insert Console Print nodes between steps without restructuring code. The log panel timestamps every node execution.

---

## The Async Advantage

Vibrante-Node's `execute()` methods are Python coroutines (async functions). This has three practical benefits:

**Non-blocking I/O.** When your HTTP request node awaits a network response, the event loop stays active. Other UI events (like canceling a run) still work. The UI never freezes.

**Concurrent execution.** Nodes that have no data dependency on each other can run concurrently in future engine versions. The dependency graph structure makes parallelism explicit — if two nodes both read from the same source but don't feed into each other, they can run simultaneously.

**Subprocess orchestration.** `asyncio.create_subprocess_exec()` lets nodes run CLI tools (ffmpeg, git, mayapy) and await their completion without blocking the UI thread.

The one rule: never call blocking code directly inside `execute()`. Use `asyncio.to_thread()` for file I/O, database queries, CPU-bound operations, and any synchronous library call that takes more than a few milliseconds.

---

## Use Case 1: File Processing and Batch Operations

### The Problem

You have 500 files in a folder that need to be renamed according to a naming convention, copied to a destination, and logged in a CSV file. The naming rule: `{project}_{date}_{original_name_lowercase}.ext`.

### Why Node-Based

A linear script becomes fragile when the naming rule changes (you edit the core loop), when a file fails to copy (exception handling obscures the flow), and when you want to add a new step like compression (rewrite the whole middle section).

With nodes, you change the rename node's logic independently, the error branch is a separate visual path, and adding compression is a new node dropped between "copy" and "log."

### Nodes to Use

```
[File Batch Processor]   ← folder_path, pattern="*"
        ↓ file_list
[ForEach]
        ↓ current_item (one file path per iteration)
[Python Script: Build new name]
        ↓ new_name, old_path
[Python Script: Copy file]
        ↓ copied_path, success
[TwoWaySwitch on success]
  exec_true  → [List Append: results]
  exec_false → [Console Print: "Copy failed: {old_path}"]
        ↓ (both branches)
[back to ForEach loop_exec_in]
        ↓ (after loop)
[Python Script: Write CSV log]
[Console Print: "Batch complete."]
```

### Custom Node: Build New Name

```python
import os
from datetime import date

async def execute(self, inputs):
    full_path = inputs.get("current_item", "")
    project   = inputs.get("project", "proj")
    today     = date.today().strftime("%Y%m%d")
    original  = os.path.basename(full_path)
    name, ext = os.path.splitext(original)
    new_name  = f"{project}_{today}_{name.lower()}{ext}"

    return {"new_name": new_name, "old_path": full_path, "exec_out": True}
```

### Custom Node: Copy File

```python
import asyncio
import os
import shutil

async def execute(self, inputs):
    old_path  = inputs.get("old_path", "")
    new_name  = inputs.get("new_name", "")
    dest_dir  = inputs.get("dest_dir", "")

    dest_path = os.path.join(dest_dir, new_name)

    try:
        await asyncio.to_thread(shutil.copy2, old_path, dest_path)
        return {"copied_path": dest_path, "success": True, "exec_out": True}
    except Exception as e:
        self.log_error(f"Copy failed: {e}")
        return {"copied_path": "", "success": False, "exec_out": True}
```

---

## Use Case 2: Folder Monitoring System

### The Problem

A render farm drops finished frames into a watch folder. You want to automatically detect new `.exr` files, validate them (non-zero size), generate a JPEG proxy, and move the frame to a delivery folder.

### Pattern: Poll + Process

Since Vibrante-Node runs execution in response to a Run click (not as a daemon by default), the folder monitor pattern uses a polling loop with a configurable dwell time. For continuous monitoring, run the workflow headlessly on a cron schedule.

### Using Watchdog Inside a Node

```python
import asyncio
import fnmatch
import os
import time
from src.nodes.base import BaseNode

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG = True
except ImportError:
    _WATCHDOG = False


class Watch_Folder(BaseNode):
    name = "watch_folder"

    def __init__(self):
        super().__init__()
        self.add_input("folder_path",  "string", widget_type="text", default="")
        self.add_input("pattern",      "string", widget_type="text", default="*.exr")
        self.add_input("dwell_secs",   "int",    widget_type="int",  default=60)
        self.add_output("new_files",   "list")

    async def execute(self, inputs):
        folder = inputs.get("folder_path", "")
        pattern = inputs.get("pattern", "*.exr")
        dwell   = int(inputs.get("dwell_secs") or 60)

        new_files = []

        if _WATCHDOG:
            class Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory and fnmatch.fnmatch(
                        os.path.basename(event.src_path), pattern
                    ):
                        new_files.append(event.src_path)

            def _watch():
                obs = Observer()
                obs.schedule(Handler(), folder, recursive=False)
                obs.start()
                time.sleep(dwell)
                obs.stop()
                obs.join()

            await asyncio.to_thread(_watch)
        else:
            # Simple polling fallback
            before = set(os.listdir(folder))
            await asyncio.sleep(dwell)
            after = set(os.listdir(folder))
            new_files = [
                os.path.join(folder, f)
                for f in (after - before)
                if fnmatch.fnmatch(f, pattern)
            ]

        return {"new_files": new_files, "exec_out": True}
```

### Looping Pattern for Continuous Monitoring

Use a **WhileLoop** node wrapping the Watch Folder node. Set the WhileLoop's `condition` to `True` (infinite) or wire a `should_continue` variable that is set to `False` by a "stop" condition.

---

## Use Case 3: Image Processing Pipeline

### The Problem

A photography client delivers 200 high-resolution images that need to be: resized to web dimensions (1920×1080 max), watermarked with a studio logo, converted from TIFF to JPEG at 85% quality, and organized into subfolders by date.

### Nodes to Use

```
[File Batch Processor: *.tiff]
        ↓ file_list
[ForEach]
        ↓ current_item
[Image Resizer: 1920x1080, keep_aspect=True]
        ↓ out_path (temp resized file)
[Python Script: Add Watermark (PIL)]
        ↓ watermarked_path
[Python Script: Convert to JPEG]
        ↓ final_path
[Python Script: Move to dated subfolder]
        ↓ exec_out (loop back)
        ↓ (after loop)
[Console Print: "Processed N images."]
```

### Watermark Node Code

```python
import asyncio
import os
from src.nodes.base import BaseNode

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False


class Add_Watermark(BaseNode):
    name = "add_watermark"

    def __init__(self):
        super().__init__()
        self.add_input("image_path",     "string", widget_type="text", default="")
        self.add_input("watermark_path", "string", widget_type="text", default="")
        self.add_input("opacity",        "float",  widget_type="float", default=0.3)
        self.add_input("position",       "string", widget_type="text", default="bottom-right")
        self.add_output("out_path",      "string")

    async def execute(self, inputs):
        if not _PIL:
            self.log_error("Pillow required: pip install Pillow")
            return {"out_path": "", "exec_out": True}

        img_path = inputs.get("image_path", "")
        wm_path  = inputs.get("watermark_path", "")
        opacity  = float(inputs.get("opacity") or 0.3)
        position = inputs.get("position", "bottom-right")

        def _watermark():
            base = Image.open(img_path).convert("RGBA")
            wm   = Image.open(wm_path).convert("RGBA")

            # Scale watermark to 20% of base width
            wm_w = base.width // 5
            ratio = wm_w / wm.width
            wm_h  = int(wm.height * ratio)
            wm    = wm.resize((wm_w, wm_h), Image.LANCZOS)

            # Apply opacity
            r, g, b, a = wm.split()
            a = a.point(lambda x: int(x * opacity))
            wm.putalpha(a)

            # Position
            margin = 20
            if "right" in position:
                x = base.width - wm_w - margin
            else:
                x = margin
            if "bottom" in position:
                y = base.height - wm_h - margin
            else:
                y = margin

            composite = Image.new("RGBA", base.size)
            composite.paste(base, (0, 0))
            composite.paste(wm, (x, y), mask=wm)

            out_path = img_path.rsplit(".", 1)[0] + "_wm." + img_path.rsplit(".", 1)[-1]
            composite.convert("RGB").save(out_path, quality=92)
            return out_path

        try:
            out = await asyncio.to_thread(_watermark)
            return {"out_path": out, "exec_out": True}
        except Exception as e:
            self.log_error(f"Watermark failed: {e}")
            return {"out_path": img_path, "exec_out": True}  # pass through original


def register_node():
    return Add_Watermark
```

---

## Use Case 4: Data Transformation Workflows

### The Problem

A business analyst provides a CSV with raw sales data. You need to: filter records by region, compute a derived metric (revenue per unit), group by product category, sort by revenue, and export the summary as a formatted JSON report.

### Why Nodes Beat pandas Scripts

A pandas script does all of this in 20 lines but is opaque — you cannot see the data after each step without adding print() calls. A node workflow makes each transform a visible, testable step.

### Workflow Structure

```
[File Load: sales.csv]
        ↓ content
[Python Script: Parse CSV → list of dicts]
        ↓ records
[Python Script: Filter by region]
        ↓ filtered
[Python Script: Compute revenue_per_unit]
        ↓ enriched
[Python Script: Group by category]
        ↓ grouped
[Python Script: Sort by total_revenue desc]
        ↓ sorted_data
[Python Script: Format JSON report]
        ↓ json_string
[File Save: report.json]
[Console Print: summary]
```

### Parse CSV Node

```python
import asyncio
import csv
import io

async def execute(self, inputs):
    content = inputs.get("content", "")
    reader  = csv.DictReader(io.StringIO(content))
    records = [dict(row) for row in reader]
    return {"records": records, "record_count": len(records), "exec_out": True}
```

### Compute Metric Node

```python
async def execute(self, inputs):
    records = list(inputs.get("records") or [])
    enriched = []
    for r in records:
        try:
            revenue  = float(r.get("revenue", 0))
            units    = float(r.get("units", 1)) or 1
            r["revenue_per_unit"] = round(revenue / units, 2)
        except (ValueError, ZeroDivisionError):
            r["revenue_per_unit"] = 0.0
        enriched.append(r)
    return {"enriched": enriched, "exec_out": True}
```

Hover the wire between any two steps to see a sample of the data at that point.

---

## Use Case 5: API Requests and Web Automation

### The Problem

Your team uses a project management API. Every Monday, you need to: authenticate (get a token), fetch all open tasks, filter tasks assigned to a specific user, update their status to "in progress," and post a summary to a Slack webhook.

### Chain Pattern: Auth → Fetch → Transform → Act → Notify

```
[Python Script: Build auth payload]
        ↓ payload
[HTTP Request: POST /auth → token]
        ↓ response_data (contains "access_token")
[Python Script: Extract token]
        ↓ auth_header (dict: {"Authorization": "Bearer {token}"})
[HTTP Request: GET /tasks, headers=auth_header]
        ↓ response_data (list of task dicts)
[Python Script: Filter by assignee]
        ↓ my_tasks
[ForEach: my_tasks]
        ↓ current_item (one task)
[HTTP Request: PATCH /tasks/{id} body={"status":"in_progress"}]
        ↓ exec_out
[Console Print: "Updated task {id}"]
        ↓ (after loop)
[HTTP Request: POST slack_webhook, body={"text": summary}]
[Console Print: "Done."]
```

### Extract Token Node

```python
async def execute(self, inputs):
    data  = inputs.get("response_data", {})
    token = data.get("access_token", "") if isinstance(data, dict) else ""
    if not token:
        self.log_error("Authentication failed — no access_token in response.")
    return {"auth_header": {"Authorization": f"Bearer {token}"}, "token": token, "exec_out": True}
```

### Filter by Assignee Node

```python
async def execute(self, inputs):
    tasks    = list(inputs.get("response_data") or [])
    assignee = inputs.get("assignee_id", "")
    filtered = [t for t in tasks if str(t.get("assignee_id", "")) == str(assignee)]
    return {"my_tasks": filtered, "count": len(filtered), "exec_out": True}
```

---

## Use Case 6: AI/LLM Workflow Orchestration

### The Problem

You receive raw customer feedback text. You want to: classify the sentiment (positive/negative/neutral), extract key topics, generate a suggested response, translate the response to French, and write everything to a database.

### Chain of LLM Prompts

```
[File Load or HTTP Request: raw feedback text]
        ↓ raw_text
[LLM Text Generation: Classify sentiment]
    prompt = "Classify the sentiment of this feedback as positive, negative, or neutral. Reply with one word only: {raw_text}"
        ↓ generated_text (e.g., "negative")
[SetVariable: "sentiment"]

[LLM Text Generation: Extract topics]
    prompt = "List the key topics mentioned in this feedback as a comma-separated list: {raw_text}"
        ↓ generated_text
[SetVariable: "topics"]

[LLM Text Generation: Draft response]
    prompt = "Write a professional customer service response to this {sentiment} feedback about {topics}: {raw_text}"
        ↓ generated_text (the draft response)
[SetVariable: "draft_response"]

[LLM Text Generation: Translate to French]
    prompt = "Translate the following to French: {draft_response}"
        ↓ generated_text
[SetVariable: "french_response"]

[Database Query: INSERT INTO feedback_responses ...]
[Console Print: "Processed feedback."]
```

### Passing Context with SetVariable/GetVariable

Each LLM node needs context from previous steps. Use SetVariable after each LLM result, then GetVariable to build the next prompt:

```python
# In the "Draft response" LLM's prompt-building Python Script:
context   = inputs.get("data", {})
sentiment = context.get("sentiment", "neutral")
topics    = context.get("topics", "")
raw_text  = context.get("raw_text", "")
result = (
    f"Write a professional customer service response to this {sentiment} "
    f"feedback about {topics}: {raw_text}"
)
```

---

## Use Case 7: Local Automation Tools

### The Problem

Your project build process involves: running a test suite, if tests pass — building a distribution package, running a linter, and committing the result to git. Each step's output determines whether the next step runs.

### Subprocess Node Pattern

```python
import asyncio
from src.nodes.base import BaseNode


class Run_Command(BaseNode):
    name = "run_command"

    def __init__(self):
        super().__init__()
        self.add_input("command",    "string", widget_type="text", default="")
        self.add_input("args",       "list",   default=None)
        self.add_input("cwd",        "string", widget_type="text", default="")
        self.add_input("timeout",    "int",    widget_type="int",  default=120)
        self.add_output("stdout",    "string")
        self.add_output("stderr",    "string")
        self.add_output("exit_code", "int")
        self.add_output("success",   "bool")

    async def execute(self, inputs):
        import shlex
        command = inputs.get("command", "")
        args    = list(inputs.get("args") or [])
        cwd     = inputs.get("cwd") or None
        timeout = int(inputs.get("timeout") or 120)

        if not command:
            self.log_error("No command specified.")
            return {"stdout": "", "stderr": "", "exit_code": -1, "success": False, "exec_out": True}

        cmd_parts = shlex.split(command) + args

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                ),
                timeout=5,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            exit_code = proc.returncode
            self.log_info(f"Command exited with code {exit_code}: {command}")
            return {
                "stdout":    stdout.decode("utf-8", errors="replace"),
                "stderr":    stderr.decode("utf-8", errors="replace"),
                "exit_code": exit_code,
                "success":   exit_code == 0,
                "exec_out":  True,
            }
        except asyncio.TimeoutError:
            self.log_error(f"Command timed out after {timeout}s: {command}")
            return {"stdout": "", "stderr": "TIMEOUT", "exit_code": -1, "success": False, "exec_out": True}
        except Exception as e:
            self.log_error(f"Command failed: {e}")
            return {"stdout": "", "stderr": str(e), "exit_code": -1, "success": False, "exec_out": True}


def register_node():
    return Run_Command
```

### Build Pipeline Workflow

```
[Run Command: "pytest tests/ -x"]
        ↓ success
[TwoWaySwitch on success]
  exec_false → [Console Print: "Tests failed. Aborting."]
  exec_true  →
      [Run Command: "python -m build"]
              ↓ success
      [TwoWaySwitch on success]
        exec_false → [Console Print: "Build failed."]
        exec_true  →
            [Run Command: "flake8 src/"]
            [Run Command: "git add dist/ && git commit -m 'Build artifact'"]
            [Console Print: "Build pipeline complete."]
```

---

## Use Case 8: Database Operations

### The Problem

An e-commerce system logs orders to a SQLite database. Every night, you need to: query orders from the last 24 hours, compute revenue by product category, update a summary table, and export the summary to a CSV for the finance team.

### Workflow Structure

```
[Python Script: Compute date range]
        ↓ start_datetime, end_datetime
[Database Query: SELECT orders WHERE created_at BETWEEN ? AND ?]
    parameters = [start_datetime, end_datetime]
        ↓ rows (list of order dicts)
[Python Script: Aggregate by category]
        ↓ summary (list of {category, revenue, order_count})
[ForEach: summary]
    [Database Query: INSERT OR REPLACE INTO daily_summary ...]
[Python Script: Format as CSV]
        ↓ csv_content
[File Save: daily_summary.csv]
[Console Print: "Nightly report complete."]
```

### Aggregation Node

```python
from collections import defaultdict

async def execute(self, inputs):
    rows     = list(inputs.get("rows") or [])
    totals   = defaultdict(lambda: {"revenue": 0.0, "order_count": 0})

    for row in rows:
        cat = row.get("category", "Uncategorized")
        totals[cat]["revenue"]     += float(row.get("revenue", 0))
        totals[cat]["order_count"] += 1

    summary = [
        {"category": cat, **vals}
        for cat, vals in sorted(totals.items(), key=lambda x: -x[1]["revenue"])
    ]
    total_revenue = sum(v["revenue"] for v in totals.values())
    return {"summary": summary, "total_revenue": total_revenue, "exec_out": True}
```

---

## Use Case 9: Task Scheduling

### The Problem

You want to run a workflow every 5 minutes to poll an API for status updates, process any new data, and stop once a "complete" status is received.

### Timer / Delay Node

```python
import asyncio
from src.nodes.base import BaseNode


class Timer_Delay(BaseNode):
    name = "timer_delay"

    def __init__(self):
        super().__init__()
        self.add_input("delay_seconds", "float", widget_type="float", default=5.0)
        self.add_output("elapsed", "float")

    async def execute(self, inputs):
        delay = float(inputs.get("delay_seconds") or 5.0)
        import time
        t0 = time.perf_counter()
        await asyncio.sleep(delay)
        elapsed = time.perf_counter() - t0
        return {"elapsed": elapsed, "exec_out": True}


def register_node():
    return Timer_Delay
```

### Polling Loop Workflow

```
[SetVariable: "should_continue" = True]
        ↓ exec_out
[WhileLoop: condition = should_continue]
        ↓ loop_exec_out

    [Timer Delay: 300 seconds (5 min)]
    [HTTP Request: GET /api/job/{job_id}/status]
            ↓ response_data
    [Python Script: Check status]
        data = inputs.get("data", {})
        status = data.get("status", "")
        result = status in ("complete", "failed", "error")
            ↓ result (bool)
    [TwoWaySwitch on result]
      exec_true  → [SetVariable: "should_continue" = False]
                   [Console Print: "Job finished"]
      exec_false → [Console Print: "Still running"]
            ↓ (both branches back to WhileLoop loop_exec_in)

        ↓ exec_out (after WhileLoop exits)
[Console Print: "Polling complete."]
```

### Integration with System Schedulers

For truly periodic execution, run the workflow headlessly via a system scheduler:

**Windows Task Scheduler:**
```batch
python -m src.headless --workflow my_poll_workflow.json
```

**Linux cron:**
```cron
*/5 * * * * /path/to/venv/bin/python -m src.headless --workflow /path/to/workflow.json
```

**macOS launchd:** Create a plist in `~/Library/LaunchAgents/` with `StartInterval` set to 300.

---

## Use Case 10: Multi-Step Business Logic

### The Problem

An approval workflow: receive a purchase request, validate the amount and supplier, check budget availability, auto-approve if under $1,000 or queue for manual review if over, notify the requester, and write an audit log entry.

### Approval Workflow

```
[Python Script: Receive/load purchase request]
        ↓ request (dict: amount, supplier, department, requester_email)

[Python Script: Validate request]
    request = inputs.get("data", {})
    valid = request.get("amount", 0) > 0 and request.get("supplier", "") != ""
    result = valid
        ↓ result (bool)

[TwoWaySwitch on result]
  exec_false → [Email Notification: "Request invalid — missing required fields"]
               [Console Print: "Rejected"]
  exec_true  →

    [Python Script: Check budget]
        budget_remaining = get_budget(department)   # DB query
        result = budget_remaining >= amount
            ↓ result (bool)

    [TwoWaySwitch on result]
      exec_false → [Email Notification: "Insufficient budget"]
      exec_true  →

        [Python Script: Threshold check]
            result = amount < 1000
                ↓ result (bool)

        [TwoWaySwitch on result]
          exec_true  → [Python Script: Approve and deduct budget]
                       [Email Notification: requester — "Approved automatically"]
          exec_false → [Python Script: Create review ticket]
                       [Email Notification: approver — "Review required"]
                       [Email Notification: requester — "Pending review"]

[Python Script: Write audit log entry]
[Database Query: INSERT INTO audit_log ...]
[Console Print: "Workflow complete."]
```

### exec_fail Branches

For nodes that might throw exceptions (database writes, email sends), connect their `exec_fail` output to an error handling branch:

```
[Database Query] ─── exec_out  → [Continue]
                 └── exec_fail → [Console Print: "DB write failed — manual intervention required."]
                                 [Email Notification: ops team]
```

---

## Use Case 11: DevOps and Build Automation

### The Problem

On every merge to the main branch, run the test suite, build a Docker image, push it to a registry, deploy to a staging environment, run smoke tests, and send a status notification.

### Workflow

```
[Python Script: Read environment variables]
    GIT_SHA, REGISTRY, IMAGE_NAME, STAGING_HOST = os.environ
        ↓ image_tag = f"{REGISTRY}/{IMAGE_NAME}:{GIT_SHA[:8]}"

[Run Command: "pytest tests/ --tb=short"]
        ↓ success, stdout
[TwoWaySwitch on success]
  exec_false → [Email Notification / Slack: "Tests FAILED"]
               [Python Script: exit with code 1]
  exec_true  →
    [Run Command: f"docker build -t {image_tag} ."]
            ↓ success
    [TwoWaySwitch on success]
      exec_false → [Slack: "Docker build FAILED"]
      exec_true  →
        [Run Command: f"docker push {image_tag}"]
        [Run Command: f"ssh {STAGING_HOST} 'docker pull {image_tag} && docker-compose up -d'"]
        [Run Command: "pytest tests/smoke/ --base-url=https://staging.example.com"]
                ↓ success, stdout
        [TwoWaySwitch on success]
          exec_true  → [Slack: "Deploy SUCCEEDED — {image_tag}"]
          exec_false → [Slack: "Smoke tests FAILED — {image_tag}"]
                       [Run Command: "ssh {STAGING_HOST} 'docker-compose down'"]
```

### Reading Environment Variables Node

```python
import os

async def execute(self, inputs):
    keys = list(inputs.get("env_keys") or [])
    env_values = {}
    for key in keys:
        val = os.environ.get(key, "")
        if not val:
            self.log_error(f"Environment variable not set: {key}")
        env_values[key] = val
    return {
        "env_values": env_values,
        "PATH":       os.environ.get("PATH", ""),
        "HOME":       os.environ.get("HOME", ""),
        "all_env":    dict(os.environ),
        "exec_out":   True,
    }
```

---

## Use Case 12: Background Services and Workers

### Running Headlessly

Vibrante-Node workflows can run without the UI using the headless execution API:

```python
import asyncio
import json
from src.core.models import WorkflowModel
from src.core.graph import GraphManager
from src.core.engine import NetworkExecutor


def run_workflow(workflow_path: str) -> None:
    with open(workflow_path) as f:
        data = json.load(f)

    workflow = WorkflowModel.model_validate(data)
    gm       = GraphManager()
    gm.from_model(workflow)

    executor = NetworkExecutor(gm)

    # Connect signals for headless logging
    executor.node_started.connect(lambda nid: print(f"[START] {nid}"))
    executor.node_finished.connect(lambda nid, r: print(f"[DONE]  {nid}"))
    executor.node_error.connect(lambda nid, e: print(f"[ERROR] {nid}: {e}"))

    asyncio.run(executor.run())


if __name__ == "__main__":
    import sys
    run_workflow(sys.argv[1])
```

### Logging to File vs. UI

In headless mode, connect to engine signals and write to a log file:

```python
import logging

logging.basicConfig(
    filename="workflow.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

executor.node_error.connect(
    lambda nid, e: logging.error(f"Node {nid} failed: {e}")
)
executor.node_finished.connect(
    lambda nid, r: logging.info(f"Node {nid} finished")
)
```

### Restart on Failure Pattern

Wrap the headless run in a retry loop:

```python
import time

MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds

for attempt in range(1, MAX_RETRIES + 1):
    try:
        run_workflow("my_workflow.json")
        print("Workflow completed successfully.")
        break
    except Exception as e:
        print(f"Attempt {attempt} failed: {e}")
        if attempt < MAX_RETRIES:
            print(f"Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
        else:
            print("All retries exhausted. Giving up.")
            raise
```

---

## Thinking in Node-Based Logic

The hardest part of adopting node-based automation is learning to decompose problems into nodes. This section teaches a repeatable method.

### Step 1: Identify Inputs, Transforms, Outputs

Every automation task is a transformation from some starting data to some end result.

Ask:
- **What do I start with?** Files, API responses, user input, database records, environment variables.
- **What do I end with?** Modified files, API calls made, database rows inserted, emails sent, logs written.
- **What transforms happen in between?** Filtering, formatting, computing, converting, validating.

Map each answer to a category of node:
- Inputs → File Load, HTTP Request, Database Query, Python Script (static data)
- Transforms → Python Script, String nodes, Math nodes, List nodes
- Outputs → File Save, HTTP Request (POST/PUT), Database Query (INSERT/UPDATE), Email Notification

### Step 2: Separate Data Flow from Control Flow

Data flow (the white/colored wires) carries values between nodes. Control flow (exec wires, gray) determines which nodes run and in what order.

Keep them separate in your thinking:

**Data questions:**
- What value does this node need?
- Where does that value come from?
- What type should it be?

**Control questions:**
- Does this node always run, or only sometimes?
- If step A fails, should step B still run?
- Are there loops? What is the exit condition?

Once you have answered these separately, wiring becomes straightforward: data connections carry the values, exec connections carry the "go" signal.

### Step 3: Group Reusable Logic into Subgraphs

Any sequence of nodes you find yourself building more than once is a candidate for a GroupNode. Common reusable subgraphs:

- "Authenticate and return token" (auth pattern)
- "Load, validate, transform a JSON file" (ETL pattern)
- "Run command, check exit code, branch on failure" (CLI wrapper pattern)
- "Build an audit log entry and write it" (logging pattern)

Select the nodes, press Ctrl+Shift+G, name the group, and it becomes a single reusable node.

### Step 4: Connect Error Handling Branches

Every workflow needs to handle failure. For each critical step, ask: "What happens if this fails?"

The three patterns:

**Silent fail with log:** Return a safe default and `exec_out: True`. The chain continues; downstream nodes receive `None` or an empty value. Use for non-critical steps.

```python
try:
    pass  # ... your work ...
except Exception as e:
    self.log_error(f"Step failed: {e}")
    return {"result": None, "exec_out": True}  # chain continues
```

**Hard stop:** Return `exec_out: False`. The chain stops at this node. Use when continuing would produce nonsense results.

**Explicit error branch:** Use `exec_fail` port (available on GroupNode and some special nodes). Connect error handling nodes (notification, rollback, cleanup) to `exec_fail`. Use for recoverable errors where you want to take remediation action.

Build the happy path first, then add error branches. Use TwoWaySwitch with a `success` bool to route to success or failure paths when a node doesn't have an `exec_fail` pin.

### Decision Framework: When to Use Which Node

| Situation | Node to Use |
|-----------|-------------|
| Run arbitrary Python | Python Script |
| Repeat for each item in a list | ForEach |
| Repeat until a condition | WhileLoop |
| Choose between two exec paths | TwoWaySwitch |
| Share a value across disconnected nodes | SetVariable / GetVariable |
| Group reusable logic | GroupNode (Ctrl+Shift+G) |
| Inspect intermediate values | Console Print |
| Make an HTTP call | HTTP Request |
| Read/write a file | File Load / File Save |
| Run a shell command | Run Command (custom) |
| Query a database | Database Query (custom) |
| Call an AI model | LLM Text Generation (custom) |
| Wait before continuing | Timer Delay (custom) |
| Collapse a complex section | GroupNode |
