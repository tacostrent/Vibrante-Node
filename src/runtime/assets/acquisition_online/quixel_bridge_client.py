"""
Quixel Bridge Local Client (Tier 12.9)
=========================================
Connects to the Quixel Bridge / Fab Bridge standalone application running
on localhost:28241.

Why this path:
  - Bridge handles Epic/Quixel authentication automatically.
  - Bridge manages format selection (FBX / OBJ / USD / raw textures).
  - Assets land locally with the correct folder structure.
  - No API credentials needed in Vibrante — just have Bridge open.

How Bridge works:
  - Bridge hosts an HTTP server on port 28241.
  - DCCs (Houdini, Maya, Blender) connect to request or receive asset exports.
  - You can POST a JSON payload to request a specific asset by ID and format.
  - Bridge downloads if needed, then pushes the export paths back.

Three access modes (in priority order):
  1. Bridge running  → POST localhost:28241 with asset request.
  2. Bridge not running → fall back to Megascans Web REST API.
  3. Both unavailable → return offline advisory.

Injectable transport for tests:
  client._transport = MyMockTransport()
  # transport.post(url, payload) → dict
  # transport.get(url) → dict
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_BRIDGE_PORT    = 28241               # Old Quixel Bridge (deprecated)
_FAB_PLUGIN_PORT = 31337              # New Fab Plugin socketExport
_BRIDGE_BASE    = f"http://localhost:{_BRIDGE_PORT}"
_TIMEOUT        = 5   # seconds — Bridge should respond instantly if running


def _read_fab_plugin_port() -> int:
    """Read socketExport port from FabPlugins/settings_v1.json. Returns 31337 on any error."""
    try:
        import json as _json
        settings_path = os.path.join(
            os.environ.get("LOCALAPPDATA", "C:/Users/Default/AppData/Local"),
            "FabPlugins", "settings_v1.json",
        )
        if os.path.isfile(settings_path):
            with open(settings_path, encoding="utf-8", errors="replace") as f:
                data = _json.load(f)
            return int(data.get("plugins", {}).get("socketExport", {}).get("port") or _FAB_PLUGIN_PORT)
    except Exception:
        pass
    return _FAB_PLUGIN_PORT


@dataclass
class BridgeExportResult:
    ok:          bool  = False
    asset_id:    str   = ""
    name:        str   = ""
    asset_type:  str   = ""
    mesh_path:   str   = ""          # primary importable file (FBX/OBJ/USD)
    texture_paths: List[str] = field(default_factory=list)
    export_dir:  str   = ""
    source:      str   = "bridge"
    error:       str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":            bool(self.ok),
            "asset_id":      str(self.asset_id),
            "name":          str(self.name),
            "asset_type":    str(self.asset_type),
            "mesh_path":     str(self.mesh_path),
            "texture_paths": list(self.texture_paths),
            "export_dir":    str(self.export_dir),
            "source":        str(self.source),
            "error":         str(self.error),
        }


class QuixelBridgeClient:
    """
    Thin HTTP client for the Quixel Bridge local server (localhost:28241).

    Designed to be used as the FIRST acquisition step before the web REST API.
    Injectable transport for offline tests.
    """

    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._export_count = 0
        self._transport: Optional[Any] = None   # Injectable for tests

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_bridge_running(self) -> bool:
        """Return True if Quixel Bridge (port 28241) is listening. Never raises."""
        try:
            result = self._get(f"{_BRIDGE_BASE}/")
            return result is not None
        except Exception:
            return False

    def is_fab_plugin_active(self) -> bool:
        """
        Return True if the Fab Plugin socket export server is already running
        on its configured port (default 31337).  This means EITHER:
          - The Vibrante FabSocketReceiver is listening, OR
          - Another DCC plugin (Houdini, UE5) already owns the port.
        Never raises.
        """
        try:
            import socket as _socket
            port = _read_fab_plugin_port()
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.settimeout(1.0)
            result = s.connect_ex(("127.0.0.1", port))
            s.close()
            return result == 0
        except Exception:
            return False

    def get_pending_fab_assets(self) -> List[Dict[str, Any]]:
        """
        Return any assets queued in the Fab socket receiver (pushed from Fab app).
        Drains the queue. Never raises.
        """
        try:
            from .fab_socket_receiver import get_fab_socket_receiver
            receiver = get_fab_socket_receiver()
            return [a.to_dict() for a in receiver.get_received_assets(drain=True)]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Asset search through Bridge
    # ------------------------------------------------------------------

    def search_assets(
        self,
        query:    str,
        limit:    int = 20,
        asset_type: str = "",     # "3d", "surface", "decal", etc.
    ) -> List[Dict[str, Any]]:
        """
        Search Megascans assets accessible through Bridge.
        Returns a list of raw asset dicts. Never raises.
        """
        try:
            params: Dict[str, Any] = {"query": str(query), "limit": int(limit)}
            if asset_type:
                params["type"] = str(asset_type)
            result = self._get(f"{_BRIDGE_BASE}/api/v1/assets", params=params)
            if not result:
                return []
            raw_list = result.get("assets") or result.get("results") or []
            return [r for r in raw_list if isinstance(r, dict)]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Export request (trigger Bridge to download + export an asset)
    # ------------------------------------------------------------------

    def export_asset(
        self,
        asset_id:   str,
        export_dir: str,
        quality:    str = "2K",
        fmt:        str = "fbx",
    ) -> BridgeExportResult:
        """
        Request Bridge to export a specific asset to export_dir.

        Bridge will:
          1. Download the asset if not already in its cache.
          2. Convert to the requested format.
          3. Write files to export_dir.
          4. Return the file paths in its response.

        Never raises.
        """
        try:
            asset_id   = str(asset_id).strip()
            export_dir = str(export_dir).strip()
            if not asset_id or not export_dir:
                return BridgeExportResult(error="asset_id and export_dir are required")

            os.makedirs(export_dir, exist_ok=True)

            payload = {
                "id":          asset_id,
                "exportPath":  export_dir.replace("\\", "/"),
                "quality":     quality,
                "format":      fmt.lower(),
                "components":  ["mesh", "albedo", "roughness", "normal", "displacement"],
            }

            result = self._post(f"{_BRIDGE_BASE}/api/v1/export", payload)
            if not result:
                return BridgeExportResult(
                    asset_id=asset_id,
                    error="Bridge did not respond — is Quixel Bridge / Fab Bridge open?",
                )

            if not result.get("ok", True) or result.get("error"):
                return BridgeExportResult(
                    asset_id=asset_id,
                    error=str(result.get("error") or result.get("message") or "Bridge export failed"),
                )

            # Parse Bridge response — extract file paths from components
            mesh_path     = self._find_mesh_from_response(result, export_dir)
            texture_paths = self._find_textures_from_response(result, export_dir)

            with self._lock:
                self._export_count += 1

            return BridgeExportResult(
                ok=bool(mesh_path or texture_paths),
                asset_id=asset_id,
                name=str(result.get("name") or ""),
                asset_type=str(result.get("type") or ""),
                mesh_path=mesh_path,
                texture_paths=texture_paths,
                export_dir=export_dir,
                source="bridge",
                error="" if mesh_path else "Bridge exported but no mesh file found",
            )
        except Exception as exc:
            return BridgeExportResult(asset_id=str(asset_id), error=str(exc))

    def export_asset_by_name(
        self,
        query:      str,
        export_dir: str,
        quality:    str = "2K",
        fmt:        str = "fbx",
        asset_type: str = "",
    ) -> BridgeExportResult:
        """
        Search then export the best-matching asset.
        Convenience wrapper for search + export. Never raises.
        """
        try:
            assets = self.search_assets(query, limit=5, asset_type=asset_type)
            if not assets:
                return BridgeExportResult(
                    error=f"No assets found in Bridge for query '{query}'"
                )
            best = assets[0]
            asset_id = str(best.get("id") or best.get("asset_id") or "")
            if not asset_id:
                return BridgeExportResult(error="Bridge returned asset with no ID")
            return self.export_asset(asset_id, export_dir, quality=quality, fmt=fmt)
        except Exception as exc:
            return BridgeExportResult(error=str(exc))

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "export_count":    self._export_count,
                "bridge_running":  self.is_bridge_running(),
                "bridge_port":     _BRIDGE_PORT,
            }

    # ------------------------------------------------------------------
    # HTTP helpers (injectable)
    # ------------------------------------------------------------------

    def _get(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        if self._transport is not None:
            return self._transport.get(url, params or {})
        try:
            import urllib.request, urllib.parse
            full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
            req = urllib.request.Request(full_url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return data if isinstance(data, dict) else {}
        except Exception:
            return None

    def _post(
        self, url: str, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if self._transport is not None:
            return self._transport.post(url, payload)
        try:
            import urllib.request
            body = json.dumps(payload).encode("utf-8")
            req  = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept",       "application/json")
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return data if isinstance(data, dict) else {}
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Response parsing helpers
    # ------------------------------------------------------------------

    _MESH_EXTS = frozenset({".fbx", ".obj", ".usd", ".usda", ".usdc", ".usdz", ".abc"})
    _TEX_EXTS  = frozenset({".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"})

    def _find_mesh_from_response(
        self, result: Dict[str, Any], export_dir: str
    ) -> str:
        """Extract the mesh file path from a Bridge export response."""
        # Bridge may return components list or a direct meshPath field
        mesh = str(result.get("meshPath") or result.get("mesh_path") or "")
        if mesh and os.path.isfile(mesh):
            return mesh

        components = result.get("components") or []
        for comp in components:
            if not isinstance(comp, dict):
                continue
            path = str(comp.get("path") or comp.get("filePath") or "")
            ext  = os.path.splitext(path)[-1].lower()
            if ext in self._MESH_EXTS and os.path.isfile(path):
                return path

        # Walk the export_dir looking for any mesh file
        for root, _, files in os.walk(export_dir):
            for fname in sorted(files):
                if os.path.splitext(fname)[-1].lower() in self._MESH_EXTS:
                    return os.path.join(root, fname)
        return ""

    def _find_textures_from_response(
        self, result: Dict[str, Any], export_dir: str
    ) -> List[str]:
        """Extract texture file paths from a Bridge export response."""
        textures: List[str] = []
        components = result.get("components") or []
        for comp in components:
            if not isinstance(comp, dict):
                continue
            path = str(comp.get("path") or comp.get("filePath") or "")
            if os.path.splitext(path)[-1].lower() in self._TEX_EXTS and os.path.isfile(path):
                textures.append(path)
        if not textures:
            for root, _, files in os.walk(export_dir):
                for fname in sorted(files):
                    if os.path.splitext(fname)[-1].lower() in self._TEX_EXTS:
                        textures.append(os.path.join(root, fname))
        return textures


_INSTANCE: Optional[QuixelBridgeClient] = None
_INSTANCE_LOCK = threading.Lock()


def get_quixel_bridge_client() -> QuixelBridgeClient:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = QuixelBridgeClient()
    return _INSTANCE


def reset_quixel_bridge_client_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
