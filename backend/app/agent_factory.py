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

        return openai.Realtime(fps=settings.realtime_video_fps)

    from vision_agents.plugins import gemini

    return gemini.Realtime(fps=settings.realtime_video_fps)


def build_agent(settings: Settings | None = None) -> object:
    active_settings = settings or get_settings()

    from vision_agents.core import Agent, User
    from vision_agents.plugins import getstream

    llm = build_realtime_llm(active_settings)
    processors: Sequence[object] = _build_processors(active_settings)

    return Agent(
        edge=getstream.Edge(),
        agent_user=User(name=active_settings.agent_name, id=active_settings.agent_user_id),
        instructions=active_settings.agent_instructions,
        llm=llm,
        processors=list(processors),
    )

