from typing import Literal

from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    name: str
    environment: str
    docs_path: str
    architecture_doc: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    pose_processor_enabled: bool
    facial_droop_api_configured: bool


class BootstrapSummary(BaseModel):
    provider: str
    video_fps: int
    processor_fps: int
    enabled_processors: list[str]
    notes: list[str]


class SessionRuntimeConfig(BaseModel):
    speech_pipeline: str | None = None
    enable_pose_processor: bool | None = None
    gemini_llm_model: str | None = None
    fast_whisper_model_size: str | None = None
    fast_whisper_language: str | None = None
    fast_whisper_device: str | None = None
    pipeline_turn_delay_ms: int | None = None
    backend_tts_enabled: bool | None = None


class ChecklistItemResponse(BaseModel):
    id: str
    label: str
    kind: str
    status: str
    source_protocol_id: str | None = None


class ChecklistTemplateItemResponse(BaseModel):
    id: str
    label: str
    kind: str
    required: bool


class ProtocolHitResponse(BaseModel):
    protocol_id: str
    title: str
    score: float
    matched_excerpt: str
    severity: str


class ProtocolSearchResultResponse(ProtocolHitResponse):
    summary: str
    incident_type: str | None = None


class IncidentStateResponse(BaseModel):
    incident_type: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    active_protocol_id: str | None = None
    active_protocol_title: str | None = None
    active_protocol_summary: str | None = None
    active_protocol_manual: str | None = None
    active_checklist_id: str | None = None
    manual_hits: list[ProtocolHitResponse] = Field(default_factory=list)
    has_user_explicitly_asked: bool = False
    last_agent_prompted_step: str | None = None


class ProtocolSummaryResponse(BaseModel):
    id: str
    title: str
    summary: str
    severity: str
    incident_type: str | None = None
    search_terms: list[str]
    activation_triggers: list[str]
    checklist_count: int


class ProtocolDetailResponse(BaseModel):
    id: str
    title: str
    summary: str
    severity: str
    incident_type: str | None = None
    search_terms: list[str]
    activation_triggers: list[str]
    manual_markdown: str
    checklist_template: list[ChecklistTemplateItemResponse]


class GuideSearchRequest(BaseModel):
    query: str
    incident_type: str | None = None
    auto_activate: bool = False


class GuideSearchResponse(BaseModel):
    query: str
    activated_protocol_id: str | None = None
    hits: list[ProtocolHitResponse] = Field(default_factory=list)
    active_checklist: list[ChecklistItemResponse] = Field(default_factory=list)
    incident_state: IncidentStateResponse


class ChecklistSetRequest(BaseModel):
    protocol_id: str
    matched_query: str | None = None


class ChecklistStatusRequest(BaseModel):
    status: str


class SpatialPointResponse(BaseModel):
    y: float
    x: float


class SpatialBoxResponse(BaseModel):
    ymin: float
    xmin: float
    ymax: float
    xmax: float


class SpatialOverlayResponse(BaseModel):
    id: str
    kind: Literal["point", "box", "trajectory", "polygon", "text"]
    mode: Literal["default", "expert_scope"] | None = None
    label: str | None = None
    color: str | None = None
    confidence: float | None = None
    source: str | None = None
    prompt: str | None = None
    text: str | None = None
    group_id: str | None = None
    sequence_index: int | None = None
    emphasis: Literal["normal", "active", "ghost"] | None = None
    expires_at: str | None = None
    point: SpatialPointResponse | None = None
    box: SpatialBoxResponse | None = None
    points: list[SpatialPointResponse] = Field(default_factory=list)


class SpatialOverlaySetRequest(BaseModel):
    overlays: list[SpatialOverlayResponse] = Field(default_factory=list)
    context_summary: str | None = None
    replace: bool = True
    ttl_ms: int | None = Field(default=None, ge=1, le=60000)
    mode: Literal["default", "expert_scope"] = "default"


class FacialDroopToolResponse(BaseModel):
    session_id: str
    source: str
    droop_probability: float | None
    is_drooping: bool | None
    severity: str | None
    confidence: float | None
    face_detected: bool
    asymmetry_score: float | None = None
    mouth_asymmetry: float | None = None
    eye_asymmetry: float | None = None
    brow_asymmetry: float | None = None


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
    preview_frame_available: bool = False
    preview_frame_updated_at: str | None = None
    spatial_context_summary: str | None = None
    spatial_overlays: list[SpatialOverlayResponse] = Field(default_factory=list)
    call_id: str | None = None
    call_type: str | None = None
    agent_session_id: str | None = None
    stream_user_id: str | None = None
    vision_agent_started: bool = False
    vision_agent_error: str | None = None
    runtime_config: SessionRuntimeConfig = Field(default_factory=SessionRuntimeConfig)
    incident_state: IncidentStateResponse = Field(default_factory=IncidentStateResponse)
    active_checklist: list[ChecklistItemResponse] = Field(default_factory=list)
    protocol_hits: list[ProtocolHitResponse] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    user_id: str | None = None
    user_name: str | None = None
    call_id: str | None = None
    call_type: str = "default"
    start_agent_session: bool = True
    runtime_config: SessionRuntimeConfig = Field(default_factory=SessionRuntimeConfig)
