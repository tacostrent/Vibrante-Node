"""
Houdini Bridge Client
=====================
Communicates with the Vibrante-Node command server running inside Houdini.
Used by Houdini-specific nodes to create/modify nodes in the live session.

The server must be running inside Houdini (vibrante_hou_server.start()).
When Vibrante-Node is launched from Houdini, the server starts automatically
and the port is passed via the VIBRANTE_HOU_PORT environment variable.

Usage inside node python_code:
    from src.utils.hou_bridge import get_bridge
    bridge = get_bridge()
    result = bridge.create_node("/obj", "geo", "my_geo")
"""

import json
import os
import socket

DEFAULT_PORT = 18811


class HouBridge:
    """Client for the Houdini command server."""

    def __init__(self, host="127.0.0.1", port=None):
        self.host = host
        self.port = port or int(os.environ.get("VIBRANTE_HOU_PORT", DEFAULT_PORT))
        self._sock = None
        self._id = 0
        self._lock = __import__("threading").Lock()

    def connect(self):
        if self._sock:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(30)
        sock.connect((self.host, self.port))
        self._sock = sock

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _send(self, method, params=None):
        """Send a JSON-RPC request and return the result."""
        with self._lock:
            return self._send_locked(method, params)

    def _send_locked(self, method, params=None):
        if not self._sock:
            self.connect()

        self._id += 1
        request = {"method": method, "params": params or {}, "id": self._id}
        payload = json.dumps(request).encode("utf-8") + b"\n"

        try:
            self._sock.sendall(payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Reconnect once and retry
            self.disconnect()
            self.connect()
            try:
                self._sock.sendall(payload)
            except OSError as e:
                raise ConnectionError(f"Houdini bridge reconnect failed: {e}") from e

        # Read response (newline-delimited); recv may need multiple calls for
        # large payloads (e.g. get_parms on a complex node).
        buf = b""
        try:
            while b"\n" not in buf:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionError("Houdini command server closed connection")
                buf += chunk
        except socket.timeout:
            # Server took longer than 30 s — disconnect so next call reconnects.
            self.disconnect()
            raise ConnectionError(
                f"Houdini command server timed out on method '{method}'. "
                "Check that Houdini is responsive and not blocked on a long cook."
            )
        except OSError as e:
            self.disconnect()
            raise ConnectionError(f"Houdini bridge recv error: {e}") from e

        line = buf.split(b"\n")[0]
        response = json.loads(line.decode("utf-8"))

        if "error" in response and response["error"]:
            raise RuntimeError(f"Houdini: {response['error']}")

        return response.get("result")

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    def ping(self):
        """Check if the server is alive."""
        return self._send("ping")

    def create_node(self, parent, node_type, name=""):
        """Create a new node in the Houdini scene."""
        return self._send("create_node", {
            "parent": parent, "type": node_type, "name": name
        })

    def delete_node(self, path):
        """Delete a node."""
        return self._send("delete_node", {"path": path})

    def set_parm(self, node, parm, value):
        """Set a single parameter value."""
        return self._send("set_parm", {"node": node, "parm": parm, "value": value})

    def get_parm(self, node, parm):
        """Get a single parameter value."""
        return self._send("get_parm", {"node": node, "parm": parm})

    def set_parms(self, node, parms):
        """Set multiple parameters at once."""
        return self._send("set_parms", {"node": node, "parms": parms})

    def get_parms(self, node):
        """Get all parameter values."""
        return self._send("get_parms", {"node": node})

    def connect_nodes(self, from_node, to_node, output=0, input_idx=0):
        """Connect output of one node to input of another."""
        return self._send("connect_nodes", {
            "from": from_node, "to": to_node,
            "output": output, "input": input_idx
        })

    def cook_node(self, path, force=False):
        """Force cook a node."""
        return self._send("cook_node", {"path": path, "force": force})

    def run_code(self, code):
        """Execute arbitrary Python code in Houdini."""
        return self._send("run_code", {"code": code})

    def scene_info(self):
        """Get current scene information."""
        return self._send("scene_info")

    def node_info(self, path):
        """Get detailed info about a node."""
        return self._send("node_info", {"path": path})

    def children(self, path="/obj"):
        """List child nodes."""
        return self._send("children", {"path": path})

    def node_exists(self, path):
        """Check if a node exists."""
        return self._send("node_exists", {"path": path})

    def set_display_flag(self, path, on=True):
        """Set the display flag on a node."""
        return self._send("set_display_flag", {"path": path, "on": on})

    def set_render_flag(self, path, on=True):
        """Set the render flag on a node."""
        return self._send("set_render_flag", {"path": path, "on": on})

    def layout_children(self, path="/obj"):
        """Auto-layout child nodes."""
        return self._send("layout_children", {"path": path})

    def save_hip(self, path=""):
        """Save the current HIP file."""
        return self._send("save_hip", {"path": path})

    def set_expression(self, node, parm, expression, language="hscript"):
        """Set a parameter expression."""
        return self._send("set_expression", {
            "node": node, "parm": parm,
            "expression": expression, "language": language
        })

    def set_keyframe(self, node, parm, frame, value):
        """Set a keyframe on a parameter."""
        return self._send("set_keyframe", {
            "node": node, "parm": parm,
            "frame": frame, "value": value
        })

    def set_frame(self, frame):
        """Set the current frame."""
        return self._send("set_frame", {"frame": frame})

    def set_playback_range(self, start, end):
        """Set the playback frame range."""
        return self._send("set_playback_range", {"start": start, "end": end})

    def get_completions(self, prefix=""):
        """Fetch auto-complete suggestions from Houdini."""
        return self._send("get_completions", {"prefix": prefix})

    def get_selection(self):
        """Return the list of currently selected node paths.

        In headless / batch Houdini there is no UI selection, so this always
        returns []. Used by the runtime layer's scene_context aggregator.
        """
        result = self._send("get_selection", {})
        if isinstance(result, dict):
            return list(result.get("paths") or [])
        return list(result or [])

    def network_summary(self, path):
        """Return children of `path` with name + type + path + category in one call.

        Cheaper than calling children() and then node_info() per child, because
        category lookup happens server-side. Used by the runtime layer to build
        per-network listings for scene_context.
        """
        return self._send("network_summary", {"path": path})

    def call(self, path, *args, **kwargs):
        """Call any Houdini API method dynamically.
        
        Example: bridge.call("node", "/obj").call("createNode", "geo")
        Wait, better to just pass the full path:
        bridge.call("node('/obj').createNode", "geo")
        """
        return self._send("call", {"path": path, "args": args, "kwargs": kwargs})


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_bridge = None


def get_bridge():
    """Get or create the global HouBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = HouBridge()
    return _bridge


def is_available():
    """Check if the Houdini command server is reachable."""
    try:
        bridge = get_bridge()
        bridge.ping()
        return True
    except Exception:
        return False
