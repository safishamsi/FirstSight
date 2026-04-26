from collections.abc import Sequence

from .config import Settings, get_settings


def _build_processors(settings: Settings, *, session_id: str | None = None) -> list[object]:
    processors: list[object] = []
    if settings.enable_pose_processor:
        from .processors.pose_overlay import PoseOverlayProcessor

        processors.append(
            PoseOverlayProcessor(
                session_id=session_id or "preview",
                model_path=settings.pose_model_path,
                conf_threshold=settings.pose_conf_threshold,
                device=settings.pose_device,
                fps=settings.processor_fps,
                enable_hand_tracking=settings.pose_enable_hand_tracking,
            )
        )
    return processors


def build_realtime_llm(settings: Settings) -> object:
    if settings.realtime_provider == "openai":
        from vision_agents.plugins import openai

        return openai.Realtime(
            fps=settings.realtime_video_fps,
            api_key=settings.openai_api_key or None,
        )

    from vision_agents.plugins import gemini

    return gemini.Realtime(
        fps=settings.realtime_video_fps,
        api_key=settings.gemini_api_key or None,
    )


def build_text_llm(settings: Settings) -> object:
    from vision_agents.plugins import gemini

    return gemini.LLM(
        model=settings.gemini_llm_model,
        api_key=settings.gemini_api_key or None,
    )


def build_stt(settings: Settings) -> object:
    from .stt.fast_whisper_live import FastWhisperLiveSTT

    return FastWhisperLiveSTT(
        model_size=settings.fast_whisper_model_size,
        language=settings.fast_whisper_language,
        device=settings.fast_whisper_device,
        min_buffer_duration_ms=settings.fast_whisper_min_buffer_ms,
        process_interval_ms=settings.fast_whisper_process_interval_ms,
        max_buffer_duration_ms=settings.fast_whisper_max_buffer_ms,
    )


def build_tts(settings: Settings) -> object | None:
    if not settings.backend_tts_enabled or not settings.elevenlabs_api_key:
        return None

    from vision_agents.plugins import elevenlabs

    return elevenlabs.TTS(
        api_key=settings.elevenlabs_api_key or None,
        voice_id=settings.elevenlabs_voice_id,
        model_id=settings.elevenlabs_model_id,
    )


def build_agent(settings: Settings | None = None) -> object:
    active_settings = settings or get_settings()

    from vision_agents.core import Agent, User
    from vision_agents.plugins import getstream

    from .agent_events import AgentCustomEventBridgeProcessor

    processors: Sequence[object] = [
        *_build_processors(active_settings),
        AgentCustomEventBridgeProcessor(),
    ]
    if active_settings.speech_pipeline == "fast_whisper_pipeline":
        return Agent(
            edge=getstream.Edge(),
            agent_user=User(name=active_settings.agent_name, id=active_settings.agent_user_id),
            instructions=active_settings.agent_instructions,
            llm=build_text_llm(active_settings),
            stt=build_stt(active_settings),
            tts=build_tts(active_settings),
            processors=list(processors),
        )

    return Agent(
        edge=getstream.Edge(),
        agent_user=User(name=active_settings.agent_name, id=active_settings.agent_user_id),
        instructions=active_settings.agent_instructions,
        llm=build_realtime_llm(active_settings),
        processors=list(processors),
    )
