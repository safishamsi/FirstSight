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


session_manager = SessionManager()

