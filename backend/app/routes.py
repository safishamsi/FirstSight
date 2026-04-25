import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from .config import Settings, get_settings
from .schemas import (
    BootstrapSummary,
    HealthResponse,
    ServiceInfo,
    SessionCreateResponse,
    SessionStatusResponse,
)
from .session_manager import session_manager

router = APIRouter()


def _missing_configuration(settings: Settings) -> list[str]:
    missing: list[str] = []
    if settings.realtime_provider == "gemini" and not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if settings.realtime_provider == "openai" and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.stream_api_key:
        missing.append("STREAM_API_KEY")
    if not settings.stream_api_secret:
        missing.append("STREAM_API_SECRET")
    return missing


@router.get("/", response_model=ServiceInfo)
def read_root(settings: Settings = Depends(get_settings)) -> ServiceInfo:
    return ServiceInfo(
        name="droopdetection-backend",
        environment=settings.app_env,
        docs_path="/docs",
        architecture_doc="../ARCHITECTURE.md",
    )


@router.get("/health", response_model=HealthResponse)
def read_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        provider=settings.realtime_provider,
        face_droop_processor_enabled=settings.enable_face_droop_processor,
    )


@router.get("/bootstrap", response_model=BootstrapSummary)
def read_bootstrap(settings: Settings = Depends(get_settings)) -> BootstrapSummary:
    enabled_processors: list[str] = []
    if settings.enable_face_droop_processor:
        enabled_processors.append("face_droop")

    return BootstrapSummary(
        provider=settings.realtime_provider,
        video_fps=settings.realtime_video_fps,
        processor_fps=settings.processor_fps,
        enabled_processors=enabled_processors,
        notes=[
            "FastAPI is intentionally bootable without a live Vision Agents session.",
            "Use app.examples.basic_video_agent as the minimal realtime starting point.",
            "The viewer/dashboard contract will be added on top of this base scaffold.",
            "The /sessions endpoints currently provide app-to-backend ingest only.",
        ],
    )


@router.post("/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(settings: Settings = Depends(get_settings)) -> SessionCreateResponse:
    record = session_manager.create(provider=settings.realtime_provider)
    missing = _missing_configuration(settings)
    return SessionCreateResponse(
        session_id=record.session_id,
        provider=record.provider,
        status=record.status,
        vision_agent_provider_ready=(
            ("GEMINI_API_KEY" not in missing) if settings.realtime_provider == "gemini" else ("OPENAI_API_KEY" not in missing)
        ),
        vision_agent_transport_ready=("STREAM_API_KEY" not in missing and "STREAM_API_SECRET" not in missing),
        missing_configuration=missing,
    )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
def read_session(session_id: str) -> SessionStatusResponse:
    record = session_manager.get(session_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionStatusResponse(**record.to_dict())


@router.websocket("/sessions/{session_id}/stream")
async def stream_session(websocket: WebSocket, session_id: str) -> None:
    record = session_manager.get(session_id)
    if record is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unknown session")
        return

    await websocket.accept()
    session_manager.connect(session_id)
    await websocket.send_json(
        {
            "type": "session_ready",
            "session_id": session_id,
            "provider": record.provider,
            "note": "Ingress is live. Vision Agents forwarding is not wired yet.",
        }
    )

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("text") is not None:
                payload = json.loads(message["text"])
                event_type = str(payload.get("type", "message"))
                updated = session_manager.record_text_event(session_id, event_type)
                if updated is None:
                    break
                await websocket.send_json(
                    {
                        "type": "ack",
                        "received_type": event_type,
                        "session_id": session_id,
                        "video_frames": updated.video_frames,
                        "audio_chunks": updated.audio_chunks,
                    }
                )
                continue

            if message.get("bytes") is not None:
                updated = session_manager.record_binary_event(session_id)
                if updated is None:
                    break
                await websocket.send_json(
                    {
                        "type": "ack",
                        "received_type": "binary_frame",
                        "session_id": session_id,
                        "binary_messages": updated.binary_messages,
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        session_manager.disconnect(session_id)

