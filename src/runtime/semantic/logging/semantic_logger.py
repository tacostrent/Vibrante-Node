"""
Semantic Pipeline Logger (Phase 1)
=====================================
Structured event logging for the scene intent extraction pipeline.

Produces inspectable, replayable, debuggable pipeline traces without
storing any raw user data beyond what is structurally necessary.

Every log entry records:
  - A stage name (extraction, validation, enrichment, serialization)
  - An event type (start, complete, error, warning)
  - Structured data specific to that stage
  - A monotonic timestamp

Entries are held in memory (capped list) and can be exported to JSON.
No file I/O by default — consumers decide where to persist the log.

Design rules:
  - Never store raw LLM responses verbatim (store only structured fields).
  - Never store raw user prompts longer than 500 chars (truncate).
  - Log entries are immutable once written.
  - Thread-safe.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIPELINE_STAGES = frozenset({
    "extraction",
    "validation",
    "enrichment",
    "serialization",
    "orchestration",
})

EVENT_TYPES = frozenset({
    "start",
    "complete",
    "error",
    "warning",
    "skip",
})

_MAX_PROMPT_CHARS = 500
_DEFAULT_MAX_ENTRIES = 200


# ---------------------------------------------------------------------------
# Log entry
# ---------------------------------------------------------------------------

@dataclass
class SemanticLogEntry:
    """A single structured pipeline log entry.

    Attributes:
        entry_id:    Unique identifier.
        stage:       Pipeline stage name.
        event_type:  Event classification.
        data:        Structured event data dict.
        timestamp:   Monotonic seconds since epoch.
        intent_id:   Optional intent identifier this entry relates to.
    """
    entry_id:   str              = field(default_factory=lambda: str(uuid.uuid4())[:8])
    stage:      str              = "orchestration"
    event_type: str              = "start"
    data:       Dict[str, Any]   = field(default_factory=dict)
    timestamp:  float            = field(default_factory=time.monotonic)
    intent_id:  Optional[str]    = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id":   self.entry_id,
            "stage":      self.stage,
            "event_type": self.event_type,
            "data":       dict(self.data),
            "timestamp":  self.timestamp,
            "intent_id":  self.intent_id,
        }

    @property
    def formatted(self) -> str:
        intent_part = f" [{self.intent_id[:8]}]" if self.intent_id else ""
        data_summary = ", ".join(f"{k}={v!r}" for k, v in list(self.data.items())[:3])
        return f"[{self.stage}:{self.event_type}]{intent_part} {data_summary}"

    def __str__(self) -> str:
        return self.formatted


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class SemanticLogger:
    """Thread-safe pipeline logger for the scene intent extraction pipeline.

    Usage::

        logger = SemanticLogger()
        logger.log_extraction_start("create a burning city at night")
        logger.log_extraction_complete(intent_id, confidence=0.87, fields_extracted=8)
        logger.log_validation_complete(intent_id, valid=True, error_count=0)
        logger.log_enrichment_complete(intent_id, rules_fired=3)
        entries = logger.get_entries()
    """

    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES):
        self._max_entries = max_entries
        self._entries: List[SemanticLogEntry] = []
        self._lock = threading.Lock()
        self._log_count = 0

    # ------------------------------------------------------------------
    # High-level convenience methods
    # ------------------------------------------------------------------

    def log_extraction_start(self, prompt: str, intent_id: Optional[str] = None) -> None:
        """Log the start of an extraction call."""
        truncated = prompt[:_MAX_PROMPT_CHARS] + ("..." if len(prompt) > _MAX_PROMPT_CHARS else "")
        self._log("extraction", "start",
                  {"prompt_length": len(prompt), "prompt_preview": truncated[:80]},
                  intent_id=intent_id)

    def log_extraction_complete(
        self,
        intent_id: str,
        confidence: float,
        fields_extracted: int,
        llm_enhanced: bool = False,
    ) -> None:
        """Log a successful extraction."""
        self._log("extraction", "complete", {
            "confidence":      round(confidence, 3),
            "fields_extracted":fields_extracted,
            "llm_enhanced":    llm_enhanced,
        }, intent_id=intent_id)

    def log_extraction_error(
        self,
        error: str,
        intent_id: Optional[str] = None,
    ) -> None:
        """Log an extraction failure."""
        self._log("extraction", "error", {"error": str(error)}, intent_id=intent_id)

    def log_validation_complete(
        self,
        intent_id: str,
        valid: bool,
        error_count: int,
        warning_count: int = 0,
    ) -> None:
        """Log validation outcome."""
        self._log("validation", "complete" if valid else "error", {
            "valid":         valid,
            "error_count":   error_count,
            "warning_count": warning_count,
        }, intent_id=intent_id)

    def log_enrichment_complete(
        self,
        intent_id: str,
        rules_fired: int,
        effects_added: int = 0,
        fx_inferred: int = 0,
        assets_inferred: int = 0,
    ) -> None:
        """Log enrichment pass completion."""
        self._log("enrichment", "complete", {
            "rules_fired":     rules_fired,
            "effects_added":   effects_added,
            "fx_inferred":     fx_inferred,
            "assets_inferred": assets_inferred,
        }, intent_id=intent_id)

    def log_warning(
        self,
        stage: str,
        message: str,
        intent_id: Optional[str] = None,
    ) -> None:
        """Log an advisory warning for any stage."""
        stage = stage if stage in PIPELINE_STAGES else "orchestration"
        self._log(stage, "warning", {"message": message}, intent_id=intent_id)

    # ------------------------------------------------------------------
    # Log management
    # ------------------------------------------------------------------

    def get_entries(
        self,
        stage: Optional[str] = None,
        event_type: Optional[str] = None,
        intent_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[SemanticLogEntry]:
        """Return log entries with optional filters."""
        with self._lock:
            entries = list(self._entries)

        if stage:
            entries = [e for e in entries if e.stage == stage]
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        if intent_id:
            entries = [e for e in entries if e.intent_id == intent_id]
        if limit is not None:
            entries = entries[-limit:]

        return entries

    def get_formatted_log(self, limit: Optional[int] = None) -> List[str]:
        """Return formatted log strings."""
        entries = self.get_entries(limit=limit)
        return [e.formatted for e in entries]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Return all entries as a list of dicts (JSON-serializable)."""
        with self._lock:
            return [e.to_dict() for e in self._entries]

    def clear(self) -> None:
        """Clear all log entries."""
        with self._lock:
            self._entries.clear()

    def stats(self) -> Dict[str, Any]:
        """Return logger statistics."""
        with self._lock:
            by_stage: Dict[str, int] = {}
            by_event: Dict[str, int] = {}
            for e in self._entries:
                by_stage[e.stage] = by_stage.get(e.stage, 0) + 1
                by_event[e.event_type] = by_event.get(e.event_type, 0) + 1
            return {
                "log_count":  self._log_count,
                "entry_count":len(self._entries),
                "max_entries":self._max_entries,
                "by_stage":   by_stage,
                "by_event":   by_event,
            }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _log(
        self,
        stage: str,
        event_type: str,
        data: Dict[str, Any],
        intent_id: Optional[str] = None,
    ) -> None:
        resolved_stage = stage if stage in PIPELINE_STAGES else "orchestration"
        resolved_event = event_type if event_type in EVENT_TYPES else "warning"

        entry = SemanticLogEntry(
            stage=resolved_stage,
            event_type=resolved_event,
            data=data,
            intent_id=intent_id,
        )
        with self._lock:
            self._entries.append(entry)
            self._log_count += 1
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]


# ---------------------------------------------------------------------------
# Shared instance
# ---------------------------------------------------------------------------

_logger: Optional[SemanticLogger] = None


def get_semantic_logger() -> SemanticLogger:
    """Return the shared SemanticLogger instance."""
    global _logger
    if _logger is None:
        _logger = SemanticLogger()
    return _logger


def reset_semantic_logger_for_tests() -> None:
    """Reset shared instance for test isolation."""
    global _logger
    _logger = None
