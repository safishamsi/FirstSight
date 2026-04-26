from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from .incident_state import ChecklistItem, IncidentState, ProtocolHit
from .protocols.loader import ProtocolPack


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class ChecklistItemNotFoundError(LookupError):
    pass


class ChecklistAdvanceNotAvailableError(LookupError):
    pass


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    provider: str
    created_at: str
    last_event_at: str
    call_id: str | None = None
    call_type: str | None = None
    agent_session_id: str | None = None
    stream_user_id: str | None = None
    runtime_config: dict[str, object] = field(default_factory=dict)
    vision_agent_started: bool = False
    vision_agent_error: str | None = None
    welcome_sent: bool = False
    demo_guidance_sent: bool = False
    status: str = "created"
    connected_clients: int = 0
    video_frames: int = 0
    audio_chunks: int = 0
    binary_messages: int = 0
    text_messages: int = 0
    last_event_type: str | None = None
    recent_events: deque[str] = field(default_factory=lambda: deque(maxlen=10))
    latest_user_transcript: str = ""
    latest_assistant_transcript: str = ""
    transcript_turns: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=6))
    processor_signals: dict[str, dict[str, object]] = field(default_factory=dict)
    debug_events: deque[dict[str, object]] = field(default_factory=lambda: deque(maxlen=40))
    latest_preview_frame: bytes | None = None
    latest_preview_mime_type: str = "image/jpeg"
    latest_preview_updated_at: str | None = None
    spatial_context_summary: str | None = None
    spatial_overlays: list[dict[str, object]] = field(default_factory=list)
    tool_results: deque[dict[str, object]] = field(default_factory=lambda: deque(maxlen=12))
    incident_state: IncidentState = field(default_factory=IncidentState)
    active_checklist: list[ChecklistItem] = field(default_factory=list)
    protocol_hits: list[ProtocolHit] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "created_at": self.created_at,
            "last_event_at": self.last_event_at,
            "call_id": self.call_id,
            "call_type": self.call_type,
            "agent_session_id": self.agent_session_id,
            "stream_user_id": self.stream_user_id,
            "runtime_config": dict(self.runtime_config),
            "vision_agent_started": self.vision_agent_started,
            "vision_agent_error": self.vision_agent_error,
            "welcome_sent": self.welcome_sent,
            "demo_guidance_sent": self.demo_guidance_sent,
            "status": self.status,
            "connected_clients": self.connected_clients,
            "video_frames": self.video_frames,
            "audio_chunks": self.audio_chunks,
            "binary_messages": self.binary_messages,
            "text_messages": self.text_messages,
            "last_event_type": self.last_event_type,
            "recent_events": list(self.recent_events),
            "latest_user_transcript": self.latest_user_transcript,
            "latest_assistant_transcript": self.latest_assistant_transcript,
            "transcript_turns": list(self.transcript_turns),
            "processor_signals": dict(self.processor_signals),
            "debug_events": list(self.debug_events),
            "preview_frame_available": self.latest_preview_frame is not None,
            "preview_frame_updated_at": self.latest_preview_updated_at,
            "spatial_context_summary": self.spatial_context_summary,
            "spatial_overlays": list(self.spatial_overlays),
            "tool_results": list(self.tool_results),
            "incident_state": self.incident_state.to_dict(),
            "active_checklist": [item.to_dict() for item in self.active_checklist],
            "protocol_hits": [hit.to_dict() for hit in self.protocol_hits],
        }


class SessionManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, SessionRecord] = {}

    def create(self, provider: str, runtime_config: dict[str, object] | None = None) -> SessionRecord:
        session_id = uuid4().hex
        timestamp = utc_now_iso()
        record = SessionRecord(
            session_id=session_id,
            provider=provider,
            created_at=timestamp,
            last_event_at=timestamp,
            runtime_config=runtime_config or {},
        )
        with self._lock:
            self._sessions[session_id] = record
        return record

    def update_bootstrap(
        self,
        session_id: str,
        *,
        call_id: str | None,
        call_type: str | None,
        agent_session_id: str | None,
        stream_user_id: str | None,
        vision_agent_started: bool,
        vision_agent_error: str | None,
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.call_id = call_id
            record.call_type = call_type
            record.agent_session_id = agent_session_id
            record.stream_user_id = stream_user_id
            record.vision_agent_started = vision_agent_started
            record.vision_agent_error = vision_agent_error
            record.last_event_at = utc_now_iso()
            return record

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is not None:
                self._prune_expired_spatial_overlays(record)
            return record

    def list_ids(self) -> Iterable[str]:
        with self._lock:
            return list(self._sessions)

    def list_records(self) -> list[SessionRecord]:
        with self._lock:
            for record in self._sessions.values():
                self._prune_expired_spatial_overlays(record)
            return sorted(
                self._sessions.values(),
                key=lambda record: record.last_event_at,
                reverse=True,
            )

    def connect(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.connected_clients += 1
            record.status = "streaming"
            record.last_event_at = utc_now_iso()
            return record

    def disconnect(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.connected_clients = max(0, record.connected_clients - 1)
            if record.connected_clients == 0:
                record.status = "idle"
            record.last_event_at = utc_now_iso()
            return record

    def record_text_event(self, session_id: str, event_type: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.text_messages += 1
            record.last_event_type = event_type
            record.last_event_at = utc_now_iso()
            record.recent_events.append(event_type)
            if event_type == "video_frame":
                record.video_frames += 1
            elif event_type == "audio_chunk":
                record.audio_chunks += 1
            return record

    def record_binary_event(self, session_id: str, event_type: str = "binary_frame") -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.binary_messages += 1
            record.last_event_type = event_type
            record.last_event_at = utc_now_iso()
            record.recent_events.append(event_type)
            return record

    def mark_welcome_sent(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.welcome_sent = True
            record.last_event_at = utc_now_iso()
            return record

    def mark_demo_guidance_sent(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.demo_guidance_sent = True
            record.last_event_at = utc_now_iso()
            return record

    def append_debug_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.debug_events.append(
                {
                    "ts": utc_now_iso(),
                    "type": event_type,
                    "payload": payload,
                }
            )
            record.last_event_at = utc_now_iso()
            return record

    def update_input_transcript(self, session_id: str, text: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.latest_user_transcript += text
            record.last_event_at = utc_now_iso()
            return record

    def update_output_transcript(self, session_id: str, text: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.latest_assistant_transcript += text
            record.last_event_at = utc_now_iso()
            return record

    def complete_turn(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            user_text = record.latest_user_transcript.strip()
            assistant_text = record.latest_assistant_transcript.strip()
            if user_text or assistant_text:
                record.transcript_turns.append(
                    {
                        "user_text": user_text,
                        "assistant_text": assistant_text,
                    }
                )
            record.latest_user_transcript = ""
            record.latest_assistant_transcript = ""
            record.last_event_at = utc_now_iso()
            return record

    def update_processor_signal(
        self,
        session_id: str,
        processor_name: str,
        payload: dict[str, object],
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.processor_signals[processor_name] = payload
            record.last_event_at = utc_now_iso()
            return record

    def update_preview_frame(
        self,
        session_id: str,
        frame_bytes: bytes,
        *,
        mime_type: str = "image/jpeg",
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.latest_preview_frame = frame_bytes
            record.latest_preview_mime_type = mime_type
            record.latest_preview_updated_at = utc_now_iso()
            record.last_event_at = utc_now_iso()
            return record

    def set_spatial_overlays(
        self,
        session_id: str,
        overlays: list[dict[str, object]],
        *,
        context_summary: str | None = None,
        replace: bool = True,
        ttl_ms: int | None = None,
        mode: str = "default",
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            self._prune_expired_spatial_overlays(record)
            effective_ttl_ms = ttl_ms
            if mode == "expert_scope" and effective_ttl_ms is None:
                effective_ttl_ms = 5000
            expires_at = None
            if effective_ttl_ms is not None:
                expires_at = (
                    datetime.now(UTC) + timedelta(milliseconds=effective_ttl_ms)
                ).isoformat()
            normalized_overlays = [
                self._normalize_spatial_overlay(
                    overlay,
                    expires_at=expires_at,
                    mode=mode,
                )
                for overlay in overlays
            ]
            if replace:
                record.spatial_overlays = normalized_overlays
            else:
                record.spatial_overlays.extend(normalized_overlays)
            if context_summary is not None:
                record.spatial_context_summary = context_summary
            record.last_event_at = utc_now_iso()
            return record

    def clear_spatial_overlays(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.spatial_overlays = []
            record.spatial_context_summary = None
            record.last_event_at = utc_now_iso()
            return record

    def _normalize_spatial_overlay(
        self,
        overlay: dict[str, object],
        *,
        expires_at: str | None,
        mode: str,
    ) -> dict[str, object]:
        normalized = dict(overlay)
        normalized.setdefault("mode", mode)
        normalized.setdefault(
            "emphasis",
            "active" if mode == "expert_scope" else "normal",
        )
        if expires_at is not None and "expires_at" not in normalized:
            normalized["expires_at"] = expires_at
        return normalized

    def _prune_expired_spatial_overlays(self, record: SessionRecord) -> None:
        if not record.spatial_overlays:
            return
        now = datetime.now(UTC)
        kept: list[dict[str, object]] = []
        removed_any = False
        for overlay in record.spatial_overlays:
            expiry = _parse_iso_datetime(overlay.get("expires_at"))
            if expiry is not None and expiry <= now:
                removed_any = True
                continue
            kept.append(overlay)
        if removed_any:
            record.spatial_overlays = kept
            if not kept:
                record.spatial_context_summary = None

    def set_protocol_hits(self, session_id: str, hits: list[ProtocolHit]) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.protocol_hits = list(hits)
            record.incident_state.manual_hits = list(hits)
            record.last_event_at = utc_now_iso()
            return record

    def mark_user_requested_guidance(self, session_id: str, observation: str | None = None) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.incident_state.has_user_explicitly_asked = True
            if observation:
                record.incident_state.observations = _dedupe(
                    [*record.incident_state.observations, observation.strip()]
                )
            record.last_event_at = utc_now_iso()
            return record

    def set_checklist_from_protocol(
        self,
        session_id: str,
        protocol: ProtocolPack,
        *,
        matched_query: str | None = None,
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            checklist_items = [
                ChecklistItem(
                    id=item.id,
                    label=item.label,
                    kind=item.kind,
                    status="pending",
                    source_protocol_id=protocol.id,
                    agent_hint=item.agent_hint,
                    speak_before=item.speak_before,
                    tool_name=item.tool_name,
                    tool_query=item.tool_query,
                    tool_prompt=item.tool_prompt,
                    advance_when=item.advance_when,
                    requires_user_confirmation=item.requires_user_confirmation,
                )
                for item in protocol.checklist_template
            ]
            if checklist_items:
                checklist_items[0].status = "active"
            record.active_checklist = checklist_items
            record.incident_state.active_protocol_id = protocol.id
            record.incident_state.active_protocol_title = protocol.title
            record.incident_state.active_protocol_summary = protocol.summary
            record.incident_state.active_protocol_manual = protocol.manual_markdown
            record.incident_state.active_checklist_id = protocol.id
            record.incident_state.incident_type = protocol.incident_type or protocol.id
            record.incident_state.last_agent_prompted_step = (
                checklist_items[0].label if checklist_items else None
            )
            if matched_query:
                record.incident_state.observations = _dedupe(
                    [*record.incident_state.observations, f"user_reported: {matched_query.strip()}"]
                )
            record.last_event_at = utc_now_iso()
            return record

    def append_tool_result(
        self,
        session_id: str,
        *,
        step_id: str,
        tool_name: str,
        status: str,
        summary: str,
        payload: dict[str, object] | None = None,
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.tool_results.append(
                {
                    "ts": utc_now_iso(),
                    "step_id": step_id,
                    "tool_name": tool_name,
                    "status": status,
                    "summary": summary,
                    "payload": payload or {},
                }
            )
            record.incident_state.observations = _dedupe(
                [*record.incident_state.observations, f"{tool_name}:{status}: {summary}"]
            )
            record.last_event_at = utc_now_iso()
            return record

    def clear_active_checklist(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.active_checklist = []
            record.tool_results.clear()
            record.incident_state.active_protocol_id = None
            record.incident_state.active_protocol_title = None
            record.incident_state.active_protocol_summary = None
            record.incident_state.active_protocol_manual = None
            record.incident_state.active_checklist_id = None
            record.incident_state.last_agent_prompted_step = None
            record.spatial_context_summary = None
            record.spatial_overlays = []
            record.last_event_at = utc_now_iso()
            return record

    def get_active_checklist_item(self, session_id: str) -> ChecklistItem | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            for item in record.active_checklist:
                if item.status == "active":
                    return item
            for item in record.active_checklist:
                if item.status == "pending":
                    return item
            return None

    def activate_protocol(
        self,
        session_id: str,
        protocol: ProtocolPack,
        *,
        matched_query: str | None = None,
    ) -> SessionRecord | None:
        return self.set_checklist_from_protocol(
            session_id,
            protocol,
            matched_query=matched_query,
        )

    def complete_checklist_item(self, session_id: str, item_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            next_active: str | None = None
            found = False
            for item in record.active_checklist:
                if item.id == item_id:
                    item.status = "done"
                    found = True
                elif item.status == "active":
                    item.status = "pending"
            if not found:
                raise ChecklistItemNotFoundError(item_id)
            for item in record.active_checklist:
                if item.status == "pending":
                    item.status = "active"
                    next_active = item.label
                    break
            record.incident_state.last_agent_prompted_step = next_active
            record.last_event_at = utc_now_iso()
            return record

    def complete_next_checklist_item(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            next_item: ChecklistItem | None = None
            for item in record.active_checklist:
                if item.status == "active":
                    next_item = item
                    break
            if next_item is None:
                for item in record.active_checklist:
                    if item.status == "pending":
                        next_item = item
                        break
            if next_item is None:
                raise ChecklistAdvanceNotAvailableError(session_id)

            next_active: str | None = None
            for item in record.active_checklist:
                if item.id == next_item.id:
                    item.status = "done"
                elif item.status == "active":
                    item.status = "pending"

            for item in record.active_checklist:
                if item.status == "pending":
                    item.status = "active"
                    next_active = item.label
                    break

            record.incident_state.last_agent_prompted_step = next_active
            record.last_event_at = utc_now_iso()
            return record

    def update_checklist_item_status(
        self,
        session_id: str,
        item_id: str,
        status_value: str,
    ) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            found = False
            for item in record.active_checklist:
                if item.id == item_id:
                    item.status = status_value
                    if status_value == "active":
                        record.incident_state.last_agent_prompted_step = item.label
                    found = True
                    break
            if not found:
                raise ChecklistItemNotFoundError(item_id)
            record.last_event_at = utc_now_iso()
            return record

    def build_agent_context(self, session_id: str) -> str:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return ""
            context_parts: list[str] = []
            if record.incident_state.active_protocol_id:
                context_parts.append(
                    "Active protocol: "
                    f"{record.incident_state.active_protocol_title or record.incident_state.active_protocol_id}."
                )
            if record.incident_state.risk_flags:
                context_parts.append(
                    "Risk flags: " + ", ".join(record.incident_state.risk_flags) + "."
                )
            active_items = [
                item.label for item in record.active_checklist if item.status in {"active", "pending"}
            ][:3]
            if active_items:
                context_parts.append(
                    "Current checklist focus: " + " | ".join(active_items) + "."
                )
            active_step = next((item for item in record.active_checklist if item.status == "active"), None)
            if active_step is not None:
                context_parts.append(
                    "Active step details: "
                    f"kind={active_step.kind}; label={active_step.label}."
                )
                if active_step.speak_before:
                    context_parts.append(f"Speak before step: {active_step.speak_before}.")
                if active_step.agent_hint:
                    context_parts.append(f"Agent guidance: {active_step.agent_hint}.")
                if active_step.tool_name:
                    context_parts.append(f"Suggested tool: {active_step.tool_name}.")
                if active_step.tool_query:
                    context_parts.append(f"Tool query: {active_step.tool_query}.")
                if active_step.tool_prompt:
                    context_parts.append(f"Tool prompt: {active_step.tool_prompt}.")
                if active_step.advance_when:
                    context_parts.append(f"Advance when: {active_step.advance_when}.")
                if active_step.requires_user_confirmation:
                    context_parts.append("Wait for explicit human readiness before running the tool.")
            if record.tool_results:
                last_tool = record.tool_results[-1]
                context_parts.append(
                    "Latest tool result: "
                    f"{last_tool['tool_name']} status={last_tool['status']} summary={last_tool['summary']}."
                )
            if record.protocol_hits:
                context_parts.append(
                    "Retrieved guidance: "
                    + "; ".join(hit.title for hit in record.protocol_hits[:2])
                    + "."
                )
            if record.spatial_context_summary:
                context_parts.append(
                    f"Spatial tool context: {record.spatial_context_summary}."
                )
            return " ".join(context_parts)

    def build_step_guidance_prompt(self, session_id: str, *, reason: str) -> str:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return ""
            active_step = next((item for item in record.active_checklist if item.status == "active"), None)
            if active_step is None:
                return ""

            protocol_name = record.incident_state.active_protocol_title or record.incident_state.active_protocol_id or "playbook"
            prompt_parts = [
                f"A {reason} happened for the active first-aid playbook: {protocol_name}.",
                "Respond in one or two short sentences.",
                "Guide the wearer only on the current step, not the whole protocol.",
                f"Current step kind: {active_step.kind}.",
                f"Current step label: {active_step.label}.",
            ]
            if active_step.speak_before:
                prompt_parts.append(f"Preferred wording: {active_step.speak_before}.")
            if active_step.agent_hint:
                prompt_parts.append(f"Execution hint: {active_step.agent_hint}.")
            if active_step.tool_name:
                prompt_parts.append(f"If appropriate, mention that the next tool to run is {active_step.tool_name}.")
            if active_step.tool_prompt:
                prompt_parts.append(f"Tool goal: {active_step.tool_prompt}.")
            if active_step.advance_when:
                prompt_parts.append(f"Advance condition: {active_step.advance_when}.")
            if active_step.requires_user_confirmation:
                prompt_parts.append("Ask the wearer to confirm readiness before the tool runs.")
            return " ".join(prompt_parts)


session_manager = SessionManager()
