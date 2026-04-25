import base64
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from .config import Settings, get_settings
from .schemas import (
    BootstrapSummary,
    HealthResponse,
    SessionCreateRequest,
    SessionRuntimeConfig,
    ServiceInfo,
    SessionCreateResponse,
    SessionStatusResponse,
)
from .realtime_bridge import vision_bridge_manager
from .session_manager import session_manager
from .vision_runtime import vision_runtime

router = APIRouter()
logger = logging.getLogger(__name__)


def _should_log_media_count(count: int) -> bool:
    return count in {1, 2, 5, 10} or count % 25 == 0


def _extract_client_text(payload: dict[str, object]) -> str | None:
    client_content = payload.get("clientContent")
    if not isinstance(client_content, dict):
        return None

    turns = client_content.get("turns")
    if not isinstance(turns, list):
        return None

    texts: list[str] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        parts = turn.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())

    if not texts:
        return None
    return " ".join(texts)


def _extract_realtime_blob(
    payload: dict[str, object],
    *,
    key: str,
) -> bytes | None:
    realtime_input = payload.get("realtimeInput")
    if not isinstance(realtime_input, dict):
        return None
    blob = realtime_input.get(key)
    if not isinstance(blob, dict):
        return None
    data = blob.get("data")
    if not isinstance(data, str) or not data:
        return None
    try:
        return base64.b64decode(data)
    except Exception:
        return None


def _parse_stream_payload(payload: dict[str, object]) -> tuple[str, str | None, bytes | None]:
    if "setup" in payload:
        return "setup", None, None

    realtime_input = payload.get("realtimeInput")
    if isinstance(realtime_input, dict):
        audio = realtime_input.get("audio")
        if isinstance(audio, dict):
            return "audio_chunk", None, _extract_realtime_blob(payload, key="audio")

        video = realtime_input.get("video")
        if isinstance(video, dict):
            return "video_frame", None, _extract_realtime_blob(payload, key="video")

    client_text = _extract_client_text(payload)
    if client_text is not None:
        return "text_message", client_text, None

    event_type = payload.get("type")
    if isinstance(event_type, str) and event_type:
        return event_type, None, None

    return "message", None, None


def _welcome_message() -> str:
    return (
        "Vision agent backend connected. Streaming is live. "
        "Show me the patient and I will provide step by step first aid guidance."
    )


def _stroke_demo_guidance() -> str:
    return (
        "Possible stroke check started. Look for face droop, arm weakness, and slurred speech. "
        "If symptoms are present, call emergency services immediately and keep the patient seated and monitored."
    )


def _missing_configuration(settings: Settings) -> list[str]:
    missing: list[str] = []
    if settings.realtime_provider == "gemini" and not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if settings.realtime_provider == "openai" and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if settings.speech_pipeline == "fast_whisper_pipeline" and not settings.gemini_api_key:
        if "GEMINI_API_KEY" not in missing:
            missing.append("GEMINI_API_KEY")
    if not settings.stream_api_key:
        missing.append("STREAM_API_KEY")
    if not settings.stream_api_secret:
        missing.append("STREAM_API_SECRET")
    return missing


def _runtime_config_overrides(runtime_config: SessionRuntimeConfig) -> dict[str, object]:
    overrides: dict[str, object] = {}
    if runtime_config.speech_pipeline is not None:
        overrides["speech_pipeline"] = runtime_config.speech_pipeline
    if runtime_config.gemini_llm_model is not None:
        overrides["gemini_llm_model"] = runtime_config.gemini_llm_model
    if runtime_config.fast_whisper_model_size is not None:
        overrides["fast_whisper_model_size"] = runtime_config.fast_whisper_model_size
    if runtime_config.fast_whisper_language is not None:
        overrides["fast_whisper_language"] = runtime_config.fast_whisper_language
    if runtime_config.fast_whisper_device is not None:
        overrides["fast_whisper_device"] = runtime_config.fast_whisper_device
    if runtime_config.pipeline_turn_delay_ms is not None:
        overrides["pipeline_turn_delay_ms"] = runtime_config.pipeline_turn_delay_ms
    if runtime_config.backend_tts_enabled is not None:
        overrides["backend_tts_enabled"] = runtime_config.backend_tts_enabled
    return overrides


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
            "POST /sessions now doubles as the Android backend-mode bootstrap endpoint.",
            "The /sessions websocket accepts both custom ingest events and Gemini-style setup/realtimeInput envelopes.",
        ],
    )


@router.post("/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreateRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> SessionCreateResponse:
    request = payload or SessionCreateRequest()
    effective_settings = settings.model_copy(
        update=_runtime_config_overrides(request.runtime_config),
    )
    record = session_manager.create(
        provider=effective_settings.realtime_provider,
        runtime_config=request.runtime_config.model_dump(exclude_none=True),
    )
    missing = _missing_configuration(effective_settings)
    bootstrap = None
    bootstrap_error: str | None = None
    logger.info(
        "create_session session_id=%s provider=%s user_id=%s call_type=%s start_agent_session=%s missing=%s",
        record.session_id,
        effective_settings.realtime_provider,
        request.user_id,
        request.call_type,
        request.start_agent_session,
        ",".join(missing) or "none",
    )

    if (
        request.start_agent_session
        and request.user_id
        and "STREAM_API_KEY" not in missing
        and "STREAM_API_SECRET" not in missing
        and (
            ("GEMINI_API_KEY" not in missing and effective_settings.realtime_provider == "gemini")
            or ("OPENAI_API_KEY" not in missing and effective_settings.realtime_provider == "openai")
        )
    ):
        try:
            bootstrap = await vision_runtime.bootstrap(
                effective_settings,
                user_id=request.user_id,
                user_name=request.user_name,
                call_id=request.call_id,
                call_type=request.call_type,
            )
            logger.info(
                "vision_runtime bootstrap started session_id=%s agent_session_id=%s call_id=%s call_type=%s",
                record.session_id,
                bootstrap.agent_session_id,
                bootstrap.call_id,
                bootstrap.call_type,
            )
        except Exception as exc:  # pragma: no cover - network/config failures are environment-specific
            bootstrap_error = str(exc)
            logger.exception(
                "vision_runtime bootstrap failed session_id=%s provider=%s",
                record.session_id,
                effective_settings.realtime_provider,
            )
    else:
        logger.info(
            "vision_runtime bootstrap skipped session_id=%s provider=%s reason=missing_transport_or_provider_config",
            record.session_id,
            effective_settings.realtime_provider,
        )

    session_manager.update_bootstrap(
        record.session_id,
        call_id=bootstrap.call_id if bootstrap else None,
        call_type=bootstrap.call_type if bootstrap else (request.call_type if request.user_id else None),
        agent_session_id=bootstrap.agent_session_id if bootstrap else None,
        stream_user_id=bootstrap.stream_user_id if bootstrap else request.user_id,
        vision_agent_started=bootstrap is not None,
        vision_agent_error=bootstrap_error,
    )

    return SessionCreateResponse(
        session_id=record.session_id,
        provider=record.provider,
        status=record.status,
        vision_agent_provider_ready=(
            ("GEMINI_API_KEY" not in missing) if settings.realtime_provider == "gemini" else ("OPENAI_API_KEY" not in missing)
        ),
        vision_agent_transport_ready=("STREAM_API_KEY" not in missing and "STREAM_API_SECRET" not in missing),
        missing_configuration=missing,
        call_id=bootstrap.call_id if bootstrap else None,
        call_type=bootstrap.call_type if bootstrap else None,
        agent_session_id=bootstrap.agent_session_id if bootstrap else None,
        stream_api_key=bootstrap.stream_api_key if bootstrap else None,
        stream_user_id=bootstrap.stream_user_id if bootstrap else request.user_id,
        stream_user_token=bootstrap.stream_user_token if bootstrap else None,
        stream_call_cid=bootstrap.call_cid if bootstrap else None,
        vision_agent_started=bootstrap is not None,
        vision_agent_error=bootstrap_error,
    )


@router.get("/sessions", response_model=list[SessionStatusResponse])
def list_sessions() -> list[SessionStatusResponse]:
    return [SessionStatusResponse(**record.to_dict()) for record in session_manager.list_records()]


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

    settings = get_settings().model_copy(update=record.runtime_config)
    missing = _missing_configuration(settings)

    await websocket.accept()
    session_manager.connect(session_id)
    logger.info(
        "stream_session accepted session_id=%s provider=%s missing=%s",
        session_id,
        record.provider,
        ",".join(missing) or "none",
    )
    session_manager.append_debug_event(
        session_id,
        "stream_connected",
        {
            "provider": record.provider,
            "bridge_expected": (
                ("GEMINI_API_KEY" not in missing and settings.realtime_provider == "gemini")
                or ("OPENAI_API_KEY" not in missing and settings.realtime_provider == "openai")
            ),
        },
    )
    send_lock = asyncio.Lock()

    async def send_json_safe(payload: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_json(payload)

    bridge = None
    bridge_error: str | None = None
    if (
        ("GEMINI_API_KEY" not in missing and settings.realtime_provider == "gemini")
        or ("OPENAI_API_KEY" not in missing and settings.realtime_provider == "openai")
    ):
        try:
            bridge = await vision_bridge_manager.start(
                session_id=session_id,
                settings=settings,
                emit=send_json_safe,
            )
            logger.info(
                "realtime bridge started session_id=%s provider=%s",
                session_id,
                settings.realtime_provider,
            )
        except Exception as exc:  # pragma: no cover - network/provider-specific
            bridge_error = str(exc)
            logger.exception(
                "realtime bridge failed session_id=%s provider=%s",
                session_id,
                settings.realtime_provider,
            )
    else:
        logger.info(
            "realtime bridge skipped session_id=%s provider=%s reason=missing_provider_key",
            session_id,
            settings.realtime_provider,
        )

    await send_json_safe(
        {
            "type": "session_ready",
            "session_id": session_id,
            "provider": record.provider,
            "bridge_active": bridge is not None,
            "bridge_error": bridge_error,
            "note": (
                "Ingress is live and provider bridge is active."
                if bridge is not None
                else "Ingress is live. Falling back to local demo adapter because provider bridge is unavailable."
            ),
        }
    )

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("text") is not None:
                payload = json.loads(message["text"])
                event_type, client_text, blob_bytes = _parse_stream_payload(payload)

                if event_type == "setup":
                    updated = session_manager.record_text_event(session_id, event_type)
                    if updated is None:
                        break
                    logger.info(
                        "stream setup received session_id=%s bridge_active=%s",
                        session_id,
                        bridge is not None,
                    )
                    session_manager.append_debug_event(
                        session_id,
                        "setup",
                        {"bridge_active": bridge is not None},
                    )
                    await send_json_safe(
                        {
                            "setupComplete": {
                                "session_id": session_id,
                                "provider": record.provider,
                                "vision_agent_started": updated.vision_agent_started,
                            }
                        }
                    )
                    if bridge is not None:
                        await bridge.send_initial_prompt()
                    elif not updated.welcome_sent:
                        session_manager.mark_welcome_sent(session_id)
                        await send_json_safe(
                            {
                                "serverContent": {
                                    "outputTranscription": {"text": _welcome_message()},
                                    "turnComplete": True,
                                }
                            }
                        )
                    continue

                updated = session_manager.record_text_event(session_id, event_type)
                if updated is None:
                    break

                if bridge is not None and event_type == "audio_chunk" and blob_bytes:
                    if _should_log_media_count(updated.audio_chunks):
                        logger.info(
                            "stream audio forwarded session_id=%s chunk_count=%s bytes=%s",
                            session_id,
                            updated.audio_chunks,
                            len(blob_bytes),
                        )
                    await bridge.send_audio(blob_bytes)
                elif bridge is not None and event_type == "video_frame" and blob_bytes:
                    if _should_log_media_count(updated.video_frames):
                        logger.info(
                            "stream video forwarded session_id=%s frame_count=%s bytes=%s",
                            session_id,
                            updated.video_frames,
                            len(blob_bytes),
                        )
                    await bridge.send_video_frame(blob_bytes)
                elif bridge is not None and event_type == "text_message" and client_text:
                    logger.info(
                        "stream text forwarded session_id=%s chars=%s text=%r",
                        session_id,
                        len(client_text),
                        client_text[:200],
                    )
                    session_manager.append_debug_event(
                        session_id,
                        "client_text",
                        {"text": client_text},
                    )
                    await bridge.send_text(client_text)
                elif event_type == "text_message" and client_text:
                    logger.info(
                        "stream text received without bridge session_id=%s chars=%s text=%r",
                        session_id,
                        len(client_text),
                        client_text[:200],
                    )

                if bridge is None and event_type == "video_frame" and not updated.demo_guidance_sent:
                    session_manager.mark_demo_guidance_sent(session_id)
                    await send_json_safe(
                        {
                            "serverContent": {
                                "outputTranscription": {"text": _stroke_demo_guidance()},
                                "turnComplete": True,
                            }
                        }
                    )

                if bridge is None and event_type == "text_message" and client_text:
                    await send_json_safe(
                        {
                            "serverContent": {
                                "inputTranscription": {"text": client_text},
                                "outputTranscription": {
                                    "text": f"Backend adapter received: {client_text}"
                                },
                                "turnComplete": True,
                            }
                        }
                    )

                await send_json_safe(
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
                if _should_log_media_count(updated.binary_messages):
                    logger.info(
                        "binary frame received session_id=%s binary_count=%s bytes=%s",
                        session_id,
                        updated.binary_messages,
                        len(message["bytes"]),
                    )
                await send_json_safe(
                    {
                        "type": "ack",
                        "received_type": "binary_frame",
                        "session_id": session_id,
                        "binary_messages": updated.binary_messages,
                    }
                )
    except WebSocketDisconnect:
        logger.info("stream_session disconnected session_id=%s", session_id)
    finally:
        session_manager.disconnect(session_id)
        session_manager.append_debug_event(session_id, "stream_closed", {})
        await vision_bridge_manager.close(session_id)
        logger.info("stream_session closed session_id=%s", session_id)
