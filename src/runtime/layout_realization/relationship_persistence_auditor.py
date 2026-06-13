"""
relationship_persistence_auditor.py — §47 Tier 14.4.4 Relationship Metadata Persistence
==========================================================================================
Reads relationship metadata from realized Houdini nodes and produces a
per-asset persistence audit report.

Architecture — bridge isolation (same pattern as Tier 14.4.3 auditor):
  RelationshipPersistenceAuditor  pure planning (no bridge calls), fully testable.
  HoudiniMetadataFetcher          the ONLY component that calls get_bridge();
                                  used by the Houdini node to fill node_metadata.

PASS criteria (hard rules):
  metadata_coverage == 1.0     every node has all 9 required keys
  missing_metadata  == 0       zero assets are incomplete

Output per asset (read from Houdini nodes, not planner memory):
  asset_name         — Houdini node name
  role               — vibrante_asset_role
  relationship_type  — vibrante_relationship_type
  expected_parent    — vibrante_expected_parent
  actual_parent      — vibrante_actual_parent
  support_surface    — vibrante_support_surface
  placement_engine   — vibrante_placement_engine

Public API:
  PERSISTENCE_AUDIT_PASS
  PERSISTENCE_AUDIT_FAIL
  REQUIRED_METADATA_KEYS
  AssetMetadataRecord
  RelationshipPersistenceAuditResult
  RelationshipPersistenceAuditor
  HoudiniMetadataFetcher
  get_relationship_persistence_auditor()
  reset_relationship_persistence_auditor_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.layout_realization.relationship_metadata_writer import METADATA_KEYS
from src.runtime.layout_realization.transform_resolver import ResolvedTransform

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERSISTENCE_AUDIT_PASS = "PASS"
PERSISTENCE_AUDIT_FAIL = "FAIL"

REQUIRED_METADATA_KEYS: List[str] = list(METADATA_KEYS)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AssetMetadataRecord:
    """
    Per-asset audit row. All string fields come from Houdini user-data;
    metadata_* flags are derived by the auditor.
    """
    asset_id:  str
    asset_name: str   # Houdini node name (from hou.Node.name())
    node_path:  str

    # Values read from Houdini user-data
    asset_role:        str = ""
    relationship_type: str = ""
    expected_parent:   str = ""
    actual_parent:     str = ""
    support_surface:   str = ""
    anchor_id:         str = ""
    anchor_type:       str = ""
    placement_engine:  str = ""
    layout_cluster_id: str = ""

    # Derived audit flags
    metadata_exists:         bool       = False   # at least 1 vibrante_ key found
    metadata_complete:       bool       = False   # all 9 required keys present
    metadata_matches_layout: bool       = False   # relationship_type + expected_parent match plan
    missing_keys:            List[str]  = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_name":              self.asset_name,
            "role":                    self.asset_role,
            "relationship_type":       self.relationship_type,
            "expected_parent":         self.expected_parent,
            "actual_parent":           self.actual_parent,
            "support_surface":         self.support_surface,
            "placement_engine":        self.placement_engine,
            "metadata_exists":         self.metadata_exists,
            "metadata_complete":       self.metadata_complete,
            "metadata_matches_layout": self.metadata_matches_layout,
            "missing_keys":            list(self.missing_keys),
        }


@dataclass
class RelationshipPersistenceAuditResult:
    """Full output of RelationshipPersistenceAuditor.audit()."""

    records:                List[AssetMetadataRecord] = field(default_factory=list)

    total_assets:           int   = 0
    assets_with_metadata:   int   = 0   # metadata_exists == True
    assets_complete:        int   = 0   # metadata_complete == True
    assets_matching_layout: int   = 0   # metadata_matches_layout == True
    missing_metadata:       int   = 0   # total_assets - assets_complete

    metadata_coverage:      float = 0.0  # assets_complete / total_assets

    status:          str  = PERSISTENCE_AUDIT_FAIL
    production_ready: bool = False
    audit_table:      str  = ""

    ok:     bool      = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "records":                  [r.to_dict() for r in self.records],
            "total_assets":             self.total_assets,
            "assets_with_metadata":     self.assets_with_metadata,
            "assets_complete":          self.assets_complete,
            "assets_matching_layout":   self.assets_matching_layout,
            "missing_metadata":         self.missing_metadata,
            "metadata_coverage":        round(self.metadata_coverage, 4),
            "status":                   self.status,
            "production_ready":         self.production_ready,
            "audit_table":              self.audit_table,
            "ok":                       self.ok,
            "errors":                   list(self.errors),
        }


# ---------------------------------------------------------------------------
# Auditor (pure planning — no bridge calls)
# ---------------------------------------------------------------------------

class RelationshipPersistenceAuditor:
    """
    Validates relationship metadata completeness and layout fidelity.

    Usage (tests — inject node_metadata directly):
        auditor = get_relationship_persistence_auditor()
        result  = auditor.audit(
            node_metadata      = {"chair_01": {"vibrante_asset_role": "cluster_member", ...}},
            node_names         = {"chair_01": "chair_01"},
            node_paths         = {"chair_01": "/obj/scene/chair_01"},
            planned_transforms = planned,   # optional, for layout comparison
        )

    Usage (production — fetch from Houdini via HoudiniMetadataFetcher):
        node_metadata, node_names, node_paths = HoudiniMetadataFetcher().fetch_metadata(node_path_map)
        result = auditor.audit(node_metadata, node_names, node_paths, planned_transforms)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def audit(
        self,
        node_metadata:      Dict[str, Dict[str, str]],
        node_names:         Optional[Dict[str, str]]           = None,
        node_paths:         Optional[Dict[str, str]]           = None,
        planned_transforms: Optional[List[ResolvedTransform]]  = None,
    ) -> RelationshipPersistenceAuditResult:
        """
        Audit metadata completeness for every asset in node_metadata.

        Args:
            node_metadata:      {asset_id: {vibrante_key: value, ...}}
                                Keys that are absent mean the metadata was never written.
            node_names:         {asset_id: houdini_node_name} — optional, used for report
            node_paths:         {asset_id: node_path}         — optional, used for report
            planned_transforms: planned ResolvedTransform list — optional, used for
                                metadata_matches_layout comparison

        Returns: RelationshipPersistenceAuditResult. Never raises.
        """
        try:
            return self._audit(
                node_metadata,
                node_names or {},
                node_paths or {},
                planned_transforms or [],
            )
        except Exception as exc:
            return RelationshipPersistenceAuditResult(
                ok=False,
                errors=[f"RelationshipPersistenceAuditor.audit failed: {exc}"],
                status=PERSISTENCE_AUDIT_FAIL,
            )

    def _audit(
        self,
        node_metadata:      Dict[str, Dict[str, str]],
        node_names:         Dict[str, str],
        node_paths:         Dict[str, str],
        planned_transforms: List[ResolvedTransform],
    ) -> RelationshipPersistenceAuditResult:

        # Build planned_map for layout-match comparison
        planned_map: Dict[str, ResolvedTransform] = {
            t.asset_id: t for t in planned_transforms
        }

        records: List[AssetMetadataRecord] = []

        for asset_id, meta in node_metadata.items():
            node_name = node_names.get(asset_id, asset_id)
            node_path = node_paths.get(asset_id, "")
            planned   = planned_map.get(asset_id)
            rec       = self._build_record(asset_id, meta, node_name, node_path, planned)
            records.append(rec)

        total    = len(records)
        n_exist  = sum(1 for r in records if r.metadata_exists)
        n_comp   = sum(1 for r in records if r.metadata_complete)
        n_match  = sum(1 for r in records if r.metadata_matches_layout)
        missing  = total - n_comp
        coverage = (n_comp / total) if total > 0 else 1.0  # vacuous pass for empty set

        passed   = coverage >= 1.0 and missing == 0
        audit_table = _format_table(records, coverage, missing)

        return RelationshipPersistenceAuditResult(
            records                = records,
            total_assets           = total,
            assets_with_metadata   = n_exist,
            assets_complete        = n_comp,
            assets_matching_layout = n_match,
            missing_metadata       = missing,
            metadata_coverage      = round(coverage, 4),
            status                 = PERSISTENCE_AUDIT_PASS if passed else PERSISTENCE_AUDIT_FAIL,
            production_ready       = passed,
            audit_table            = audit_table,
            ok                     = passed,
        )

    def _build_record(
        self,
        asset_id:  str,
        meta:      Dict[str, str],
        node_name: str,
        node_path: str,
        planned:   Optional[ResolvedTransform],
    ) -> AssetMetadataRecord:
        # Detect which keys are present
        present = {k for k in REQUIRED_METADATA_KEYS if k in meta}
        missing = [k for k in REQUIRED_METADATA_KEYS if k not in meta]

        exists   = len(present) > 0
        complete = len(missing) == 0

        # Extract values (default "" for absent keys)
        role      = meta.get("vibrante_asset_role",        "")
        rel_type  = meta.get("vibrante_relationship_type", "")
        exp_par   = meta.get("vibrante_expected_parent",   "")
        act_par   = meta.get("vibrante_actual_parent",     "")
        surface   = meta.get("vibrante_support_surface",   "")
        anchor_id = meta.get("vibrante_anchor_id",         "")
        anc_type  = meta.get("vibrante_anchor_type",       "")
        engine    = meta.get("vibrante_placement_engine",  "")
        cluster   = meta.get("vibrante_layout_cluster_id", "")

        # Layout match: relationship_type and expected_parent match the plan
        matches_layout = False
        if complete and planned is not None:
            rel_ok = rel_type == (planned.relationship or "")
            par_ok = exp_par  == (planned.parent_id    or "")
            matches_layout = rel_ok and par_ok
        elif complete and planned is None:
            # No plan to compare against — mark as matching (no contradiction)
            matches_layout = True

        return AssetMetadataRecord(
            asset_id               = asset_id,
            asset_name             = node_name,
            node_path              = node_path,
            asset_role             = role,
            relationship_type      = rel_type,
            expected_parent        = exp_par,
            actual_parent          = act_par,
            support_surface        = surface,
            anchor_id              = anchor_id,
            anchor_type            = anc_type,
            placement_engine       = engine,
            layout_cluster_id      = cluster,
            metadata_exists        = exists,
            metadata_complete      = complete,
            metadata_matches_layout= matches_layout,
            missing_keys           = missing,
        )


# ---------------------------------------------------------------------------
# Houdini bridge adapter (isolated — the ONLY component that calls get_bridge)
# ---------------------------------------------------------------------------

class HoudiniMetadataFetcher:
    """
    Reads vibrante_ user-data keys from live Houdini nodes via run_code().

    Call fetch_metadata(node_path_map) from the Houdini node and pass the
    returned tuple directly to RelationshipPersistenceAuditor.audit().
    """

    def fetch_metadata(
        self,
        node_path_map: Dict[str, str],
    ) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, str]]:
        """
        Returns:
            node_metadata — {asset_id: {vibrante_key: value, ...}}
            node_names    — {asset_id: hou.Node.name()}
            node_paths    — {asset_id: node_path}

        Never raises; missing / errored nodes produce empty metadata dicts.
        """
        from src.utils.hou_bridge import get_bridge
        bridge = get_bridge()

        node_metadata: Dict[str, Dict[str, str]] = {}
        node_names:    Dict[str, str]             = {}
        node_paths:    Dict[str, str]             = {}

        # Build key list repr once
        keys_repr = repr(REQUIRED_METADATA_KEYS)

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
                    "        'metadata': {k: (_n.userData(k) or '') for k in " + keys_repr + "},\n"
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
    records:  List[AssetMetadataRecord],
    coverage: float,
    missing:  int,
) -> str:
    w1, w2, w3, w4 = 22, 16, 20, 8
    sep = "-" * (w1 + w2 + w3 + w4 + 12)
    header = (
        f"{'asset_name':<{w1}} {'role':<{w2}} {'relationship':<{w3}} {'status':<{w4}}"
        f"  missing_keys"
    )
    lines = ["", "RELATIONSHIP METADATA PERSISTENCE AUDIT", sep, header, sep]

    for r in records:
        status = "COMPLETE" if r.metadata_complete else "MISSING"
        mk_str = ", ".join(k.replace("vibrante_", "") for k in r.missing_keys) or "—"
        lines.append(
            f"{r.asset_name:<{w1}} {r.asset_role:<{w2}} "
            f"{r.relationship_type:<{w3}} {status:<{w4}}  {mk_str}"
        )

    lines.append(sep)
    n_total = len(records)
    n_comp  = sum(1 for r in records if r.metadata_complete)
    lines.append(
        f"Coverage: {coverage:.1%} ({n_comp}/{n_total})"
        f"  Missing: {missing}"
        f"  Status: {'PASS' if coverage >= 1.0 and missing == 0 else 'FAIL'}"
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RelationshipPersistenceAuditor] = None
_lock = threading.Lock()


def get_relationship_persistence_auditor() -> RelationshipPersistenceAuditor:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RelationshipPersistenceAuditor()
    return _instance


def reset_relationship_persistence_auditor_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
