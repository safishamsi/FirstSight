from pydantic import BaseModel


class ServiceInfo(BaseModel):
    name: str
    environment: str
    docs_path: str
    architecture_doc: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    face_droop_processor_enabled: bool


class BootstrapSummary(BaseModel):
    provider: str
    video_fps: int
    processor_fps: int
    enabled_processors: list[str]
    notes: list[str]

