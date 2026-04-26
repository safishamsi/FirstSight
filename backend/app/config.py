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
    realtime_video_fps: int = 10
    processor_fps: int = 10
    enable_face_droop_processor: bool = False
    enable_pose_processor: bool = False
    facial_droop_api_url: str = ""
    facial_droop_timeout_s: float = 8.0
    vision_tool_base_url: str = ""
    vision_tool_auth_token: str = ""
    vision_tool_timeout_s: float = 15.0
    pose_model_path: str = "yolo11n-pose.pt"
    pose_conf_threshold: float = 0.5
    pose_device: Literal["cpu", "cuda"] = "cpu"
    pose_enable_hand_tracking: bool = True
    stream_api_key: str = ""
    stream_api_secret: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-3-flash-preview"
    fast_whisper_model_size: str = "base"
    fast_whisper_language: str = "en"
    fast_whisper_device: Literal["cpu", "cuda"] = "cpu"
    fast_whisper_min_buffer_ms: int = 400
    fast_whisper_process_interval_ms: int = 800
    fast_whisper_max_buffer_ms: int = 3000
    pipeline_turn_delay_ms: int = 1200
    backend_tts_enabled: bool = True
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "VR6AewLTigWG4xSOukaG"
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    agent_name: str = "DroopDetection Agent"
    agent_user_id: str = "agent"
    agent_instructions: str = (
        "You are a calm first-aid playbook assistant. "
        "Always anchor on the active checklist step before answering. "
        "Prefer one concrete next action over general commentary. "
        "Use tool results, visible evidence, processor signals, and retrieved guidance together. "
        "If the current step is unclear, ask for one specific camera adjustment or confirmation. "
        "Do not narrate the whole protocol unless asked. "
        "Never pretend to place calls or take external actions on the user's behalf."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
