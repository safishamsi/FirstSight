from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
        }


class SessionManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, SessionRecord] = {}

    def create(self, provider: str) -> SessionRecord:
        session_id = uuid4().hex
        timestamp = utc_now_iso()
        record = SessionRecord(
            session_id=session_id,
            provider=provider,
            created_at=timestamp,
            last_event_at=timestamp,
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
            return self._sessions.get(session_id)

    def list_ids(self) -> Iterable[str]:
        with self._lock:
            return list(self._sessions)

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


session_manager = SessionManager()
