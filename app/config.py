from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_path: str = "model/droop_model.onnx"
    threshold_path: str = "checkpoints/threshold.json"
    image_size: int = 224
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_path_resolved(self) -> Path:
        return Path(self.model_path).resolve()

    def threshold_path_resolved(self) -> Path:
        return Path(self.threshold_path).resolve()


settings = Settings()
