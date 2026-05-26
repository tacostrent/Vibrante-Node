"""
Agent Runtime (Tier 4)
=======================
Runtime-supervised advisory agent system.  Agents may propose plans,
suggest workflows, analyze scenes, and generate semantic intents.

AGENTS MAY NOT:
  - execute operations directly
  - bypass validation or approval
  - bypass runtime constraints
  - mutate DCC state

All agent proposals pass through the full Tier 3 pipeline (IntentParser
→ AIPlanner → PlanValidator) before being returned.  The runtime decides
whether a proposal may proceed.  Agents are always advisory.

Supervision levels:
    "strict"   — proposal is always flagged requires_approval=True
    "standard" — auto-allows safe (risk_level != "high") proposals
    "advisory" — dry_run semantics; never authorises execution

Public API:
    get_agent_runtime() -> AgentRuntime   (singleton)
    reset_agent_runtime_for_tests()

    AgentRuntime.register_agent(name, role, capabilities, supervision_level) -> str
    AgentRuntime.deregister_agent(agent_id) -> bool
    AgentRuntime.submit_proposal(agent_id, proposal) -> dict   (async)
    AgentRuntime.get_agent(agent_id) -> dict | None
    AgentRuntime.list_agents(role=None) -> list[dict]
    AgentRuntime.stats() -> dict
"""

import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

SUPERVISION_LEVELS = frozenset({"strict", "standard", "advisory"})
AGENT_ROLES        = frozenset({"scene_analyzer", "workflow_suggester", "optimizer", "custom"})


class AgentRuntime:
    """Supervises advisory agents and routes proposals through the runtime."""

    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._agents:    Dict[str, Dict[str, Any]] = {}
        self._proposals: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        name:             str,
        role:             str = "custom",
        capabilities:     Optional[List[str]] = None,
        supervision_level: str = "standard",
    ) -> str:
        """Register an agent and return its agent_id.

        Raises:
            ValueError: If supervision_level or role is invalid.
        """
        if supervision_level not in SUPERVISION_LEVELS:
            raise ValueError(
                f"Invalid supervision_level {supervision_level!r}. "
                f"Valid: {sorted(SUPERVISION_LEVELS)}"
            )
        agent_id = str(uuid.uuid4())
        with self._lock:
            self._agents[agent_id] = {
                "id":               agent_id,
                "name":             name,
                "role":             role,
                "capabilities":     list(capabilities or []),
                "supervision_level": supervision_level,
                "registered_at":    time.time(),
                "proposal_count":   0,
            }
        return agent_id

    def deregister_agent(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                return True
        return False

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            a = self._agents.get(agent_id)
            return dict(a) if a else None

    def list_agents(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            agents = list(self._agents.values())
        if role:
            agents = [a for a in agents if a.get("role") == role]
        return [dict(a) for a in sorted(agents, key=lambda a: a["registered_at"])]

    # ------------------------------------------------------------------
    # Proposal submission
    # ------------------------------------------------------------------

    async def submit_proposal(
        self,
        agent_id: str,
        proposal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit an agent proposal through the runtime supervision pipeline.

        The proposal dict must contain at least one of:
            "prompt"   — natural language intent string
            "intent"   — pre-parsed intent name
            "context"  — optional planning context dict

        Returns a supervision result. The proposal is NEVER executed here —
        the caller decides whether to forward to hou_mcp_ai_execute.
        """
        agent = self.get_agent(agent_id)
        if agent is None:
            return {
                "ok":         False,
                "proposal_id": None,
                "error":      f"Unknown agent: {agent_id!r}",
            }

        supervision_level = agent["supervision_level"]
        proposal_id       = str(uuid.uuid4())

        # Increment agent proposal count
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id]["proposal_count"] += 1

        prompt   = str(proposal.get("prompt", "")).strip()
        intent   = str(proposal.get("intent", "")).strip()
        context  = dict(proposal.get("context") or {})

        # Need a prompt or intent to plan from
        if not prompt and not intent:
            return {
                "ok":          False,
                "proposal_id": proposal_id,
                "agent_id":    agent_id,
                "error":       "Proposal must include 'prompt' or 'intent'",
            }

        try:
            from src.runtime.intent_parser        import get_intent_parser
            from src.runtime.contextual_reasoning import get_contextual_reasoner
            from src.runtime.ai_planner           import get_ai_planner
            from src.runtime.plan_validator       import get_plan_validator
            from src.runtime.execution_explainer  import get_execution_explainer

            # 1. Parse intent (if only prompt provided)
            if prompt and not intent:
                parsed = await get_intent_parser().parse(prompt, context)
            else:
                parsed = {
                    "intent":     intent,
                    "parameters": context,
                    "confidence": 1.0,
                    "llm_enhanced": False,
                }

            # 2. Contextual analysis
            ctx_analysis = get_contextual_reasoner().analyze(
                parsed.get("intent", ""), parsed.get("parameters", {}), None
            )

            # 3. Generate plan
            plan = await get_ai_planner().plan(parsed, ctx_analysis, None)

            # 4. Validate plan
            validation = await get_plan_validator().validate(plan)

            # 5. Apply supervision rules
            supervision_result = self._apply_supervision(
                supervision_level, plan, validation
            )

            # 6. Explain
            expl = get_execution_explainer().explain_plan(plan)

        except Exception as exc:
            record = {
                "ok":          False,
                "proposal_id": proposal_id,
                "agent_id":    agent_id,
                "error":       str(exc),
            }
            with self._lock:
                self._proposals[proposal_id] = record
            return record

        record = {
            "ok":               plan.get("ok", False) and validation.get("valid", False),
            "proposal_id":      proposal_id,
            "agent_id":         agent_id,
            "agent_name":       agent["name"],
            "supervision_level": supervision_level,
            "intent":           plan.get("intent", ""),
            "plan":             plan,
            "plan_json":        json.dumps(plan, default=str),
            "validation":       validation,
            "supervision_result": supervision_result,
            "explanation":      expl.get("full_text", ""),
            "requires_approval": supervision_result["requires_approval"],
            "execution_authorized": supervision_result["execution_authorized"],
            "submitted_at":     time.time(),
        }
        with self._lock:
            self._proposals[proposal_id] = record
        return record

    def _apply_supervision(
        self,
        supervision_level: str,
        plan:              Dict[str, Any],
        validation:        Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply supervision policy.  Returns a supervision_result dict."""
        valid       = validation.get("valid", False)
        risk_level  = validation.get("risk_level", "high")
        plan_req    = plan.get("requires_approval", False)

        if supervision_level == "advisory":
            return {
                "allowed":              valid,
                "execution_authorized": False,
                "requires_approval":    True,
                "reason":               "advisory agents never authorize execution",
            }

        if supervision_level == "strict":
            return {
                "allowed":              valid,
                "execution_authorized": False,
                "requires_approval":    True,
                "reason":               "strict supervision always requires human approval",
            }

        # standard
        if not valid:
            return {
                "allowed":              False,
                "execution_authorized": False,
                "requires_approval":    True,
                "reason":               "validation failed",
            }
        if risk_level == "high" or plan_req:
            return {
                "allowed":              True,
                "execution_authorized": False,
                "requires_approval":    True,
                "reason":               "high-risk plan requires human approval",
            }
        return {
            "allowed":              True,
            "execution_authorized": True,
            "requires_approval":    False,
            "reason":               "safe plan auto-authorized by standard supervision",
        }

    # ------------------------------------------------------------------
    # Proposal query
    # ------------------------------------------------------------------

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            p = self._proposals.get(proposal_id)
            return dict(p) if p else None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_level: Dict[str, int] = {}
            for a in self._agents.values():
                lvl = a["supervision_level"]
                by_level[lvl] = by_level.get(lvl, 0) + 1
            return {
                "total_agents":    len(self._agents),
                "total_proposals": len(self._proposals),
                "by_supervision":  by_level,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AgentRuntime] = None
_LOCK = threading.Lock()


def get_agent_runtime() -> AgentRuntime:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = AgentRuntime()
        return _INSTANCE


def reset_agent_runtime_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
