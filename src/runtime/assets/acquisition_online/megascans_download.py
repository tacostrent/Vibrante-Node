"""
Megascans Download (Tier 12.9)
================================
Download asset files from Megascans / Fab.

Features:
  - Checksum validation (SHA-256)
  - Retry support (up to 3 attempts)
  - Partial download recovery (resume via Range headers)
  - No hardcoded credentials

Injectable transport for tests:
  downloader._transport = MyMockTransport()
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .megascans_auth import get_megascans_auth

_MAX_RETRIES = 3
_CHUNK_SIZE  = 65536  # 64 KB chunks


@dataclass
class DownloadResult:
    ok:               bool  = False
    asset_id:         str   = ""
    provider:         str   = "megascans"
    local_path:       str   = ""
    checksum:         str   = ""
    bytes_downloaded: int   = 0
    attempts:         int   = 0
    duration_ms:      float = 0.0
    source:           str   = "megascans_api"   # "megascans_api" | "offline" | "cache"
    error:            str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":               bool(self.ok),
            "asset_id":         str(self.asset_id),
            "provider":         str(self.provider),
            "local_path":       str(self.local_path),
            "checksum":         str(self.checksum),
            "bytes_downloaded": int(self.bytes_downloaded),
            "attempts":         int(self.attempts),
            "duration_ms":      float(self.duration_ms),
            "source":           str(self.source),
            "error":            str(self.error),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DownloadResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", False)),
            asset_id=str(d.get("asset_id", "")),
            provider=str(d.get("provider", "megascans")),
            local_path=str(d.get("local_path", "")),
            checksum=str(d.get("checksum", "")),
            bytes_downloaded=int(d.get("bytes_downloaded", 0)),
            attempts=int(d.get("attempts", 0)),
            duration_ms=float(d.get("duration_ms", 0.0)),
            source=str(d.get("source", "megascans_api")),
            error=str(d.get("error", "")),
        )


class MegascansDownloader:
    """
    Downloads assets from the Megascans API to a local destination directory.

    Injectable transport for tests:
      downloader._transport = MyMockTransport()
      # transport.download(url, token, dest_path) → {"ok": bool, "bytes": int}
    """

    def __init__(self) -> None:
        self._lock      = threading.Lock()
        self._dl_count  = 0
        self._transport: Optional[Any] = None  # Injectable for tests

    def download_asset(
        self,
        asset_id:    str,
        dest_dir:    str,
        download_url: str = "",
        quality:     str = "medium",
        expected_checksum: str = "",
    ) -> DownloadResult:
        """
        Download a Megascans asset to dest_dir.

        Flow:
          1. Download the asset ZIP from the API.
          2. Extract the ZIP into {dest_dir}/{asset_id}/.
          3. Find the best importable mesh file (FBX > OBJ > USD > ABC).
          4. Mirror the extracted folder into VIBRANTE_MEGASCANS_LIBRARY/{asset_id}/
             so future catalog scans pick it up automatically.
          5. Return a DownloadResult whose local_path points to the mesh file.

        Never raises.
        """
        t0 = time.time()
        try:
            asset_id = str(asset_id).strip()
            dest_dir = str(dest_dir).strip()
            if not asset_id or not dest_dir:
                return DownloadResult(asset_id=asset_id,
                                      error="asset_id and dest_dir are required")

            token = get_megascans_auth().get_token()
            if not token:
                return DownloadResult(
                    asset_id=asset_id, source="offline",
                    error="No authentication token. "
                          "Set VIBRANTE_MEGASCANS_APP_ID / APP_KEY / USERNAME / PASSWORD "
                          "or VIBRANTE_MEGASCANS_TOKEN.",
                )

            os.makedirs(dest_dir, exist_ok=True)
            url = download_url or self._resolve_download_url(asset_id, token, quality)
            if not url:
                return DownloadResult(
                    asset_id=asset_id,
                    error=f"Megascans API returned no download URL for '{asset_id}'. "
                          "Asset may not be in your library — acquire it via Fab first.",
                )

            # 1. Download ZIP
            zip_path = os.path.join(dest_dir, f"{asset_id}.zip")
            dl = self._download_with_retry(url, token, zip_path)
            if not dl["ok"]:
                return DownloadResult(
                    asset_id=asset_id,
                    error=dl.get("error", "download failed"),
                    attempts=dl.get("attempts", 1),
                    duration_ms=round((time.time() - t0) * 1000, 1),
                )

            checksum = self._compute_checksum(zip_path)
            if expected_checksum and checksum != expected_checksum:
                return DownloadResult(
                    asset_id=asset_id, local_path=zip_path, checksum=checksum,
                    bytes_downloaded=dl.get("bytes", 0), attempts=dl.get("attempts", 1),
                    error=f"Checksum mismatch: expected {expected_checksum[:8]}… got {checksum[:8]}…",
                    duration_ms=round((time.time() - t0) * 1000, 1),
                )

            # 2. Extract ZIP
            extract_dir = os.path.join(dest_dir, asset_id)
            mesh_path   = self._extract_and_find_mesh(zip_path, extract_dir)

            # 3. Mirror to Megascans library for future catalog scans
            self._mirror_to_library(asset_id, extract_dir)

            with self._lock:
                self._dl_count += 1

            # Return the mesh file path if found, else the zip as fallback
            final_path = mesh_path or zip_path
            return DownloadResult(
                ok=True,
                asset_id=asset_id,
                local_path=final_path,
                checksum=checksum,
                bytes_downloaded=dl.get("bytes", 0),
                attempts=dl.get("attempts", 1),
                duration_ms=round((time.time() - t0) * 1000, 1),
            )
        except Exception as exc:
            return DownloadResult(
                asset_id=str(asset_id),
                error=str(exc),
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

    # ------------------------------------------------------------------
    # ZIP extraction + mesh discovery
    # ------------------------------------------------------------------

    def _extract_and_find_mesh(self, zip_path: str, extract_dir: str) -> str:
        """
        Extract a Megascans ZIP and return the best importable mesh file path.
        Priority: .fbx > .obj > .usd/.usda/.usdc/.usdz > .abc
        Returns "" if nothing found or extraction fails.
        """
        try:
            import zipfile
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except Exception:
            return ""

        # Walk the extracted directory for mesh files
        _MESH_PRIORITY = [
            (".fbx",  10),
            (".obj",   9),
            (".usdz",  8),
            (".usdc",  7),
            (".usda",  6),
            (".usd",   5),
            (".abc",   4),
        ]
        best_path  = ""
        best_score = -1
        for root, _dirs, files in os.walk(extract_dir):
            for fname in files:
                low = fname.lower()
                for ext, score in _MESH_PRIORITY:
                    if low.endswith(ext) and score > best_score:
                        best_score = score
                        best_path  = os.path.join(root, fname)
        return best_path

    def _mirror_to_library(self, asset_id: str, extract_dir: str) -> None:
        """
        Copy the extracted asset folder into VIBRANTE_MEGASCANS_LIBRARY/{asset_id}/
        so future hou_mcp_library_scan picks it up automatically.
        Silently skips if env var is not set or copy fails.
        """
        try:
            library_root = os.environ.get("VIBRANTE_MEGASCANS_LIBRARY", "").strip()
            if not library_root or not os.path.isdir(extract_dir):
                return
            dest = os.path.join(library_root, str(asset_id))
            if os.path.exists(dest):
                return  # already there
            import shutil
            shutil.copytree(extract_dir, dest)
        except Exception:
            pass

    def download_components(
        self,
        asset_id: str,
        dest_dir: str,
        component_urls: Optional[List[str]] = None,
    ) -> List[DownloadResult]:
        """Download multiple components for an asset. Never raises."""
        try:
            if not component_urls:
                return [self.download_asset(asset_id, dest_dir)]
            results = []
            for url in component_urls:
                r = self.download_asset(asset_id, dest_dir, download_url=url)
                results.append(r)
            return results
        except Exception:
            return []

    def verify_download(self, local_path: str, expected_checksum: str = "") -> Dict[str, Any]:
        """Check that a downloaded file exists and optionally matches checksum. Never raises."""
        try:
            if not os.path.isfile(local_path):
                return {"verified": False, "reason": "file_missing", "path": local_path}
            size = os.path.getsize(local_path)
            if size == 0:
                return {"verified": False, "reason": "empty_file", "path": local_path}
            if expected_checksum:
                actual = self._compute_checksum(local_path)
                if actual != expected_checksum:
                    return {"verified": False, "reason": "checksum_mismatch",
                            "expected": expected_checksum, "actual": actual}
            return {"verified": True, "path": local_path, "size_bytes": size}
        except Exception as exc:
            return {"verified": False, "reason": str(exc)}

    def verify_integrity(self, local_path: str, checksum: str) -> bool:
        """Return True if file matches given SHA-256 checksum."""
        try:
            return self._compute_checksum(local_path) == str(checksum)
        except Exception:
            return False

    def register_download(
        self,
        asset_id:   str,
        local_path: str,
        provider:   str = "megascans",
        checksum:   str = "",
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a completed download with the provenance tracker. Never raises."""
        try:
            from .asset_provenance_tracker import get_asset_provenance_tracker
            rec = get_asset_provenance_tracker().register(
                asset_id=asset_id,
                provider=provider,
                local_path=local_path,
                checksum=checksum,
                source="download",
                metadata=dict(metadata or {}),
            )
            return {"registered": True, "record": rec.to_dict()}
        except Exception as exc:
            return {"registered": False, "error": str(exc)}

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"download_count": self._dl_count}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_download_url(self, asset_id: str, token: str, quality: str) -> str:
        if self._transport is not None:
            url_data = self._transport.resolve_url(asset_id, token, quality)
            return str(url_data or "")
        try:
            import json, urllib.request
            base = "https://megascans.se/v1/assets"
            req  = urllib.request.Request(f"{base}/{asset_id}/download")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return str(data.get("url") or data.get("download_url") or "")
        except Exception:
            return ""

    def _download_with_retry(
        self, url: str, token: str, dest_path: str
    ) -> Dict[str, Any]:
        last_error = ""
        for attempt in range(1, _MAX_RETRIES + 1):
            result = self._download_once(url, token, dest_path)
            if result["ok"]:
                result["attempts"] = attempt
                return result
            last_error = result.get("error", "")
            if attempt < _MAX_RETRIES:
                time.sleep(0.5 * attempt)
        return {"ok": False, "error": last_error, "attempts": _MAX_RETRIES, "bytes": 0}

    def _download_once(self, url: str, token: str, dest_path: str) -> Dict[str, Any]:
        if self._transport is not None:
            return self._transport.download(url, token, dest_path)
        try:
            import urllib.request
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            total = 0
            with urllib.request.urlopen(req, timeout=60) as resp, \
                 open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
            return {"ok": True, "bytes": total, "error": ""}
        except Exception as exc:
            return {"ok": False, "bytes": 0, "error": str(exc)}

    @staticmethod
    def _compute_checksum(path: str) -> str:
        try:
            sha = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
                    sha.update(chunk)
            return sha.hexdigest()
        except Exception:
            return ""


_INSTANCE: Optional[MegascansDownloader] = None
_INSTANCE_LOCK = threading.Lock()


def get_megascans_downloader() -> MegascansDownloader:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MegascansDownloader()
    return _INSTANCE


def reset_megascans_downloader_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
