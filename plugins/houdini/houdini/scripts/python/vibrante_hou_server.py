"""
Vibrante-Node Houdini Command Server
=====================================
Runs inside Houdini's Python process and listens for JSON-RPC commands
from the Vibrante-Node subprocess.  All hou operations are executed on
Houdini's main thread via hdefereval.executeDeferred().

Usage (automatic -- called by launch functions):
    import vibrante_hou_server
    vibrante_hou_server.start()        # start on default port
    vibrante_hou_server.stop()         # stop the server
    vibrante_hou_server.is_running()   # check status

Manual usage from Houdini Python Shell:
    import vibrante_hou_server; vibrante_hou_server.start()
"""

import json
import os
import socket
import threading
import traceback

import hou
import hdefereval

DEFAULT_PORT = 18811

_server_socket = None
_server_thread = None
_running = False
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Command handlers -- each receives a dict of params and returns a result.
# These run on Houdini's MAIN thread (deferred via hdefereval).
# ---------------------------------------------------------------------------

def _cmd_ping(params):
    return {"status": "ok", "version": hou.applicationVersionString()}


def _cmd_create_node(params):
    parent_path = params.get("parent", "/obj")
    node_type = params["type"]
    name = params.get("name", "")

    parent = hou.node(parent_path)
    if not parent:
        raise ValueError(f"Parent node not found: {parent_path}")

    node = parent.createNode(node_type, name or None)
    if params.get("move_to_end", True):
        node.moveToGoodPosition()

    return {"path": node.path(), "name": node.name(), "type": node.type().name()}


def _cmd_delete_node(params):
    node = hou.node(params["path"])
    if not node:
        raise ValueError(f"Node not found: {params['path']}")
    node.destroy()
    return {"deleted": params["path"]}


def _cmd_set_parm(params):
    node = hou.node(params["node"])
    if not node:
        raise ValueError(f"Node not found: {params['node']}")

    parm = node.parm(params["parm"])
    if parm is None:
        # Try parmTuple for vector parms
        pt = node.parmTuple(params["parm"])
        if pt is None:
            raise ValueError(f"Parameter not found: {params['parm']} on {params['node']}")
        pt.set(params["value"])
    else:
        parm.set(params["value"])
    return {"set": True}


def _cmd_get_parm(params):
    node = hou.node(params["node"])
    if not node:
        raise ValueError(f"Node not found: {params['node']}")
    parm = node.parm(params["parm"])
    if parm is None:
        pt = node.parmTuple(params["parm"])
        if pt is None:
            raise ValueError(f"Parameter not found: {params['parm']}")
        return {"value": list(pt.eval())}
    return {"value": parm.eval()}


def _cmd_set_parms(params):
    node = hou.node(params["node"])
    if not node:
        raise ValueError(f"Node not found: {params['node']}")
    parm_dict = params.get("parms", {})
    node.setParms(parm_dict)
    return {"set": True, "count": len(parm_dict)}


def _cmd_get_parms(params):
    node = hou.node(params["node"])
    if not node:
        raise ValueError(f"Node not found: {params['node']}")
    result = {}
    for parm in node.parms():
        try:
            val = parm.eval()
            # Ensure JSON-serializable
            json.dumps(val)
            result[parm.name()] = val
        except (TypeError, ValueError):
            result[parm.name()] = str(parm.rawValue())
    return result


def _cmd_connect_nodes(params):
    src = hou.node(params["from"])
    dst = hou.node(params["to"])
    if not src:
        raise ValueError(f"Source node not found: {params['from']}")
    if not dst:
        raise ValueError(f"Destination node not found: {params['to']}")

    output_idx = params.get("output", 0)
    input_idx = params.get("input", 0)
    dst.setInput(input_idx, src, output_idx)
    return {"connected": True}


def _cmd_cook_node(params):
    node = hou.node(params["path"])
    if not node:
        raise ValueError(f"Node not found: {params['path']}")
    node.cook(force=params.get("force", False))
    return {"cooked": True}


def _cmd_run_code(params):
    code = params["code"]
    local_ns = {"hou": hou, "result": None}
    exec(code, {"__builtins__": __builtins__, "hou": hou}, local_ns)
    result = local_ns.get("result")
    # Ensure JSON-serializable
    if result is not None:
        try:
            json.dumps(result)
        except (TypeError, ValueError):
            result = str(result)
    return {"result": result}


def _cmd_scene_info(params):
    # hou.playbar is only available in interactive (GUI) Houdini sessions.
    # In hbatch / hython / headless builds it raises AttributeError.
    try:
        frame_range = list(hou.playbar.frameRange())
    except AttributeError:
        frame_range = [1, 240]
    return {
        "hip_file": hou.hipFile.path(),
        "hip_name": hou.hipFile.basename(),
        "houdini_version": hou.applicationVersionString(),
        "fps": hou.fps(),
        "frame": hou.frame(),
        "frame_range": frame_range,
    }


def _cmd_node_info(params):
    node = hou.node(params["path"])
    if not node:
        raise ValueError(f"Node not found: {params['path']}")
    return {
        "path": node.path(),
        "name": node.name(),
        "type": node.type().name(),
        "category": node.type().category().name(),
        "input_connectors": len(node.inputConnectors()),
        "output_connectors": len(node.outputConnectors()),
        "inputs": [c.path() if c else None for c in node.inputs()],
        "outputs": [c.path() for c in node.outputs()],
        "children": [c.name() for c in node.children()],
    }


def _cmd_children(params):
    node = hou.node(params.get("path", "/obj"))
    if not node:
        raise ValueError(f"Node not found: {params.get('path')}")
    return [
        {"name": c.name(), "type": c.type().name(), "path": c.path()}
        for c in node.children()
    ]


def _cmd_node_exists(params):
    return {"exists": hou.node(params["path"]) is not None}


def _cmd_set_display_flag(params):
    node = hou.node(params["path"])
    if not node:
        raise ValueError(f"Node not found: {params['path']}")
    # Not all node types support the display flag (e.g. Object-level nodes
    # only have it on their children).  Guard to avoid hou.OperationFailed.
    if not callable(getattr(node, "setDisplayFlag", None)):
        raise ValueError(f"Node does not support display flag: {params['path']}")
    try:
        node.setDisplayFlag(params.get("on", True))
    except hou.OperationFailed as e:
        raise ValueError(f"Cannot set display flag on {params['path']}: {e}") from e
    return {"set": True}


def _cmd_set_render_flag(params):
    node = hou.node(params["path"])
    if not node:
        raise ValueError(f"Node not found: {params['path']}")
    if not callable(getattr(node, "setRenderFlag", None)):
        raise ValueError(f"Node does not support render flag: {params['path']}")
    try:
        node.setRenderFlag(params.get("on", True))
    except hou.OperationFailed as e:
        raise ValueError(f"Cannot set render flag on {params['path']}: {e}") from e
    return {"set": True}


def _cmd_layout_children(params):
    node = hou.node(params.get("path", "/obj"))
    if not node:
        raise ValueError(f"Node not found: {params.get('path')}")
    node.layoutChildren()
    return {"done": True}


def _cmd_save_hip(params):
    path = params.get("path", "")
    if path:
        hou.hipFile.save(path)
    else:
        hou.hipFile.save()
    return {"saved": hou.hipFile.path()}


def _cmd_set_expression(params):
    node = hou.node(params["node"])
    if not node:
        raise ValueError(f"Node not found: {params['node']}")
    parm = node.parm(params["parm"])
    if not parm:
        raise ValueError(f"Parameter not found: {params['parm']}")
    lang = params.get("language", "hscript")
    if lang.lower() == "python":
        parm.setExpression(params["expression"], hou.exprLanguage.Python)
    else:
        parm.setExpression(params["expression"], hou.exprLanguage.Hscript)
    return {"set": True}


def _cmd_set_keyframe(params):
    node = hou.node(params["node"])
    if not node:
        raise ValueError(f"Node not found: {params['node']}")
    parm = node.parm(params["parm"])
    if not parm:
        raise ValueError(f"Parameter not found: {params['parm']}")
    key = hou.Keyframe()
    key.setFrame(params["frame"])
    key.setValue(params["value"])
    parm.setKeyframe(key)
    return {"set": True}


def _cmd_set_frame(params):
    hou.setFrame(params["frame"])
    return {"frame": hou.frame()}


def _cmd_set_playback_range(params):
    start = params["start"]
    end = params["end"]
    hou.playbar.setFrameRange(start, end)
    hou.playbar.setPlaybackRange(start, end)
    return {"start": start, "end": end}


def _cmd_get_completions(params):
    """Fetch available members of the hou module for auto-complete."""
    prefix = params.get("prefix", "")
    try:
        if "." in prefix:
            # Handle nested members like hou.node.
            parts = prefix.split(".")
            obj = hou
            for p in parts[:-1]:
                if not p: continue
                obj = getattr(obj, p)
            members = dir(obj)
        else:
            members = dir(hou)
        
        # Filter and ensure JSON serializable
        return [m for m in members if not m.startswith("__")]
    except Exception as e:
        return {"error": str(e), "members": []}


def _cmd_get_selection(params):
    """Return the list of currently selected node paths.

    Headless / batch Houdini does not support hou.selectedNodes() — guard
    so the runtime's scene_context aggregator can call this safely in any
    session mode.
    """
    selected = getattr(hou, "selectedNodes", None)
    if selected is None or not callable(selected):
        return {"paths": []}
    try:
        nodes = selected()
    except (AttributeError, hou.OperationFailed):
        return {"paths": []}
    return {"paths": [n.path() for n in nodes]}


def _cmd_network_summary(params):
    """Children of `path` returned with name + type + path + category.

    Single round-trip alternative to calling `children` + `node_info` per
    child. Used by the runtime scene_context layer.
    """
    parent = hou.node(params.get("path", "/obj"))
    if not parent:
        raise ValueError(f"Node not found: {params.get('path')}")
    out = []
    for c in parent.children():
        try:
            category = c.type().category().name()
        except Exception:
            category = ""
        out.append({
            "name": c.name(),
            "type": c.type().name(),
            "path": c.path(),
            "category": category,
        })
    return out


def _cmd_call(params):
    """Call an arbitrary Houdini API method dynamically."""
    path = params["path"] # e.g. "node", "hipFile.save"
    args = params.get("args", [])
    kwargs = params.get("kwargs", {})
    
    try:
        parts = path.split(".")
        func = hou
        for p in parts:
            func = getattr(func, p)
            
        result = func(*args, **kwargs)
        
        # Handle some common Houdini return types that aren't JSON-serializable
        if hasattr(result, "path") and callable(result.path): # It's a Node
            return {"type": "node", "path": result.path()}
        if hasattr(result, "eval") and callable(result.eval): # It's a Parm
            return {"type": "parm", "value": result.eval()}
            
        try:
            json.dumps(result)
            return result
        except (TypeError, ValueError):
            return str(result)
    except Exception as e:
        raise RuntimeError(f"Dynamic call failed: {e}")


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_COMMANDS = {
    "ping":               _cmd_ping,
    "create_node":        _cmd_create_node,
    "delete_node":        _cmd_delete_node,
    "set_parm":           _cmd_set_parm,
    "get_parm":           _cmd_get_parm,
    "set_parms":          _cmd_set_parms,
    "get_parms":          _cmd_get_parms,
    "connect_nodes":      _cmd_connect_nodes,
    "cook_node":          _cmd_cook_node,
    "run_code":           _cmd_run_code,
    "scene_info":         _cmd_scene_info,
    "node_info":          _cmd_node_info,
    "children":           _cmd_children,
    "node_exists":        _cmd_node_exists,
    "set_display_flag":   _cmd_set_display_flag,
    "set_render_flag":    _cmd_set_render_flag,
    "layout_children":    _cmd_layout_children,
    "save_hip":           _cmd_save_hip,
    "set_expression":     _cmd_set_expression,
    "set_keyframe":       _cmd_set_keyframe,
    "set_frame":          _cmd_set_frame,
    "set_playback_range": _cmd_set_playback_range,
    "get_completions":    _cmd_get_completions,
    "get_selection":      _cmd_get_selection,
    "network_summary":    _cmd_network_summary,
    "call":               _cmd_call,
}


# ---------------------------------------------------------------------------
# Connection handler (runs in its own thread per client)
# ---------------------------------------------------------------------------

def _handle_client(conn, addr):
    """Read newline-delimited JSON commands and dispatch them."""
    buffer = b""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buffer += data

            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    request = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as e:
                    resp = json.dumps({"error": f"Invalid JSON: {e}", "id": None})
                    conn.sendall(resp.encode("utf-8") + b"\n")
                    continue

                method = request.get("method", "")
                params = request.get("params", {})
                req_id = request.get("id", 0)

                handler = _COMMANDS.get(method)
                if not handler:
                    resp = json.dumps({"error": f"Unknown method: {method}", "id": req_id})
                    conn.sendall(resp.encode("utf-8") + b"\n")
                    continue

                # Execute on Houdini's main thread and wait for result
                result_box = {"result": None, "error": None, "done": False}
                event = threading.Event()

                def _run(h=handler, p=params, box=result_box, evt=event):
                    try:
                        box["result"] = h(p)
                    except Exception as exc:
                        import traceback
                        box["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                    box["done"] = True
                    evt.set()

                hdefereval.executeDeferred(_run)
                event.wait(timeout=30)

                if not result_box["done"]:
                    resp = {"error": "Timeout waiting for Houdini main thread", "id": req_id}
                elif result_box["error"]:
                    resp = {"error": result_box["error"], "id": req_id}
                else:
                    resp = {"result": result_box["result"], "id": req_id}

                conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Server loop (background thread)
# ---------------------------------------------------------------------------

def _accept_loop(server_sock):
    """Accept client connections in a background thread."""
    global _running
    server_sock.settimeout(1.0)
    while _running:
        try:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=_handle_client, args=(conn, addr), daemon=True)
            t.start()
        except socket.timeout:
            continue
        except OSError:
            break


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start(port=None):
    """Start the Houdini command server.

    Args:
        port: TCP port to listen on (default: 18811 or VIBRANTE_HOU_PORT env)

    Returns:
        int: The port the server is listening on, or None on failure.
    """
    global _server_socket, _server_thread, _running

    with _lock:
        if _running and _server_socket:
            p = _server_socket.getsockname()[1]
            print(f"[Vibrante-Node] Command server already running on port {p}")
            return p

        if port is None:
            port = int(os.environ.get("VIBRANTE_HOU_PORT", DEFAULT_PORT))

        try:
            _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _server_socket.bind(("127.0.0.1", port))
            _server_socket.listen(5)
        except OSError as e:
            print(f"[Vibrante-Node] Failed to start server on port {port}: {e}")
            _server_socket = None
            return None

        _running = True
        _server_thread = threading.Thread(target=_accept_loop, args=(_server_socket,), daemon=True)
        _server_thread.start()

        print(f"[Vibrante-Node] Command server started on 127.0.0.1:{port}")
        return port


def stop():
    """Stop the Houdini command server."""
    global _server_socket, _server_thread, _running

    with _lock:
        _running = False

        if _server_socket:
            try:
                _server_socket.close()
            except OSError:
                pass
            _server_socket = None

    if _server_thread:
        _server_thread.join(timeout=5)
        _server_thread = None

    print("[Vibrante-Node] Command server stopped")


def is_running():
    """Check if the command server is currently running."""
    return _running and _server_socket is not None


def get_port():
    """Return the port the server is listening on, or None."""
    if _server_socket:
        try:
            return _server_socket.getsockname()[1]
        except OSError:
            pass
    return None
