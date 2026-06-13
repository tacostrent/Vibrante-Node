"""
Asset Serializer (Tier 8 — Asset Intelligence Runtime)
=======================================================
Deterministic JSON serialization for Tier 8 data models.

Uses the existing storage.serialization infrastructure for
sorted-key JSON and schema migration compatibility.

Public API:
    AssetSerializer
    get_asset_serializer()
    reset_asset_serializer_for_tests()
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.runtime.assets.schema import (
    AssetDescriptor,
    AssetQueryResult,
    AssetRecommendation,
)

try:
    from src.runtime.storage.serialization import serialize_record, deserialize_record
    _HAS_STORAGE = True
except ImportError:
    _HAS_STORAGE = False

    def serialize_record(record: Dict[str, Any]) -> str:  # type: ignore[misc]
        return json.dumps(record, sort_keys=True, default=str)

    def deserialize_record(s: str) -> Dict[str, Any]:  # type: ignore[misc]
        try:
            return json.loads(s)
        except Exception:
            return {}


class AssetSerializer:
    """Deterministic JSON serializer for Tier 8 models."""

    # ------------------------------------------------------------------
    # AssetDescriptor
    # ------------------------------------------------------------------

    def descriptor_to_json(self, asset: AssetDescriptor, compact: bool = False) -> str:
        data = asset.to_dict()
        data["record_type"] = "asset_descriptor"
        if compact:
            return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
        return serialize_record(data)

    def descriptor_from_json(self, s: str, lenient: bool = False) -> Optional[AssetDescriptor]:
        try:
            data = deserialize_record(s)
            data.pop("record_type", None)
            return AssetDescriptor.from_dict(data)
        except Exception:
            if lenient:
                return None
            raise

    def descriptor_list_to_json(self, assets: List[AssetDescriptor]) -> str:
        return json.dumps(
            [a.to_dict() for a in assets],
            sort_keys=True, default=str
        )

    def descriptor_list_from_json(self, s: str) -> List[AssetDescriptor]:
        try:
            items = json.loads(s)
            if not isinstance(items, list):
                return []
            return [AssetDescriptor.from_dict(d) for d in items if isinstance(d, dict)]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # AssetQueryResult
    # ------------------------------------------------------------------

    def query_result_to_json(self, result: AssetQueryResult) -> str:
        data = result.to_dict()
        data["record_type"] = "asset_query_result"
        return serialize_record(data)

    def query_result_from_json(self, s: str, lenient: bool = False) -> Optional[AssetQueryResult]:
        try:
            data = deserialize_record(s)
            data.pop("record_type", None)
            return AssetQueryResult.from_dict(data)
        except Exception:
            if lenient:
                return None
            raise

    # ------------------------------------------------------------------
    # AssetRecommendation
    # ------------------------------------------------------------------

    def recommendation_to_json(self, rec: AssetRecommendation) -> str:
        data = rec.to_dict()
        data["record_type"] = "asset_recommendation"
        return serialize_record(data)

    def recommendation_from_json(self, s: str, lenient: bool = False) -> Optional[AssetRecommendation]:
        try:
            data = deserialize_record(s)
            data.pop("record_type", None)
            return AssetRecommendation.from_dict(data)
        except Exception:
            if lenient:
                return None
            raise

    def recommendation_list_to_json(self, recs: List[AssetRecommendation]) -> str:
        return json.dumps(
            [r.to_dict() for r in recs],
            sort_keys=True, default=str
        )

    def recommendation_list_from_json(self, s: str) -> List[AssetRecommendation]:
        try:
            items = json.loads(s)
            if not isinstance(items, list):
                return []
            return [AssetRecommendation.from_dict(d) for d in items if isinstance(d, dict)]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def save(self, obj: Any, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(obj, AssetDescriptor):
            text = self.descriptor_to_json(obj)
        elif isinstance(obj, AssetQueryResult):
            text = self.query_result_to_json(obj)
        elif isinstance(obj, AssetRecommendation):
            text = self.recommendation_to_json(obj)
        elif isinstance(obj, list):
            text = self.descriptor_list_to_json(obj)
        else:
            text = json.dumps(obj, sort_keys=True, default=str)
        p.write_text(text, encoding="utf-8")

    def load_descriptor(self, path: Union[str, Path], lenient: bool = False) -> Optional[AssetDescriptor]:
        try:
            text = Path(path).read_text(encoding="utf-8")
            return self.descriptor_from_json(text, lenient=lenient)
        except FileNotFoundError:
            if lenient:
                return None
            raise


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetSerializer] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_serializer() -> AssetSerializer:
    """Return the module-level singleton AssetSerializer."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetSerializer()
    return _INSTANCE


def reset_asset_serializer_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
