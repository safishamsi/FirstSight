from pydantic import BaseModel, Field


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


class SessionRuntimeConfig(BaseModel):
    speech_pipeline: str | None = None
    gemini_llm_model: str | None = None
    fast_whisper_model_size: str | None = None
    fast_whisper_language: str | None = None
    fast_whisper_device: str | None = None
    pipeline_turn_delay_ms: int | None = None
    backend_tts_enabled: bool | None = None


class SessionCreateResponse(BaseModel):
    session_id: str
    provider: str
    status: str
    vision_agent_provider_ready: bool
    vision_agent_transport_ready: bool
    missing_configuration: list[str]
    call_id: str | None = None
    call_type: str | None = None
    agent_session_id: str | None = None
    stream_api_key: str | None = None
    stream_user_id: str | None = None
    stream_user_token: str | None = None
    stream_call_cid: str | None = None
    vision_agent_started: bool = False
    vision_agent_error: str | None = None


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
    latest_user_transcript: str = ""
    latest_assistant_transcript: str = ""
    transcript_turns: list[dict[str, str]] = Field(default_factory=list)
    processor_signals: dict[str, dict[str, object]] = Field(default_factory=dict)
    debug_events: list[dict[str, object]] = Field(default_factory=list)
    call_id: str | None = None
    call_type: str | None = None
    agent_session_id: str | None = None
    stream_user_id: str | None = None
    vision_agent_started: bool = False
    vision_agent_error: str | None = None
    runtime_config: SessionRuntimeConfig = Field(default_factory=SessionRuntimeConfig)


class SessionCreateRequest(BaseModel):
    user_id: str | None = None
    user_name: str | None = None
    call_id: str | None = None
    call_type: str = "default"
    start_agent_session: bool = True
    runtime_config: SessionRuntimeConfig = Field(default_factory=SessionRuntimeConfig)
