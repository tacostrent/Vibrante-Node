"""
Fab Plugin Socket Receiver (Tier 12.9 — Fab Migration)
=======================================================
Replaces the dead Quixel/Megascans REST API with the modern Fab Plugin
socket export protocol.

How it works:
  1. Vibrante starts a TCP server on port 31337 (or the port in FabPlugins/settings_v1.json).
  2. When the user exports an asset from the Fab desktop app (or Unreal Engine's
     built-in Fab panel) with "Send to DCC / Socket Export", Fab connects to that port,
     pushes a JSON payload containing the locally-saved file paths, and disconnects.
  3. Vibrante parses the payload, queues the asset, and the local scanner picks it up.

The socket protocol (from Blender Fab plugin source):
  - Fab connects as CLIENT; Vibrante is the SERVER.
  - b'ping'    → respond with plugin version string, do not queue.
  - b'Bye Fab' → stop signal (stop the server).
  - anything else → accumulate bytes until disconnect, then parse as JSON.

Payload format:
  {
    "id":         "asset_uid_from_fab",
    "path":       "E:/local/export/dir/",
    "meshes":     [{"file": "mesh.fbx", "name": "ModelName", "material_index": 0}],
    "materials":  [{"name": "Mat", "textures": {"albedo": "tex.png", ...}}],
    "native_files": [],
    "additional_textures": [],
    "metadata": {
      "launcher": {"version": "...", "listening_port": 24563},
      "fab": {"listing": {"listingType": "3d-model", "title": "...", "format": "fbx"}},
      "megascans": {...}
    }
  }

The callback port (metadata.launcher.listening_port) is used by Fab to expect
a status reply — Vibrante sends {"status": "success", "message": "received"}.

User instructions (shown when receiver starts):
  1. Open the Fab desktop app (or open Unreal Engine with the built-in Fab panel).
  2. Browse to the asset you want in "My Library" (only owned/purchased assets).
  3. Click the Export / Send to DCC button.
  4. Choose format: "houdini", "fbx", or "obj".
  5. Vibrante will receive the exported file paths automatically.

Security rules:
  - Only binds to localhost (127.0.0.1) — not exposed to the network.
  - No credentials. Fab handles auth internally.
  - Received file paths must exist on disk before cataloguing.
"""
from __future__ import annotations

import json
import os
import pathlib
import queue
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_PLUGIN_VERSION   = "vibrante/1.0"
_DEFAULT_PORT     = 31337
_CALLBACK_TIMEOUT = 1.0   # seconds to wait when sending status back to Fab
_BUFFER_SIZE      = 4096 * 2

# Path to Fab Plugin settings — used to read the configured socket export port
_FAB_SETTINGS_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", "C:/Users/Default/AppData/Local"),
    "FabPlugins", "settings_v1.json",
)


@dataclass
class FabReceivedAsset:
    """An asset received via the Fab Plugin socket export."""
    asset_id:     str   = ""
    name:         str   = ""
    asset_type:   str   = ""          # "3d-model", "material", etc.
    export_path:  str   = ""          # local directory where files were saved
    mesh_files:   List[str] = field(default_factory=list)   # full paths
    texture_files: List[str] = field(default_factory=list)  # full paths
    native_files: List[str] = field(default_factory=list)
    format:       str   = ""          # "fbx", "obj", "usd", ...
    quality:      str   = ""          # "2K", "4K", ...
    tags:         List[str] = field(default_factory=list)
    is_quixel:    bool  = False
    received_at:  float = field(default_factory=time.time)
    raw_payload:  Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     str(self.asset_id),
            "name":         str(self.name),
            "asset_type":   str(self.asset_type),
            "export_path":  str(self.export_path),
            "mesh_files":   list(self.mesh_files),
            "texture_files": list(self.texture_files),
            "native_files": list(self.native_files),
            "format":       str(self.format),
            "quality":      str(self.quality),
            "tags":         list(self.tags),
            "is_quixel":    bool(self.is_quixel),
            "received_at":  float(self.received_at),
        }

    def primary_mesh(self) -> str:
        """Return the first available mesh file path, or ''."""
        for f in self.mesh_files:
            if os.path.isfile(f):
                return f
        return ""

    def to_asset_descriptor(self) -> Dict[str, Any]:
        """Convert to a basic AssetDescriptor-compatible dict for the catalog."""
        return {
            "asset_id":    self.asset_id or pathlib.Path(self.export_path).name,
            "name":        self.name or pathlib.Path(self.export_path).name,
            "provider":    "fab",
            "category":    self.asset_type or "prop",
            "local_path":  self.export_path,
            "mesh_path":   self.primary_mesh(),
            "format":      self.format,
            "quality":     self.quality,
            "tags":        self.tags,
            "source":      "fab_socket",
        }


def _read_socket_export_port() -> int:
    """Read the socketExport port from FabPlugins/settings_v1.json. Never raises."""
    try:
        if os.path.isfile(_FAB_SETTINGS_PATH):
            with open(_FAB_SETTINGS_PATH, encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            return int(data.get("plugins", {}).get("socketExport", {}).get("port") or _DEFAULT_PORT)
    except Exception:
        pass
    return _DEFAULT_PORT


def _parse_payload(raw: bytes) -> Optional[Dict[str, Any]]:
    """Parse raw bytes as JSON. Never raises."""
    try:
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        return json.loads(text)
    except Exception:
        return None


def _normalize_payload(data: Dict[str, Any]) -> FabReceivedAsset:
    """Convert Fab JSON payload to FabReceivedAsset. Never raises."""
    try:
        asset_id   = str(data.get("id") or "")
        export_dir = str(data.get("path") or "")

        meta = data.get("metadata") or {}
        fab_meta = meta.get("fab") or {}
        listing  = fab_meta.get("listing") or {}
        ms_meta  = meta.get("megascans") or {}

        name       = str(listing.get("title") or ms_meta.get("name") or asset_id)
        asset_type = str(listing.get("listingType") or "3d-model")
        fmt        = str(fab_meta.get("format") or "fbx").lower()
        quality    = str(fab_meta.get("quality") or "")
        is_quixel  = bool(fab_meta.get("isQuixel") or ms_meta)
        tags_raw   = listing.get("tags") or []
        tags = [str(t.get("slug") or t) for t in tags_raw if t]

        # Collect mesh file paths (absolute: export_dir + relative filename)
        mesh_files: List[str] = []
        for mesh in (data.get("meshes") or []):
            f = str(mesh.get("file") or "")
            if f:
                full = f if os.path.isabs(f) else os.path.join(export_dir, f)
                mesh_files.append(full)

        # Collect texture paths
        tex_files: List[str] = []
        for mat in (data.get("materials") or []):
            for ch, path in (mat.get("textures") or {}).items():
                if path:
                    full = str(path) if os.path.isabs(str(path)) else os.path.join(export_dir, str(path))
                    tex_files.append(full)
        for t in (data.get("additional_textures") or []):
            if t:
                full = str(t) if os.path.isabs(str(t)) else os.path.join(export_dir, str(t))
                tex_files.append(full)

        native = [
            (str(f) if os.path.isabs(str(f)) else os.path.join(export_dir, str(f)))
            for f in (data.get("native_files") or []) if f
        ]

        return FabReceivedAsset(
            asset_id=asset_id,
            name=name,
            asset_type=asset_type,
            export_path=export_dir,
            mesh_files=mesh_files,
            texture_files=tex_files,
            native_files=native,
            format=fmt,
            quality=quality,
            tags=tags,
            is_quixel=is_quixel,
            raw_payload=dict(data),
        )
    except Exception:
        return FabReceivedAsset(raw_payload=dict(data) if isinstance(data, dict) else {})


def _send_callback(launcher_port: int, asset_id: str, export_path: str) -> None:
    """Send success status back to Fab Launcher. Best-effort, never raises."""
    try:
        payload = json.dumps({
            "status":     "success",
            "message":    "Asset received by Vibrante-Node",
            "id":         asset_id,
            "path":       export_path,
            "app_name":   "vibrante",
            "app_version": "1.0",
        }) + "\0"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(_CALLBACK_TIMEOUT)
            s.connect(("localhost", launcher_port))
            s.sendall(payload.encode("utf-8"))
    except Exception:
        pass


class FabSocketReceiver:
    """
    TCP socket server that receives asset exports pushed from the Fab desktop app.

    Usage:
        receiver = get_fab_socket_receiver()
        receiver.start()
        # ... later ...
        assets = receiver.get_received_assets()   # list of FabReceivedAsset
    """

    def __init__(self) -> None:
        self._lock            = threading.Lock()
        self._port            = _read_socket_export_port()
        self._server_socket:  Optional[socket.socket] = None
        self._should_stop     = threading.Event()
        self._thread:         Optional[threading.Thread] = None
        self._queue:          "queue.Queue[FabReceivedAsset]" = queue.Queue()
        self._received_count  = 0
        self._started_at:     float = 0.0
        self._last_asset_at:  float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def port(self) -> int:
        return self._port

    def is_running(self) -> bool:
        """True if the socket server is actively listening."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """
        Start the socket server in a background daemon thread.
        Returns True on success, False if already running or port is in use.
        Never raises.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True   # already running
        try:
            self._should_stop.clear()
            t = threading.Thread(target=self._serve, daemon=True,
                                 name="FabSocketReceiver")
            t.start()
            self._started_at = time.time()
            with self._lock:
                self._thread = t
            return True
        except Exception:
            return False

    def stop(self) -> None:
        """Signal the server to stop. Never raises."""
        try:
            self._should_stop.set()
            with self._lock:
                ss = self._server_socket
            if ss:
                try:
                    ss.close()
                except Exception:
                    pass
        except Exception:
            pass

    def get_received_assets(self, drain: bool = True) -> List[FabReceivedAsset]:
        """
        Return all assets received since last call.
        drain=True (default): empties the queue.
        drain=False: peeks without consuming.
        """
        assets: List[FabReceivedAsset] = []
        try:
            if drain:
                while not self._queue.empty():
                    try:
                        assets.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            else:
                with self._lock:
                    assets = list(self._queue.queue)
        except Exception:
            pass
        return assets

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running":        self._thread is not None and self._thread.is_alive(),
                "port":           self._port,
                "received_count": self._received_count,
                "queue_size":     self._queue.qsize(),
                "started_at":     self._started_at,
                "last_asset_at":  self._last_asset_at,
            }

    # ------------------------------------------------------------------
    # Socket server loop
    # ------------------------------------------------------------------

    def _serve(self) -> None:
        """Main server loop — runs in background thread. Never raises."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", self._port))
            srv.settimeout(2.0)   # so we can check _should_stop regularly
            srv.listen(5)
            with self._lock:
                self._server_socket = srv

            while not self._should_stop.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break   # socket was closed — stop
                threading.Thread(
                    target=self._handle_connection,
                    args=(conn,),
                    daemon=True,
                ).start()
        except OSError as e:
            # Port already in use is common — log but don't crash
            print(f"FabSocketReceiver: could not bind to port {self._port}: {e}")
        except Exception:
            pass
        finally:
            try:
                if self._server_socket:
                    self._server_socket.close()
            except Exception:
                pass

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle one incoming connection from Fab. Never raises."""
        try:
            buffered = b""
            conn.settimeout(10.0)
            while True:
                try:
                    chunk = conn.recv(_BUFFER_SIZE)
                except socket.timeout:
                    break
                if not chunk:
                    break

                # Special Fab control messages
                if chunk == b"ping":
                    try:
                        conn.sendall(_PLUGIN_VERSION.encode("utf-8"))
                    except Exception:
                        pass
                    return
                if chunk == b"Bye Fab":
                    self._should_stop.set()
                    return

                buffered += chunk

            # Connection closed — parse accumulated data as JSON payload
            if buffered:
                data = _parse_payload(buffered)
                if data:
                    asset = _normalize_payload(data)
                    self._queue.put(asset)
                    with self._lock:
                        self._received_count += 1
                        self._last_asset_at = time.time()

                    # Send success callback to Fab Launcher
                    launcher_port = int(
                        (data.get("metadata") or {})
                        .get("launcher", {})
                        .get("listening_port") or 24563
                    )
                    _send_callback(launcher_port, asset.asset_id, asset.export_path)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_INSTANCE: Optional[FabSocketReceiver] = None
_INSTANCE_LOCK = threading.Lock()


def get_fab_socket_receiver() -> FabSocketReceiver:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = FabSocketReceiver()
    return _INSTANCE


def reset_fab_socket_receiver_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is not None:
            _INSTANCE.stop()
        _INSTANCE = None
