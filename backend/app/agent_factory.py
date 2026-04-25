from collections.abc import Sequence

from .config import Settings, get_settings


def _build_processors(settings: Settings) -> list[object]:
    processors: list[object] = []
    if settings.enable_face_droop_processor:
        from .processors.face_droop import FaceDroopProcessor

        processors.append(FaceDroopProcessor(fps=settings.processor_fps))
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
    from vision_agents.plugins import fast_whisper

    return fast_whisper.STT(
        model_size=settings.fast_whisper_model_size,
        language=settings.fast_whisper_language,
        device=settings.fast_whisper_device,
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

    processors: Sequence[object] = _build_processors(active_settings)
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
