from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ChecklistItem:
    id: str
    label: str
    kind: str = "action"
    status: str = "pending"
    source_protocol_id: str | None = None
    agent_hint: str | None = None
    speak_before: str | None = None
    tool_name: str | None = None
    tool_query: str | None = None
    tool_prompt: str | None = None
    advance_when: str | None = None
    requires_user_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "status": self.status,
            "source_protocol_id": self.source_protocol_id,
            "agent_hint": self.agent_hint,
            "speak_before": self.speak_before,
            "tool_name": self.tool_name,
            "tool_query": self.tool_query,
            "tool_prompt": self.tool_prompt,
            "advance_when": self.advance_when,
            "requires_user_confirmation": self.requires_user_confirmation,
        }


@dataclass(slots=True)
class ProtocolHit:
    protocol_id: str
    title: str
    score: float
    matched_excerpt: str
    severity: str

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol_id": self.protocol_id,
            "title": self.title,
            "score": self.score,
            "matched_excerpt": self.matched_excerpt,
            "severity": self.severity,
        }


@dataclass(slots=True)
class IncidentState:
    incident_type: str | None = None
    risk_flags: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    active_protocol_id: str | None = None
    active_protocol_title: str | None = None
    active_protocol_summary: str | None = None
    active_protocol_manual: str | None = None
    active_checklist_id: str | None = None
    manual_hits: list[ProtocolHit] = field(default_factory=list)
    has_user_explicitly_asked: bool = False
    last_agent_prompted_step: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "incident_type": self.incident_type,
            "risk_flags": list(self.risk_flags),
            "observations": list(self.observations),
            "active_protocol_id": self.active_protocol_id,
            "active_protocol_title": self.active_protocol_title,
            "active_protocol_summary": self.active_protocol_summary,
            "active_protocol_manual": self.active_protocol_manual,
            "active_checklist_id": self.active_checklist_id,
            "manual_hits": [hit.to_dict() for hit in self.manual_hits],
            "has_user_explicitly_asked": self.has_user_explicitly_asked,
            "last_agent_prompted_step": self.last_agent_prompted_step,
        }
