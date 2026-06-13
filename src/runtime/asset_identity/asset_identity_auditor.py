"""
asset_identity_auditor.py — Tier 14.4.5 Asset Identity Audit
=============================================================
Reads all Vibrante metadata from realized Houdini nodes and verifies that
every asset has a persistent, non-opaque, semantically consistent identity.

Architecture — bridge isolation (same pattern as Tier 14.4.4):
    AssetIdentityAuditor    pure planning (no bridge calls), fully testable.
    HoudiniIdentityFetcher  the ONLY component that calls get_bridge();
                            used by the Houdini node to fetch live metadata.

Per-asset identity is resolved from these Houdini user-data keys:

  Identity keys (Tier 14.4.5, new):
    vibrante_asset_id         catalog asset_id
    vibrante_asset_name       human-readable display name
    vibrante_asset_category   category (furniture / prop / structural / …)

  Relationship keys (Tier 14.4.4, existing):
    vibrante_asset_role           role in the layout
    vibrante_placement_engine     engine that placed this asset
    vibrante_relationship_type    relationship to parent
    vibrante_expected_parent      planned parent_id
    vibrante_actual_parent        resolved parent_id
    vibrante_support_surface      host surface type
    vibrante_anchor_id            anchor asset id
    vibrante_anchor_type          anchor asset type
    vibrante_layout_cluster_id    cluster id

Identity status values:
    RESOLVED               — all checks pass; full semantic identity present
    OPAQUE_NAME            — asset_name is an opaque Megascans-style ID
    OPAQUE_ID              — asset_id is opaque
    MISSING_ROLE           — vibrante_asset_role is empty
    MISSING_CATEGORY       — vibrante_asset_category is empty
    MISSING_NAME           — vibrante_asset_name is empty
    ROLE_ENGINE_MISMATCH   — role is incompatible with placement_engine
    ROLE_CATEGORY_MISMATCH — role is incompatible with category (geometry proxy)
    UNCLASSIFIED           — multiple missing identity fields; cannot classify

PASS criteria:
    identity_coverage == 1.0    (all 3 identity keys present on every node)
    unclassified_assets == 0    (no UNCLASSIFIED status)
    opaque_assets == 0          (no opaque names or IDs)

Public API:
    IDENTITY_AUDIT_PASS
    IDENTITY_AUDIT_FAIL
    IDENTITY_RESOLVED  IDENTITY_OPAQUE_NAME  IDENTITY_OPAQUE_ID
    IDENTITY_MISSING_ROLE  IDENTITY_MISSING_CATEGORY  IDENTITY_MISSING_NAME
    IDENTITY_ROLE_ENGINE_MISMATCH  IDENTITY_ROLE_CATEGORY_MISMATCH
    IDENTITY_UNCLASSIFIED
    ALL_IDENTITY_KEYS
    AssetIdentityRecord
    IdentityAuditResult
    AssetIdentityAuditor
    HoudiniIdentityFetcher
    get_asset_identity_auditor()
    reset_asset_identity_auditor_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.layout_realization.identity_metadata_writer import IDENTITY_KEYS
from src.runtime.layout_realization.relationship_metadata_writer import METADATA_KEYS
from src.runtime.asset_identity.opaque_id_detector import get_opaque_id_detector
from src.runtime.asset_identity.role_engine_validator import get_role_engine_validator
from src.runtime.asset_identity.role_geometry_validator import get_role_geometry_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDENTITY_AUDIT_PASS = "PASS"
IDENTITY_AUDIT_FAIL = "FAIL"

IDENTITY_RESOLVED              = "RESOLVED"
IDENTITY_OPAQUE_NAME           = "OPAQUE_NAME"
IDENTITY_OPAQUE_ID             = "OPAQUE_ID"
IDENTITY_MISSING_ROLE          = "MISSING_ROLE"
IDENTITY_MISSING_CATEGORY      = "MISSING_CATEGORY"
IDENTITY_MISSING_NAME          = "MISSING_NAME"
IDENTITY_ROLE_ENGINE_MISMATCH  = "ROLE_ENGINE_MISMATCH"
IDENTITY_ROLE_CATEGORY_MISMATCH = "ROLE_CATEGORY_MISMATCH"
IDENTITY_UNCLASSIFIED          = "UNCLASSIFIED"

# All keys this auditor reads from Houdini user-data
ALL_IDENTITY_KEYS: List[str] = IDENTITY_KEYS + METADATA_KEYS   # 3 + 9 = 12

# Number of identity keys that must be present for "complete" identity
_IDENTITY_KEY_COUNT = len(IDENTITY_KEYS)  # 3


# ---------------------------------------------------------------------------
# Per-asset record
# ---------------------------------------------------------------------------

@dataclass
class AssetIdentityRecord:
    """
    Full identity audit row for one realized Houdini node.
    All string fields are read from Houdini user-data.
    """

    # Keys
    asset_path:       str = ""   # Houdini node path
    node_name:        str = ""   # hou.Node.name()

    # Identity fields (new Tier 14.4.5 keys)
    asset_id:         str = ""   # vibrante_asset_id
    asset_name:       str = ""   # vibrante_asset_name
    asset_category:   str = ""   # vibrante_asset_category

    # Role / engine (existing Tier 14.4.4 keys)
    asset_role:       str = ""   # vibrante_asset_role
    placement_engine: str = ""   # vibrante_placement_engine
    relationship_type: str = ""  # vibrante_relationship_type

    # Audit flags (derived)
    identity_status:         str  = IDENTITY_UNCLASSIFIED
    identity_keys_present:   int  = 0   # count of the 3 identity keys that have values
    is_opaque_name:          bool = False
    is_opaque_id:            bool = False
    role_engine_ok:          bool = True
    role_category_ok:        bool = True
    findings:                List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_path":            self.asset_path,
            "asset_name":            self.asset_name,
            "asset_role":            self.asset_role,
            "asset_category":        self.asset_category,
            "placement_engine":      self.placement_engine,
            "identity_status":       self.identity_status,
            "identity_keys_present": self.identity_keys_present,
            "is_opaque_name":        self.is_opaque_name,
            "is_opaque_id":          self.is_opaque_id,
            "role_engine_ok":        self.role_engine_ok,
            "role_category_ok":      self.role_category_ok,
            "findings":              list(self.findings),
        }


# ---------------------------------------------------------------------------
# Audit result
# ---------------------------------------------------------------------------

@dataclass
class IdentityAuditResult:
    """Full output of AssetIdentityAuditor.audit()."""

    records:             List[AssetIdentityRecord] = field(default_factory=list)

    total_assets:        int   = 0
    resolved_assets:     int   = 0   # RESOLVED status
    opaque_assets:       int   = 0   # OPAQUE_NAME or OPAQUE_ID
    unclassified_assets: int   = 0   # UNCLASSIFIED status
    missing_identity:    int   = 0   # assets with < 3 identity keys present

    identity_coverage:   float = 0.0  # resolved_assets / total_assets

    status:              str   = IDENTITY_AUDIT_FAIL
    production_ready:    bool  = False

    audit_table:         str   = ""

    ok:     bool       = True
    errors: List[str]  = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "records":             [r.to_dict() for r in self.records],
            "total_assets":        self.total_assets,
            "resolved_assets":     self.resolved_assets,
            "opaque_assets":       self.opaque_assets,
            "unclassified_assets": self.unclassified_assets,
            "missing_identity":    self.missing_identity,
            "identity_coverage":   round(self.identity_coverage, 4),
            "status":              self.status,
            "production_ready":    self.production_ready,
            "audit_table":         self.audit_table,
            "ok":                  self.ok,
            "errors":              list(self.errors),
        }


# ---------------------------------------------------------------------------
# Auditor (pure planning — no bridge calls)
# ---------------------------------------------------------------------------

class AssetIdentityAuditor:
    """
    Validates semantic identity completeness for every realized Houdini asset.

    Usage (tests — inject node_metadata directly):
        auditor = get_asset_identity_auditor()
        result  = auditor.audit(
            node_metadata = {
                "chair_01": {
                    "vibrante_asset_id":       "chair_01",
                    "vibrante_asset_name":     "Wooden Saloon Chair",
                    "vibrante_asset_category": "furniture",
                    "vibrante_asset_role":     "cluster_member",
                    "vibrante_placement_engine": "FurnitureClusterBuilder",
                    ...
                },
            },
            node_names = {"chair_01": "chair_01"},
            node_paths = {"chair_01": "/obj/scene/chair_01"},
        )

    Usage (production — fetch from Houdini via HoudiniIdentityFetcher):
        node_metadata, node_names, node_paths = HoudiniIdentityFetcher().fetch_identity(node_path_map)
        result = auditor.audit(node_metadata, node_names, node_paths)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def audit(
        self,
        node_metadata: Dict[str, Dict[str, str]],
        node_names:    Optional[Dict[str, str]] = None,
        node_paths:    Optional[Dict[str, str]] = None,
    ) -> IdentityAuditResult:
        """
        Audit identity completeness for every asset in node_metadata.

        Args:
            node_metadata: {asset_id: {vibrante_key: value, ...}}
            node_names:    {asset_id: houdini_node_name}
            node_paths:    {asset_id: node_path}

        Returns: IdentityAuditResult. Never raises.
        """
        try:
            return self._audit(
                node_metadata,
                node_names or {},
                node_paths or {},
            )
        except Exception as exc:
            return IdentityAuditResult(
                ok=False,
                errors=[f"AssetIdentityAuditor.audit failed: {exc}"],
                status=IDENTITY_AUDIT_FAIL,
            )

    def _audit(
        self,
        node_metadata: Dict[str, Dict[str, str]],
        node_names:    Dict[str, str],
        node_paths:    Dict[str, str],
    ) -> IdentityAuditResult:

        opaque_det   = get_opaque_id_detector()
        role_eng_val = get_role_engine_validator()
        role_geo_val = get_role_geometry_validator()

        records: List[AssetIdentityRecord] = []

        for asset_id, meta in node_metadata.items():
            node_name = node_names.get(asset_id, asset_id)
            node_path = node_paths.get(asset_id, "")
            rec = self._build_record(
                asset_id, meta, node_name, node_path,
                opaque_det, role_eng_val, role_geo_val,
            )
            records.append(rec)

        total        = len(records)
        n_resolved   = sum(1 for r in records if r.identity_status == IDENTITY_RESOLVED)
        n_opaque     = sum(1 for r in records if r.is_opaque_name or r.is_opaque_id)
        n_unclass    = sum(1 for r in records if r.identity_status == IDENTITY_UNCLASSIFIED)
        n_missing    = sum(1 for r in records if r.identity_keys_present < _IDENTITY_KEY_COUNT)

        # coverage: fraction of assets that are fully resolved
        coverage = (n_resolved / total) if total > 0 else 1.0  # vacuous pass for empty set

        passed = (coverage >= 1.0 and n_opaque == 0 and n_unclass == 0)

        table = _format_table(records, coverage, n_opaque, n_unclass)

        return IdentityAuditResult(
            records             = records,
            total_assets        = total,
            resolved_assets     = n_resolved,
            opaque_assets       = n_opaque,
            unclassified_assets = n_unclass,
            missing_identity    = n_missing,
            identity_coverage   = round(coverage, 4),
            status              = IDENTITY_AUDIT_PASS if passed else IDENTITY_AUDIT_FAIL,
            production_ready    = passed,
            audit_table         = table,
            ok                  = passed,
        )

    def _build_record(
        self,
        asset_id:    str,
        meta:        Dict[str, str],
        node_name:   str,
        node_path:   str,
        opaque_det,
        role_eng_val,
        role_geo_val,
    ) -> AssetIdentityRecord:

        # Read identity fields
        v_asset_id   = meta.get("vibrante_asset_id",       "").strip()
        v_name       = meta.get("vibrante_asset_name",     "").strip()
        v_category   = meta.get("vibrante_asset_category", "").strip()
        v_role       = meta.get("vibrante_asset_role",     "").strip()
        v_engine     = meta.get("vibrante_placement_engine", "").strip()
        v_rel        = meta.get("vibrante_relationship_type", "").strip()

        # Use node_name as fallback display name when vibrante_asset_name is empty
        display_name = v_name if v_name else node_name

        # Count how many identity keys are populated
        keys_present = sum(1 for v in (v_asset_id, v_name, v_category) if v)

        # Opaque checks
        opaque_name = opaque_det.is_opaque(v_name) if v_name else False
        opaque_id   = opaque_det.is_opaque(v_asset_id) if v_asset_id else False
        # Also check node_name when vibrante_asset_name is absent
        if not v_name and node_name:
            opaque_name = opaque_det.is_opaque(node_name)

        # Role/engine validation
        role_engine_ok = role_eng_val.is_compatible(v_role, v_engine)

        # Role/category (geometry proxy) validation
        role_category_ok = role_geo_val.is_compatible(v_role, v_category)

        # Determine identity_status and findings
        findings: List[str] = []
        status: str

        missing_count = sum([not v_role, not v_category, not v_name and not node_name])
        if missing_count >= 2:
            status = IDENTITY_UNCLASSIFIED
            if not v_role:
                findings.append("missing vibrante_asset_role")
            if not v_category:
                findings.append("missing vibrante_asset_category")
            if not v_name:
                findings.append("missing vibrante_asset_name")
        elif opaque_name:
            status = IDENTITY_OPAQUE_NAME
            findings.append(
                f"asset_name '{display_name}' matches opaque Megascans ID pattern"
            )
        elif opaque_id:
            status = IDENTITY_OPAQUE_ID
            findings.append(
                f"asset_id '{v_asset_id}' matches opaque Megascans ID pattern"
            )
        elif not v_role:
            status = IDENTITY_MISSING_ROLE
            findings.append("vibrante_asset_role is empty")
        elif not v_category:
            status = IDENTITY_MISSING_CATEGORY
            findings.append("vibrante_asset_category is empty")
        elif not v_name:
            status = IDENTITY_MISSING_NAME
            findings.append("vibrante_asset_name is empty")
        elif not role_engine_ok:
            status = IDENTITY_ROLE_ENGINE_MISMATCH
            findings.append(role_eng_val.describe_mismatch(v_role, v_engine))
        elif not role_category_ok:
            status = IDENTITY_ROLE_CATEGORY_MISMATCH
            findings.append(role_geo_val.describe_mismatch(v_role, v_category))
        else:
            status = IDENTITY_RESOLVED

        return AssetIdentityRecord(
            asset_path         = node_path,
            node_name          = node_name,
            asset_id           = v_asset_id,
            asset_name         = display_name,
            asset_category     = v_category,
            asset_role         = v_role,
            placement_engine   = v_engine,
            relationship_type  = v_rel,
            identity_status    = status,
            identity_keys_present = keys_present,
            is_opaque_name     = opaque_name,
            is_opaque_id       = opaque_id,
            role_engine_ok     = role_engine_ok,
            role_category_ok   = role_category_ok,
            findings           = findings,
        )


# ---------------------------------------------------------------------------
# Houdini bridge adapter (the ONLY component that calls get_bridge)
# ---------------------------------------------------------------------------

class HoudiniIdentityFetcher:
    """
    Reads all vibrante_ user-data keys (identity + relationship) from live
    Houdini nodes via bridge.run_code().

    Returns the same triple (node_metadata, node_names, node_paths) as
    HoudiniMetadataFetcher, extended with the 3 identity keys.
    """

    def fetch_identity(
        self,
        node_path_map: Dict[str, str],
    ) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
        """
        Returns:
            node_metadata — {asset_id: {all_vibrante_key: value, ...}}
            node_names    — {asset_id: hou.Node.name()}
            node_paths    — {asset_id: node_path}

        Reads all 12 keys in ALL_IDENTITY_KEYS.
        Never raises; missing / errored nodes produce empty metadata dicts.
        """
        from src.utils.hou_bridge import get_bridge
        bridge = get_bridge()

        node_metadata: Dict[str, Dict[str, str]] = {}
        node_names:    Dict[str, str]             = {}
        node_paths:    Dict[str, str]             = {}

        keys_repr = repr(ALL_IDENTITY_KEYS)

        for asset_id, node_path in node_path_map.items():
            if not node_path:
                continue
            try:
                path_repr = repr(node_path)
                code = (
                    "_n = hou.node(" + path_repr + ")\n"
                    "if _n:\n"
                    "    result = {\n"
                    "        'node_name': _n.name(),\n"
                    "        'metadata':  {k: (_n.userData(k) or '') "
                    "for k in " + keys_repr + "},\n"
                    "    }\n"
                    "else:\n"
                    "    result = None\n"
                )
                run_result = bridge.run_code(code)
                data = run_result.get("result")
                if isinstance(data, dict):
                    node_metadata[asset_id] = data.get("metadata", {})
                    node_names[asset_id]    = data.get("node_name", asset_id)
                    node_paths[asset_id]    = node_path
                else:
                    node_metadata[asset_id] = {}
                    node_names[asset_id]    = asset_id
                    node_paths[asset_id]    = node_path
            except Exception:
                node_metadata[asset_id] = {}
                node_names[asset_id]    = asset_id
                node_paths[asset_id]    = node_path

        return node_metadata, node_names, node_paths


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_table(
    records:   List[AssetIdentityRecord],
    coverage:  float,
    n_opaque:  int,
    n_unclass: int,
) -> str:
    w1, w2, w3, w4, w5 = 24, 18, 16, 16, 12
    sep = "-" * (w1 + w2 + w3 + w4 + w5 + 15)
    header = (
        f"{'asset_name':<{w1}} {'role':<{w2}} {'category':<{w3}} "
        f"{'engine':<{w4}} {'status':<{w5}}"
    )
    lines = ["", "ASSET IDENTITY AUDIT", sep, header, sep]

    for r in records:
        engine_short = r.placement_engine.replace("Engine", "").replace("Builder", "")
        lines.append(
            f"{r.asset_name[:w1-1]:<{w1}} "
            f"{r.asset_role[:w2-1]:<{w2}} "
            f"{r.asset_category[:w3-1]:<{w3}} "
            f"{engine_short[:w4-1]:<{w4}} "
            f"{r.identity_status:<{w5}}"
        )

    lines.append(sep)
    total   = len(records)
    n_res   = sum(1 for r in records if r.identity_status == IDENTITY_RESOLVED)
    passed  = coverage >= 1.0 and n_opaque == 0 and n_unclass == 0
    lines.append(
        f"Coverage: {coverage:.1%} ({n_res}/{total})"
        f"  Opaque: {n_opaque}"
        f"  Unclassified: {n_unclass}"
        f"  Status: {'PASS' if passed else 'FAIL'}"
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[AssetIdentityAuditor] = None
_lock = threading.Lock()


def get_asset_identity_auditor() -> AssetIdentityAuditor:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AssetIdentityAuditor()
    return _instance


def reset_asset_identity_auditor_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
