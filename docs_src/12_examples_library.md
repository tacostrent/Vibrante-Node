# Examples Library

This chapter provides ten complete, copy-paste-ready node examples. Each example includes the full JSON node definition, the Python code, and a usage guide. All examples follow the node authoring conventions described in the Contribution Guide.

---

## Example 1: Custom String Processor Node

**Description:** Takes a string input and a regex pattern, replaces all matches with a replacement string, and outputs the modified result along with the count of substitutions made.

### Node JSON

```json
{
    "node_id": "regex_replace",
    "name": "regex_replace",
    "description": "Replace all regex matches in a string with a substitution value.",
    "category": "String",
    "icon_path": null,
    "use_exec": true,
    "inputs": [
        { "name": "exec_in",      "type": "any",    "widget_type": null,   "options": null, "default": null },
        { "name": "text",         "type": "string", "widget_type": "text", "options": null, "default": "" },
        { "name": "pattern",      "type": "string", "widget_type": "text", "options": null, "default": "" },
        { "name": "replacement",  "type": "string", "widget_type": "text", "options": null, "default": "" },
        { "name": "ignore_case",  "type": "bool",   "widget_type": "checkbox", "options": null, "default": false }
    ],
    "outputs": [
        { "name": "result",       "type": "string", "widget_type": null, "options": null, "default": null },
        { "name": "match_count",  "type": "int",    "widget_type": null, "options": null, "default": null },
        { "name": "exec_out",     "type": "any",    "widget_type": null, "options": null, "default": null }
    ],
    "python_code": "..."
}
```

### Python Code

```python
import re
from src.nodes.base import BaseNode


class Regex_Replace(BaseNode):
    name = "regex_replace"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("text",        "string", widget_type="text", default="")
        self.add_input("pattern",     "string", widget_type="text", default="")
        self.add_input("replacement", "string", widget_type="text", default="")
        self.add_input("ignore_case", "bool",   widget_type="checkbox", default=False)
        self.add_output("result",      "string")
        self.add_output("match_count", "int")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        text        = inputs.get("text", "")
        pattern     = inputs.get("pattern", "")
        replacement = inputs.get("replacement", "")
        ignore_case = inputs.get("ignore_case", False)

        if not pattern:
            return {"result": text, "match_count": 0, "exec_out": True}

        flags = re.IGNORECASE if ignore_case else 0

        try:
            compiled = re.compile(pattern, flags)
            matches  = compiled.findall(text)
            result   = compiled.sub(replacement, text)
            return {
                "result":      result,
                "match_count": len(matches),
                "exec_out":    True,
            }
        except re.error as e:
            self.log_error(f"Invalid regex pattern '{pattern}': {e}")
            return {"result": text, "match_count": 0, "exec_out": True}


def register_node():
    return Regex_Replace
```

### Usage

1. Wire a string value into `text`.
2. Set `pattern` to a Python regex (e.g., `\b\d{4}\b` to find 4-digit numbers).
3. Set `replacement` to the substitution string (supports back-references: `\1`).
4. Enable `ignore_case` for case-insensitive matching.
5. `result` carries the modified string; `match_count` carries how many substitutions were made.

---

## Example 2: HTTP API Request Node

**Description:** Makes an async HTTP GET or POST request, handles JSON or text responses, and outputs the parsed data. Uses `urllib.request` in a thread executor (`loop.run_in_executor`) for non-blocking I/O — compatible with Vibrante-Node's QTimer-stepped asyncio event loop.

### Node JSON

```json
{
    "node_id": "http_request",
    "name": "http_request",
    "description": "Async HTTP GET or POST request with optional JSON body and headers.",
    "category": "Network",
    "icon_path": null,
    "use_exec": true,
    "inputs": [
        { "name": "exec_in",  "type": "any",    "widget_type": null,      "options": null, "default": null },
        { "name": "url",      "type": "string", "widget_type": "text",    "options": null, "default": "" },
        { "name": "method",   "type": "string", "widget_type": "text",    "options": null, "default": "GET" },
        { "name": "headers",  "type": "any",    "widget_type": null,      "options": null, "default": null },
        { "name": "body",     "type": "any",    "widget_type": null,      "options": null, "default": null },
        { "name": "timeout",  "type": "int",    "widget_type": "int",     "options": null, "default": 30 }
    ],
    "outputs": [
        { "name": "response_data",   "type": "any",    "widget_type": null, "options": null, "default": null },
        { "name": "status_code",     "type": "int",    "widget_type": null, "options": null, "default": null },
        { "name": "response_text",   "type": "string", "widget_type": null, "options": null, "default": null },
        { "name": "success",         "type": "bool",   "widget_type": null, "options": null, "default": null },
        { "name": "exec_out",        "type": "any",    "widget_type": null, "options": null, "default": null }
    ],
    "python_code": "..."
}
```

### Python Code

```python
import json
import asyncio
from src.nodes.base import BaseNode


class Http_Request(BaseNode):
    name = "http_request"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("url",     "string", widget_type="text", default="")
        self.add_input("method",  "string", widget_type="text", default="GET")
        self.add_input("headers", "any",    default=None)
        self.add_input("body",    "any",    default=None)
        self.add_input("timeout", "int",    widget_type="int",  default=30)
        self.add_output("response_data",  "any")
        self.add_output("status_code",    "int")
        self.add_output("response_text",  "string")
        self.add_output("success",        "bool")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        import urllib.request
        import urllib.error

        url     = inputs.get("url", "")
        method  = (inputs.get("method") or "GET").upper()
        headers = dict(inputs.get("headers") or {})
        body    = inputs.get("body")
        timeout = int(inputs.get("timeout") or 30)

        if not url:
            self.log_error("No URL provided.")
            return {"response_data": None, "status_code": 0,
                    "response_text": "", "success": False, "exec_out": True}

        body_bytes = None
        if body is not None:
            body_str = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
            body_bytes = body_str.encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

        def _sync_do():
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status, resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", errors="replace")

        loop = asyncio.get_running_loop()
        try:
            status, text = await loop.run_in_executor(None, _sync_do)
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                data = text
            return {
                "response_data":  data,
                "status_code":    status,
                "response_text":  text,
                "success":        200 <= status < 300,
                "exec_out":       True,
            }
        except Exception as e:
            self.log_error(f"HTTP request failed: {e}")
            return {"response_data": None, "status_code": 0,
                    "response_text": str(e), "success": False, "exec_out": True}


def register_node():
    return Http_Request
```

### Usage

- Set `url` to any REST endpoint.
- Set `method` to `GET`, `POST`, `PUT`, or `DELETE`.
- Wire a dict into `headers` for custom headers (e.g., `{"Authorization": "Bearer token"}`).
- Wire a dict or list into `body` for POST requests — it is automatically JSON-encoded.
- Check `success` with a TwoWaySwitch to branch on HTTP errors.

---

## Example 3: File Batch Processor Node

**Description:** Scans a folder for files matching a glob pattern and outputs a list of matching absolute paths. Optionally recurses into subdirectories.

### Python Code

```python
import glob
import os
import asyncio
from src.nodes.base import BaseNode


class File_Batch_Processor(BaseNode):
    name = "file_batch_processor"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("folder_path", "string", widget_type="text", default="")
        self.add_input("pattern",     "string", widget_type="text", default="*")
        self.add_input("recursive",   "bool",   widget_type="checkbox", default=False)
        self.add_output("file_list",  "list")
        self.add_output("file_count", "int")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        folder    = inputs.get("folder_path", "")
        pattern   = inputs.get("pattern", "*")
        recursive = inputs.get("recursive", False)

        if not folder:
            self.log_error("No folder path provided.")
            return {"file_list": [], "file_count": 0, "exec_out": True}

        folder = os.path.abspath(folder)

        if not os.path.isdir(folder):
            self.log_error(f"Folder does not exist: {folder}")
            return {"file_list": [], "file_count": 0, "exec_out": True}

        def _scan():
            if recursive:
                glob_pattern = os.path.join(folder, "**", pattern)
                paths = glob.glob(glob_pattern, recursive=True)
            else:
                glob_pattern = os.path.join(folder, pattern)
                paths = glob.glob(glob_pattern)
            return sorted(p for p in paths if os.path.isfile(p))

        file_list = await asyncio.to_thread(_scan)

        self.log_info(f"Found {len(file_list)} file(s) matching '{pattern}' in {folder}")
        return {
            "file_list":  file_list,
            "file_count": len(file_list),
            "exec_out":   True,
        }


def register_node():
    return File_Batch_Processor
```

### Usage

- Set `folder_path` to an absolute directory path.
- Set `pattern` to a glob like `*.png`, `*.{jpg,jpeg,png}`, or `render_*_beauty.exr`.
- Enable `recursive` to search all subdirectories.
- Connect `file_list` to a ForEach node to process each file individually.

---

## Example 4: Email Notification Node

**Description:** Sends an email via SMTP. Supports TLS, configurable sender/recipient, subject and body. Ideal as a final step in an automation pipeline to notify on completion or failure.

### Python Code

```python
import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.nodes.base import BaseNode


class Email_Notification(BaseNode):
    name = "email_notification"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("smtp_host",   "string", widget_type="text",     default="smtp.gmail.com")
        self.add_input("smtp_port",   "int",    widget_type="int",      default=587)
        self.add_input("username",    "string", widget_type="text",     default="")
        self.add_input("password",    "string", widget_type="text",     default="")
        self.add_input("from_addr",   "string", widget_type="text",     default="")
        self.add_input("to_addr",     "string", widget_type="text",     default="")
        self.add_input("subject",     "string", widget_type="text",     default="")
        self.add_input("body",        "string", widget_type="text",     default="")
        self.add_input("use_tls",     "bool",   widget_type="checkbox", default=True)
        self.add_output("sent",       "bool")
        self.add_output("error_msg",  "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        host      = inputs.get("smtp_host", "")
        port      = int(inputs.get("smtp_port") or 587)
        username  = inputs.get("username", "")
        password  = inputs.get("password", "")
        from_addr = inputs.get("from_addr", "") or username
        to_addr   = inputs.get("to_addr", "")
        subject   = inputs.get("subject", "(no subject)")
        body      = inputs.get("body", "")
        use_tls   = inputs.get("use_tls", True)

        if not host or not to_addr:
            self.log_error("smtp_host and to_addr are required.")
            return {"sent": False, "error_msg": "Missing host or recipient.", "exec_out": True}

        def _send():
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = from_addr
            msg["To"]      = to_addr
            msg.attach(MIMEText(body, "plain"))

            context = ssl.create_default_context()

            if use_tls:
                with smtplib.SMTP(host, port) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    if username:
                        server.login(username, password)
                    server.sendmail(from_addr, to_addr, msg.as_string())
            else:
                with smtplib.SMTP_SSL(host, port, context=context) as server:
                    if username:
                        server.login(username, password)
                    server.sendmail(from_addr, to_addr, msg.as_string())

        try:
            await asyncio.to_thread(_send)
            self.log_info(f"Email sent to {to_addr}: {subject}")
            return {"sent": True, "error_msg": "", "exec_out": True}
        except Exception as e:
            self.log_error(f"Email failed: {e}")
            return {"sent": False, "error_msg": str(e), "exec_out": True}


def register_node():
    return Email_Notification
```

### Usage

- Configure `smtp_host`, `smtp_port`, `username`, `password` for your email provider.
- For Gmail: host = `smtp.gmail.com`, port = `587`, `use_tls` = `True`. Use an App Password, not your main account password.
- Wire `sent` to a TwoWaySwitch to branch on success/failure.
- Store credentials in `SetVariable` nodes or read them from environment variables rather than hardcoding.

---

## Example 5: Database Query Node

**Description:** Executes a parameterized SQL query against a SQLite database (or any database via configurable connection string). Returns results as a list of dicts.

### Python Code

```python
import asyncio
import sqlite3
from src.nodes.base import BaseNode


class Database_Query(BaseNode):
    name = "database_query"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("db_path",    "string", widget_type="text", default=":memory:")
        self.add_input("query",      "string", widget_type="text", default="")
        self.add_input("parameters", "list",   default=None)
        self.add_output("rows",       "list")
        self.add_output("row_count",  "int")
        self.add_output("columns",    "list")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        db_path    = inputs.get("db_path", ":memory:")
        query      = inputs.get("query", "")
        parameters = tuple(inputs.get("parameters") or [])

        if not query:
            self.log_error("No SQL query provided.")
            return {"rows": [], "row_count": 0, "columns": [], "exec_out": True}

        def _run_query():
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            try:
                cur = con.execute(query, parameters)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = [dict(row) for row in cur.fetchall()]
                else:
                    # INSERT / UPDATE / DELETE
                    con.commit()
                    columns = []
                    rows = []
                return rows, columns
            finally:
                con.close()

        try:
            rows, columns = await asyncio.to_thread(_run_query)
            self.log_info(f"Query returned {len(rows)} row(s).")
            return {
                "rows":      rows,
                "row_count": len(rows),
                "columns":   columns,
                "exec_out":  True,
            }
        except sqlite3.Error as e:
            self.log_error(f"SQL error: {e}")
            return {"rows": [], "row_count": 0, "columns": [], "exec_out": True}


def register_node():
    return Database_Query
```

### Usage

- Set `db_path` to a `.db` file path, or `":memory:"` for a temporary in-memory database.
- Set `query` to any SQL statement: `SELECT`, `INSERT`, `UPDATE`, `DELETE`, or `CREATE TABLE`.
- Wire a list into `parameters` for parameterized queries: `SELECT * FROM users WHERE id = ?` with `parameters = [42]`.
- `rows` is a list of dicts where each dict maps column name → value.
- For non-SELECT queries, `rows` is empty but the statement is committed.

---

## Example 6: Image Resizer Node

**Description:** Resizes an image file to specified dimensions using Pillow. Supports multiple resampling algorithms and optional aspect-ratio locking.

### Python Code

```python
import asyncio
import os
from src.nodes.base import BaseNode

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class Image_Resizer(BaseNode):
    name = "image_resizer"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("input_path",   "string", widget_type="text", default="")
        self.add_input("output_path",  "string", widget_type="text", default="")
        self.add_input("width",        "int",    widget_type="int",  default=1920)
        self.add_input("height",       "int",    widget_type="int",  default=1080)
        self.add_input("keep_aspect",  "bool",   widget_type="checkbox", default=True)
        self.add_input("resample",     "string", widget_type="text", default="LANCZOS")
        self.add_output("out_path",    "string")
        self.add_output("out_width",   "int")
        self.add_output("out_height",  "int")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        if not _PIL_AVAILABLE:
            self.log_error("Pillow is not installed. Run: pip install Pillow")
            return {"out_path": "", "out_width": 0, "out_height": 0, "exec_out": True}

        input_path  = inputs.get("input_path", "")
        output_path = inputs.get("output_path", "")
        target_w    = int(inputs.get("width")  or 1920)
        target_h    = int(inputs.get("height") or 1080)
        keep_aspect = inputs.get("keep_aspect", True)
        resample_str = (inputs.get("resample") or "LANCZOS").upper()

        resample_map = {
            "LANCZOS":  Image.LANCZOS,
            "BICUBIC":  Image.BICUBIC,
            "BILINEAR": Image.BILINEAR,
            "NEAREST":  Image.NEAREST,
        }
        resample = resample_map.get(resample_str, Image.LANCZOS)

        if not input_path or not os.path.isfile(input_path):
            self.log_error(f"Input file not found: {input_path}")
            return {"out_path": "", "out_width": 0, "out_height": 0, "exec_out": True}

        if not output_path:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_resized{ext}"

        def _resize():
            with Image.open(input_path) as img:
                if keep_aspect:
                    img.thumbnail((target_w, target_h), resample)
                    out_w, out_h = img.size
                else:
                    img = img.resize((target_w, target_h), resample)
                    out_w, out_h = img.size
                img.save(output_path)
            return out_w, out_h

        try:
            out_w, out_h = await asyncio.to_thread(_resize)
            self.log_info(f"Resized {input_path} → {output_path} ({out_w}x{out_h})")
            return {"out_path": output_path, "out_width": out_w, "out_height": out_h, "exec_out": True}
        except Exception as e:
            self.log_error(f"Image resize failed: {e}")
            return {"out_path": "", "out_width": 0, "out_height": 0, "exec_out": True}


def register_node():
    return Image_Resizer
```

### Usage

- Wire file paths from a File Batch Processor node into `input_path`.
- Set `output_path` explicitly or leave empty to auto-generate `{name}_resized.ext`.
- `keep_aspect=True` uses thumbnail mode — the image fits within the box without cropping.
- `keep_aspect=False` forces exact dimensions, potentially distorting the image.
- `resample` options: `LANCZOS` (best quality), `BICUBIC`, `BILINEAR`, `NEAREST` (fastest).

---

## Example 7: AI/LLM Text Generation Node

**Description:** Calls the Google Generative AI API to generate text from a prompt. Supports configurable model selection and temperature.

### Python Code

```python
import asyncio
from src.nodes.base import BaseNode

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


class LLM_Text_Generation(BaseNode):
    name = "llm_text_generation"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("api_key",    "string", widget_type="text", default="")
        self.add_input("model",      "string", widget_type="text", default="gemini-1.5-flash")
        self.add_input("prompt",     "string", widget_type="text", default="")
        self.add_input("system",     "string", widget_type="text", default="")
        self.add_input("temperature","float",  widget_type="float", default=0.7)
        self.add_input("max_tokens", "int",    widget_type="int",   default=1024)
        self.add_output("generated_text", "string")
        self.add_output("token_count",    "int")
        self.add_output("success",        "bool")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        if not _GENAI_AVAILABLE:
            self.log_error("google-generativeai not installed. Run: pip install google-generativeai")
            return {"generated_text": "", "token_count": 0, "success": False, "exec_out": True}

        api_key     = inputs.get("api_key", "")
        model_name  = inputs.get("model", "gemini-1.5-flash")
        prompt      = inputs.get("prompt", "")
        system      = inputs.get("system", "")
        temperature = float(inputs.get("temperature") or 0.7)
        max_tokens  = int(inputs.get("max_tokens") or 1024)

        if not api_key:
            import os
            api_key = os.environ.get("GOOGLE_API_KEY", "")

        if not api_key:
            self.log_error("No API key provided. Set api_key input or GOOGLE_API_KEY env var.")
            return {"generated_text": "", "token_count": 0, "success": False, "exec_out": True}

        if not prompt:
            self.log_error("No prompt provided.")
            return {"generated_text": "", "token_count": 0, "success": False, "exec_out": True}

        def _generate():
            genai.configure(api_key=api_key)

            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                system_instruction=system if system else None,
            )

            response = model.generate_content(prompt)
            text = response.text if response.text else ""
            token_count = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                token_count = response.usage_metadata.total_token_count or 0
            return text, token_count

        try:
            text, tokens = await asyncio.to_thread(_generate)
            self.log_info(f"LLM generated {len(text)} chars, ~{tokens} tokens.")
            return {
                "generated_text": text,
                "token_count":    tokens,
                "success":        True,
                "exec_out":       True,
            }
        except Exception as e:
            self.log_error(f"LLM generation failed: {e}")
            return {"generated_text": "", "token_count": 0, "success": False, "exec_out": True}


def register_node():
    return LLM_Text_Generation
```

### Usage

- Set `api_key` or set the `GOOGLE_API_KEY` environment variable.
- Available models: `gemini-1.5-flash` (fast), `gemini-1.5-pro` (more capable), `gemini-2.0-flash`.
- Wire the output of a Python Script or File Load node into `prompt` for dynamic prompts.
- Chain multiple LLM nodes: first generates a summary, second expands it, third translates.

---

## Example 8: Folder Monitor Workflow

**Description:** A workflow that watches a folder for new files, processes each new file (e.g., converts it), and logs completion. Uses Python's `watchdog` library in a polling loop.

### Workflow Structure (Text Description)

```
[Python Script: Start Monitor]
    → watches folder using watchdog.observers.Observer
    → detects new files matching *.png
    → appends new file paths to shared memory list "new_files"
    → runs in asyncio.to_thread for 30 seconds
    ↓ exec_out

[GetVariable: "new_files"]
    ↓ current_list

[ForEach: iterate new files]
    ↓ loop_exec_out (per file)

    [Image Resizer: 1920x1080]
        ↓ exec_out
    [Console Print: "Processed: {out_path}"]
        ↓ exec_out (back to ForEach loop_exec_in)

    ↓ exec_out (after loop)

[Console Print: "Monitor run complete."]
```

### Monitor Python Script Node Code

```python
import asyncio
import time
from src.nodes.base import BaseNode

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False


class Folder_Monitor(BaseNode):
    name = "folder_monitor"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("folder_path",  "string", widget_type="text", default="")
        self.add_input("pattern",      "string", widget_type="text", default="*.png")
        self.add_input("watch_seconds","int",    widget_type="int",  default=30)
        self.add_output("new_files",   "list")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        if not _WATCHDOG_AVAILABLE:
            self.log_error("watchdog not installed. Run: pip install watchdog")
            return {"new_files": [], "exec_out": True}

        import fnmatch

        folder  = inputs.get("folder_path", "")
        pattern = inputs.get("pattern", "*.png")
        seconds = int(inputs.get("watch_seconds") or 30)
        new_files = []

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    if fnmatch.fnmatch(event.src_path, pattern):
                        new_files.append(event.src_path)

        def _watch():
            observer = Observer()
            observer.schedule(Handler(), folder, recursive=False)
            observer.start()
            time.sleep(seconds)
            observer.stop()
            observer.join()

        self.log_info(f"Watching {folder} for {pattern} for {seconds}s...")
        await asyncio.to_thread(_watch)
        self.log_info(f"Monitor finished. {len(new_files)} new file(s) detected.")
        return {"new_files": new_files, "exec_out": True}


def register_node():
    return Folder_Monitor
```

### Usage

Install watchdog: `pip install watchdog`

Set `folder_path` and `pattern`. Wire `new_files` → ForEach → Image Resizer (or any processing node). Set `watch_seconds` to control how long the monitor runs each execution cycle. To run continuously, wrap the whole workflow in a WhileLoop.

---

## Example 9: Complete Houdini SOP Chain Workflow

**Description:** Create a Houdini geometry container, add a Box SOP, add a PolyExtrude SOP, wire and configure them, set display flags, cook the network, and return the final SOP path for downstream use.

### Python Code (single consolidated node for clarity)

```python
from src.nodes.base import BaseNode
from src.utils.hou_bridge import get_bridge


class Hou_SOP_Chain(BaseNode):
    name = "hou_sop_chain"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("geo_name",       "string", widget_type="text",  default="my_geo")
        self.add_input("box_size",       "float",  widget_type="float", default=1.0)
        self.add_input("extrude_dist",   "float",  widget_type="float", default=0.3)
        self.add_input("extrude_divs",   "int",    widget_type="int",   default=1)
        self.add_output("geo_path",      "string")
        self.add_output("display_sop",   "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        geo_name     = inputs.get("geo_name", "my_geo") or "my_geo"
        box_size     = float(inputs.get("box_size") or 1.0)
        extrude_dist = float(inputs.get("extrude_dist") or 0.3)
        extrude_divs = int(inputs.get("extrude_divs") or 1)

        try:
            bridge = get_bridge()

            # 1. Verify connection
            ping = bridge.ping()
            if ping.get("status") != "ok":
                self.log_error("Cannot reach Houdini.")
                return {"geo_path": "", "display_sop": "", "exec_out": True}

            # 2. Create /obj-level geo container
            geo_result = bridge.create_node("/obj", "geo", geo_name)
            geo_path   = geo_result["path"]

            # 3. Clear default children
            for child in bridge.children(geo_path):
                bridge.delete_node(child["path"])

            # 4. Box SOP
            box_result = bridge.create_node(geo_path, "box", "box1")
            box_path   = box_result["path"]
            bridge.set_parms(box_path, {
                "sizex": box_size,
                "sizey": box_size,
                "sizez": box_size,
            })

            # 5. PolyExtrude SOP
            extrude_result = bridge.create_node(geo_path, "polyextrude", "extrude1")
            extrude_path   = extrude_result["path"]
            bridge.connect_nodes(box_path, extrude_path, output=0, input_idx=0)
            bridge.set_parms(extrude_path, {
                "dist":  extrude_dist,
                "divs":  extrude_divs,
            })

            # 6. Display / render flags on the extrude SOP
            bridge.set_display_flag(extrude_path, True)
            bridge.set_render_flag(extrude_path, True)

            # 7. Cook
            bridge.cook_node(extrude_path, force=True)

            # 8. Auto-layout
            bridge.layout_children(geo_path)

            self.log_info(f"SOP chain built at {geo_path}, display SOP: {extrude_path}")
            return {
                "geo_path":    geo_path,
                "display_sop": extrude_path,
                "exec_out":    True,
            }

        except Exception as e:
            self.log_error(f"Houdini SOP chain failed: {e}")
            return {"geo_path": "", "display_sop": "", "exec_out": True}


def register_node():
    return Hou_SOP_Chain
```

### Usage

Connect the `display_sop` output to other Houdini nodes that need to reference the SOP context. Use `geo_path` when working at the Object level (e.g., for transforms or Alembic export from the Object level).

---

## Example 10: Prism Multi-Asset Publisher Workflow

**Description:** Iterates over a list of assets, resolves the export path for each, processes the asset (simulated), publishes via PrismCore, and logs the result.

### Python Code

```python
from src.nodes.base import BaseNode
from src.utils.prism_core import resolve_prism_core


class Prism_Multi_Asset_Publisher(BaseNode):
    name = "prism_multi_asset_publisher"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("asset_names",    "list")
        self.add_input("entity_type",    "string", widget_type="text", default="Asset")
        self.add_input("task",           "string", widget_type="text", default="model")
        self.add_input("version_comment","string", widget_type="text", default="")
        self.add_output("published",     "list")
        self.add_output("failed",        "list")
        self.add_output("publish_count", "int")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        core = resolve_prism_core(inputs)
        if core is None:
            self.log_error("PrismCore not available. Add prism_core_init node.")
            return {"published": [], "failed": [], "publish_count": 0, "exec_out": True}

        asset_names = list(inputs.get("asset_names") or [])
        entity_type = inputs.get("entity_type", "Asset")
        task        = inputs.get("task", "model")
        comment     = inputs.get("version_comment", "")

        published = []
        failed    = []

        for asset_name in asset_names:
            try:
                # Get export paths for this asset
                paths = core.getExportPaths(
                    entity=asset_name,
                    entityType=entity_type,
                    task=task,
                )

                if not paths:
                    failed.append({"asset": asset_name, "reason": "No export paths found"})
                    self.log_error(f"No export paths for: {asset_name}")
                    continue

                latest_path = paths[-1]

                # Publish via PrismCore
                result = core.publishProduct(
                    entity=asset_name,
                    entityType=entity_type,
                    task=task,
                    sourceFile=latest_path,
                    comment=comment or f"Published by Vibrante-Node automation",
                )

                if result and result.get("success"):
                    published.append({
                        "asset":        asset_name,
                        "source":       latest_path,
                        "publish_path": result.get("path", ""),
                        "version":      result.get("version", ""),
                    })
                    self.log_info(f"Published: {asset_name} v{result.get('version', '?')}")
                else:
                    reason = result.get("error", "Unknown error") if result else "No response"
                    failed.append({"asset": asset_name, "reason": reason})
                    self.log_error(f"Publish failed for {asset_name}: {reason}")

            except Exception as e:
                failed.append({"asset": asset_name, "reason": str(e)})
                self.log_error(f"Exception publishing {asset_name}: {e}")

        self.log_info(
            f"Multi-asset publish complete: {len(published)} succeeded, {len(failed)} failed."
        )
        return {
            "published":     published,
            "failed":        failed,
            "publish_count": len(published),
            "exec_out":      True,
        }


def register_node():
    return Prism_Multi_Asset_Publisher
```

### Usage

1. Place a `prism_core_init` node on the canvas (no wiring needed).
2. Wire a list of asset name strings into `asset_names`.
3. Set `entity_type` (`"Asset"` or `"Shot"`), `task` (e.g., `"model"`, `"rig"`, `"anim"`).
4. Connect `publish_count` to a Console Print for a summary.
5. Wire `failed` to a Python Script that formats and logs any failures.
6. Connect `published` to downstream processing (e.g., cache invalidation, email notification).
