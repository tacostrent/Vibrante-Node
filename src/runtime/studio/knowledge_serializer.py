"""Studio knowledge serializer (Tier 11 — §31).

Save/load/export/import studio knowledge to/from deterministic JSON files.
All output uses sorted keys and embeds a schema_version field.
"""

import json
import os
import threading
import time
from typing import Any, Dict, Optional

_module_lock = threading.Lock()
_instance: Optional["KnowledgeSerializer"] = None

KNOWLEDGE_SCHEMA_VERSION = "1.0.0"


def get_knowledge_serializer() -> "KnowledgeSerializer":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = KnowledgeSerializer()
    return _instance


def reset_knowledge_serializer_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class KnowledgeSerializer:
    """Deterministic JSON serializer for studio knowledge."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._write_count = 0

    # ------------------------------------------------------------------
    # Core JSON API
    # ------------------------------------------------------------------

    def to_json(self, data: Any, indent: int = 2) -> str:
        """Serialize data to a sorted-key JSON string with schema version."""
        payload = {
            "_schema_version": KNOWLEDGE_SCHEMA_VERSION,
            "data": data,
        }
        return json.dumps(payload, sort_keys=True, indent=indent, default=str)

    def from_json(self, s: str, lenient: bool = True) -> Optional[Any]:
        """Deserialize from a JSON string.  Returns None on error when lenient=True."""
        try:
            raw = json.loads(s)
            if isinstance(raw, dict) and "data" in raw:
                return raw["data"]
            return raw
        except json.JSONDecodeError:
            if lenient:
                return None
            raise

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def save(self, data: Any, path: str) -> bool:
        """Write data to a JSON file.  Returns True on success."""
        with self._lock:
            try:
                payload = {
                    "_schema_version": KNOWLEDGE_SCHEMA_VERSION,
                    "saved_at": time.time(),
                    "data": data,
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, sort_keys=True, indent=2, default=str)
                self._write_count += 1
                return True
            except (OSError, IOError, TypeError):
                return False

    def load(self, path: str, lenient: bool = True) -> Optional[Any]:
        """Load data from a JSON file."""
        if not os.path.exists(path):
            if lenient:
                return None
            raise FileNotFoundError(f"Knowledge file not found: {path!r}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                if lenient:
                    return None
                raise ValueError("Knowledge file root must be a JSON object")
            ver = raw.get("_schema_version", "")
            if ver and ver > KNOWLEDGE_SCHEMA_VERSION and not lenient:
                raise ValueError(
                    f"Schema version {ver!r} exceeds current {KNOWLEDGE_SCHEMA_VERSION!r}"
                )
            return raw.get("data", raw)
        except (json.JSONDecodeError, OSError, IOError) as exc:
            if lenient:
                return None
            raise

    # ------------------------------------------------------------------
    # Export / import
    # ------------------------------------------------------------------

    def export(self, path: str = "") -> Dict[str, Any]:
        """Snapshot all live studio knowledge modules into a portable dict."""
        result: Dict[str, Any] = {
            "_schema_version": KNOWLEDGE_SCHEMA_VERSION,
            "exported_at": time.time(),
            "modules": {},
        }
        for key, getter in [
            ("studio_knowledge", "src.runtime.studio.studio_knowledge.get_studio_knowledge_db"),
            ("studio_standards", "src.runtime.studio.studio_standards.get_studio_standards"),
            ("studio_metrics", "src.runtime.studio.studio_metrics.get_studio_metrics"),
            ("project_memory", "src.runtime.studio.project_memory.get_project_memory"),
        ]:
            try:
                module_path, func_name = getter.rsplit(".", 1)
                import importlib
                mod = importlib.import_module(module_path)
                obj = getattr(mod, func_name)()
                if hasattr(obj, "get_studio_statistics"):
                    result["modules"][key] = obj.get_studio_statistics()
                elif hasattr(obj, "get_all_standards"):
                    result["modules"][key] = obj.get_all_standards()
                elif hasattr(obj, "generate_metrics_report"):
                    result["modules"][key] = obj.generate_metrics_report()
                elif hasattr(obj, "get_project_statistics"):
                    result["modules"][key] = obj.get_project_statistics()
                else:
                    result["modules"][key] = obj.stats()
            except Exception:
                pass

        if path:
            self.save(result, path)
        return result

    def import_(self, path: str) -> Dict[str, Any]:
        """Load exported knowledge from a file.  Returns the data dict or {}."""
        data = self.load(path, lenient=False)
        return data if isinstance(data, dict) else {}

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"write_count": self._write_count}
