from pydantic import BaseModel


class ServiceInfo(BaseModel):
    name: str
    environment: str
    docs_path: str
    architecture_doc: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    face_droop_processor_enabled: bool


class BootstrapSummary(BaseModel):
    provider: str
    video_fps: int
    processor_fps: int
    enabled_processors: list[str]
    notes: list[str]


class SessionCreateResponse(BaseModel):
    session_id: str
    provider: str
    status: str
    vision_agent_provider_ready: bool
    vision_agent_transport_ready: bool
    missing_configuration: list[str]


class SessionStatusResponse(BaseModel):
    session_id: str
    provider: str
    status: str
    created_at: str
    last_event_at: str
    connected_clients: int
    video_frames: int
    audio_chunks: int
    binary_messages: int
    text_messages: int
    last_event_type: str | None
    recent_events: list[str]
