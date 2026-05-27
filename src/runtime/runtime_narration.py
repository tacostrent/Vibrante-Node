"""
Runtime Narration
=================
Continuously narrates orchestration reasoning with labeled blocks.
Replaces opaque "running..." status with specific, informative narration of
what the runtime is doing and why.

Block format:
  [Runtime]    — system-level messages (startup, shutdown, session events)
  [Planning]   — goal decomposition, workflow selection, intent parsing
  [Validation] — constraint checks, op validation, capability checks
  [Preview]    — pre-execution analysis, risk assessment, dependency review
  [Execution]  — active execution steps, node creation, parm setting
  [Review]     — post-execution critique, artistic assessment, production check

Design rules:
  - Deterministic — same input always produces same output.
  - No LLM calls — template-based narration only.
  - No bridge calls — pure in-memory operation.
  - Thread-safe — multiple nodes can narrate concurrently.

Public API:
    get_runtime_narration() -> RuntimeNarration    (singleton)
    reset_runtime_narration_for_tests()

    RuntimeNarration.narrate(block, message, context=None) -> NarrationEntry
    RuntimeNarration.narrate_decomposition(goal, result) -> str
    RuntimeNarration.narrate_execution_start(workflow_id, stages) -> str
    RuntimeNarration.narrate_stage_start(workflow_id, stage_id, description) -> str
    RuntimeNarration.narrate_stage_complete(workflow_id, stage_id, passed) -> str
    RuntimeNarration.narrate_review(workflow_id, review_result) -> str
    RuntimeNarration.get_session_log(limit=50) -> list[NarrationEntry]
    RuntimeNarration.clear_log() -> None
    RuntimeNarration.stats() -> dict
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Block types
# ---------------------------------------------------------------------------

NARRATION_BLOCKS = frozenset(["Runtime", "Planning", "Validation", "Preview", "Execution", "Review"])

# ---------------------------------------------------------------------------
# NarrationEntry
# ---------------------------------------------------------------------------

class NarrationEntry:
    """A single narration event with block label, message, and timestamp."""

    __slots__ = ("block", "message", "context", "timestamp", "formatted")

    def __init__(
        self,
        block: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.block = block
        self.message = message
        self.context = context or {}
        self.timestamp = time.monotonic()
        self.formatted = f"[{block}] {message}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block": self.block,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp,
            "formatted": self.formatted,
        }

    def __str__(self) -> str:
        return self.formatted


# ---------------------------------------------------------------------------
# Narration templates
# ---------------------------------------------------------------------------

_DECOMPOSITION_TEMPLATES = {
    "composite_match": (
        "Goal '{goal}' matched composite workflow '{matched_key}' "
        "→ {workflow_count} ordered workflows, {stage_count} total stages."
    ),
    "keyword_match": (
        "Goal '{goal}' matched {workflow_count} workflow(s) via keyword: "
        "{workflows}. Expanded to {stage_count} ordered stages."
    ),
    "no_match": (
        "Goal '{goal}' did not match any known workflow. "
        "Use more specific cinematic terminology (e.g. 'cinematic explosion', 'dust wave', 'arnold lighting')."
    ),
    "forced": (
        "Workflow forced via context override: '{workflow_id}'. "
        "Proceeding with {stage_count} known stages."
    ),
}

_EXECUTION_TEMPLATES = {
    "start": (
        "Beginning '{workflow_id}' execution. "
        "{stage_count} ordered stages queued: {stage_list}."
    ),
    "stage_start": (
        "Stage [{stage_id}]: {description}"
    ),
    "stage_pass": (
        "Stage [{stage_id}] ✓ complete."
    ),
    "stage_fail": (
        "Stage [{stage_id}] ✗ failed — {critique}"
    ),
    "stage_warning": (
        "Stage [{stage_id}] ⚠ warning — {critique}"
    ),
}

_REVIEW_TEMPLATES = {
    "production_ready": (
        "Workflow '{workflow_id}' is production-ready. "
        "All {stage_count} stage reviews passed."
    ),
    "has_critiques": (
        "Workflow '{workflow_id}' review complete — {pass_count}/{stage_count} stages passed. "
        "Critical issues: {issue_count}. Advisory notes: {note_count}. "
        "Top issue: {top_issue}"
    ),
    "advisory_only": (
        "Workflow '{workflow_id}' passed with {note_count} advisory note(s). "
        "Production-ready with recommended refinements: {top_note}"
    ),
}

_VALIDATION_TEMPLATES = {
    "pass": "Validation passed: {op_count} operations, risk level '{risk_level}'.",
    "fail": "Validation failed: {error_count} error(s). Top error: {top_error}",
    "warning": "Validation passed with {warning_count} warning(s). Risk: '{risk_level}'.",
    "constraint_blocked": "RuntimeConstraints blocked execution: {violation}",
    "capability_gap": "Required capability '{capability}' is not registered. Workflow may fail.",
}

_PREVIEW_TEMPLATES = {
    "low_risk": "Execution preview: {op_count} operations, low risk. Safe to proceed.",
    "medium_risk": (
        "Execution preview: {op_count} operations, medium risk. "
        "Recommended: wrap in transaction, enable rollback-on-error."
    ),
    "high_risk": (
        "Execution preview: {op_count} operations, HIGH RISK. "
        "{delete_count} destructive operations. Approval required before execution."
    ),
    "dry_run": "Dry-run validation complete: {op_count} operations validated. No execution performed.",
}

_RUNTIME_TEMPLATES = {
    "init": "Runtime initialized. Tiers 1–6 active. Semantic layer ready.",
    "session_start": "Session '{client_id}' connected. Bootstrap data delivered.",
    "session_end": "Session '{client_id}' closed. {event_count} events recorded.",
    "shutdown": "Runtime shutdown initiated. Closing MCP sessions.",
    "bridge_unavailable": (
        "Houdini bridge not available. Scene context and execution operations "
        "require Houdini + bridge on port {port}."
    ),
}


# ---------------------------------------------------------------------------
# RuntimeNarration
# ---------------------------------------------------------------------------

class RuntimeNarration:
    """Narrates orchestration reasoning with labeled blocks.

    Singleton — access via get_runtime_narration().
    """

    def __init__(self, max_log_size: int = 500) -> None:
        self._lock = threading.Lock()
        self._log: List[NarrationEntry] = []
        self._max_log_size = max_log_size
        self._narrate_count = 0

    # ------------------------------------------------------------------
    # Core narrate
    # ------------------------------------------------------------------

    def narrate(
        self,
        block: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> NarrationEntry:
        """Create and log a narration entry.

        Args:
            block:   One of NARRATION_BLOCKS ("Runtime", "Planning", etc.)
            message: The specific message to narrate.
            context: Optional context metadata stored with the entry.

        Returns:
            NarrationEntry that was logged.
        """
        if block not in NARRATION_BLOCKS:
            block = "Runtime"  # safe fallback

        entry = NarrationEntry(block=block, message=message, context=context)

        with self._lock:
            self._log.append(entry)
            self._narrate_count += 1
            # Trim if over max
            if len(self._log) > self._max_log_size:
                self._log = self._log[-self._max_log_size:]

        return entry

    # ------------------------------------------------------------------
    # Semantic narration helpers
    # ------------------------------------------------------------------

    def narrate_decomposition(self, goal: str, result: Any) -> str:
        """Narrate the result of a goal decomposition.

        Args:
            goal:   The original goal string.
            result: A DecompositionResult (or dict with matched_workflows, stages, notes).

        Returns:
            The formatted narration string.
        """
        if hasattr(result, "to_dict"):
            result_dict = result.to_dict()
        else:
            result_dict = dict(result) if result else {}

        matched_workflows = result_dict.get("matched_workflows", [])
        stages = result_dict.get("stages", [])
        notes = result_dict.get("notes", [])
        confidence = result_dict.get("confidence", 0.0)

        if not matched_workflows:
            message = _DECOMPOSITION_TEMPLATES["no_match"].format(goal=goal)
        elif any("Composite goal matched" in n for n in notes):
            matched_key = next((n.split("'")[1] for n in notes if "Composite goal matched" in n), goal)
            message = _DECOMPOSITION_TEMPLATES["composite_match"].format(
                goal=goal,
                matched_key=matched_key,
                workflow_count=len(matched_workflows),
                stage_count=len(stages),
            )
        elif any("workflow_id override" in n for n in notes):
            message = _DECOMPOSITION_TEMPLATES["forced"].format(
                workflow_id=matched_workflows[0] if matched_workflows else "unknown",
                stage_count=len(stages),
            )
        else:
            workflows_str = ", ".join(matched_workflows[:4])
            if len(matched_workflows) > 4:
                workflows_str += f" +{len(matched_workflows) - 4} more"
            message = _DECOMPOSITION_TEMPLATES["keyword_match"].format(
                goal=goal,
                workflow_count=len(matched_workflows),
                workflows=workflows_str,
                stage_count=len(stages),
            )

        if confidence < 0.7 and matched_workflows:
            message += f" (confidence: {confidence:.0%})"

        entry = self.narrate("Planning", message, context={"goal": goal, "confidence": confidence})
        return entry.formatted

    def narrate_execution_start(self, workflow_id: str, stages: List[str]) -> str:
        """Narrate the start of a workflow execution."""
        stage_list = ", ".join(stages[:6])
        if len(stages) > 6:
            stage_list += f" +{len(stages) - 6} more"

        message = _EXECUTION_TEMPLATES["start"].format(
            workflow_id=workflow_id,
            stage_count=len(stages),
            stage_list=stage_list,
        )
        entry = self.narrate("Execution", message, context={"workflow_id": workflow_id})
        return entry.formatted

    def narrate_stage_start(
        self, workflow_id: str, stage_id: str, description: str = ""
    ) -> str:
        """Narrate the start of a specific stage."""
        desc = description or f"Executing stage '{stage_id}' within {workflow_id}."
        message = _EXECUTION_TEMPLATES["stage_start"].format(
            stage_id=stage_id, description=desc
        )
        entry = self.narrate(
            "Execution", message,
            context={"workflow_id": workflow_id, "stage_id": stage_id}
        )
        return entry.formatted

    def narrate_stage_complete(
        self, workflow_id: str, stage_id: str, passed: bool, critique: str = ""
    ) -> str:
        """Narrate the completion of a stage."""
        if passed:
            message = _EXECUTION_TEMPLATES["stage_pass"].format(stage_id=stage_id)
            block = "Execution"
        elif critique:
            message = _EXECUTION_TEMPLATES["stage_fail"].format(
                stage_id=stage_id, critique=critique
            )
            block = "Review"
        else:
            message = _EXECUTION_TEMPLATES["stage_warning"].format(
                stage_id=stage_id, critique="review required"
            )
            block = "Review"

        entry = self.narrate(
            block, message,
            context={"workflow_id": workflow_id, "stage_id": stage_id, "passed": passed}
        )
        return entry.formatted

    def narrate_review(self, workflow_id: str, review_result: Any) -> str:
        """Narrate a ReviewResult from the review engine.

        Args:
            workflow_id:   The workflow that was reviewed.
            review_result: A ReviewResult object or dict.

        Returns:
            The formatted narration string.
        """
        if hasattr(review_result, "to_dict"):
            rdict = review_result.to_dict()
        else:
            rdict = dict(review_result) if review_result else {}

        production_ready = rdict.get("production_ready", False)
        stage_count = rdict.get("stage_count", 0)
        failed_stages = rdict.get("failed_stages", 0)
        critical_issues = rdict.get("critical_issues", [])
        advisory_notes = rdict.get("advisory_notes", [])
        pass_count = stage_count - failed_stages

        if production_ready:
            message = _REVIEW_TEMPLATES["production_ready"].format(
                workflow_id=workflow_id,
                stage_count=stage_count,
            )
        elif critical_issues:
            top_issue = critical_issues[0] if critical_issues else "See stage reviews."
            message = _REVIEW_TEMPLATES["has_critiques"].format(
                workflow_id=workflow_id,
                pass_count=pass_count,
                stage_count=stage_count,
                issue_count=len(critical_issues),
                note_count=len(advisory_notes),
                top_issue=top_issue,
            )
        else:
            top_note = advisory_notes[0] if advisory_notes else "All stages reviewed."
            message = _REVIEW_TEMPLATES["advisory_only"].format(
                workflow_id=workflow_id,
                note_count=len(advisory_notes),
                top_note=top_note,
            )

        entry = self.narrate("Review", message, context={"workflow_id": workflow_id})
        return entry.formatted

    def narrate_validation(self, validation_result: Dict[str, Any]) -> str:
        """Narrate a ValidationEngine result."""
        valid = validation_result.get("valid", False)
        risk = validation_result.get("risk_level", "low")
        errors = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])
        op_count = validation_result.get("op_count", 0)
        dry_run = validation_result.get("status") == "validated"

        if dry_run:
            message = _VALIDATION_TEMPLATES["pass"].format(
                op_count=op_count, risk_level=risk
            )
            message = f"[dry-run] " + message
        elif not valid:
            top_error = errors[0].get("message", "Unknown error") if errors else "Validation failed."
            message = _VALIDATION_TEMPLATES["fail"].format(
                error_count=len(errors), top_error=top_error
            )
        elif warnings:
            message = _VALIDATION_TEMPLATES["warning"].format(
                warning_count=len(warnings), risk_level=risk
            )
        else:
            message = _VALIDATION_TEMPLATES["pass"].format(
                op_count=op_count, risk_level=risk
            )

        entry = self.narrate("Validation", message, context=validation_result)
        return entry.formatted

    def narrate_preview(self, preview_data: Dict[str, Any]) -> str:
        """Narrate an execution preview result."""
        risk = preview_data.get("risk_level", "low")
        op_count = preview_data.get("op_count", len(preview_data.get("nodes_to_create", [])))
        delete_count = len(preview_data.get("nodes_to_delete", []))
        dry_run = preview_data.get("status") == "validated"

        if dry_run:
            message = _PREVIEW_TEMPLATES["dry_run"].format(op_count=op_count)
        elif risk == "high":
            message = _PREVIEW_TEMPLATES["high_risk"].format(
                op_count=op_count, delete_count=delete_count
            )
        elif risk == "medium":
            message = _PREVIEW_TEMPLATES["medium_risk"].format(op_count=op_count)
        else:
            message = _PREVIEW_TEMPLATES["low_risk"].format(op_count=op_count)

        entry = self.narrate("Preview", message, context=preview_data)
        return entry.formatted

    def narrate_runtime_event(self, event: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Narrate a runtime system event."""
        ctx = context or {}
        template = _RUNTIME_TEMPLATES.get(event, f"Runtime event: {event}")
        try:
            message = template.format(**ctx)
        except KeyError:
            message = template  # use unformatted if context keys missing

        entry = self.narrate("Runtime", message, context=ctx)
        return entry.formatted

    # ------------------------------------------------------------------
    # Log access
    # ------------------------------------------------------------------

    def get_session_log(self, limit: int = 50) -> List[NarrationEntry]:
        """Return the most recent narration entries."""
        with self._lock:
            return list(self._log[-limit:])

    def get_formatted_log(self, limit: int = 50) -> List[str]:
        """Return the most recent entries as formatted strings."""
        return [e.formatted for e in self.get_session_log(limit)]

    def clear_log(self) -> None:
        """Clear the in-memory narration log."""
        with self._lock:
            self._log.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "narrate_count": self._narrate_count,
                "log_size": len(self._log),
                "max_log_size": self._max_log_size,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RuntimeNarration] = None
_instance_lock = threading.Lock()


def get_runtime_narration() -> RuntimeNarration:
    """Return the RuntimeNarration singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RuntimeNarration()
    return _instance


def reset_runtime_narration_for_tests() -> None:
    """Reset singleton for test isolation."""
    global _instance
    with _instance_lock:
        _instance = None
