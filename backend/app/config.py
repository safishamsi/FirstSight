from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    realtime_provider: Literal["gemini", "openai"] = "gemini"
    realtime_video_fps: int = 2
    processor_fps: int = 2
    enable_face_droop_processor: bool = False

    agent_name: str = "DroopDetection Agent"
    agent_user_id: str = "agent"
    agent_instructions: str = (
        "You are a guidance-only first-aid assistant. Use visible evidence, "
        "processor signals, and retrieved guidance to help the wearer assess "
        "urgent situations. Never pretend to place calls or take external "
        "actions on the user's behalf."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

