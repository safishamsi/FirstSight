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
    speech_pipeline: Literal["realtime", "fast_whisper_pipeline"] = "fast_whisper_pipeline"
    realtime_video_fps: int = 2
    processor_fps: int = 2
    enable_face_droop_processor: bool = False
    stream_api_key: str = ""
    stream_api_secret: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-3-flash-preview"
    fast_whisper_model_size: str = "base"
    fast_whisper_language: str = "en"
    fast_whisper_device: Literal["cpu", "cuda"] = "cpu"
    pipeline_turn_delay_ms: int = 1200
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "VR6AewLTigWG4xSOukaG"
    elevenlabs_model_id: str = "eleven_multilingual_v2"

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
