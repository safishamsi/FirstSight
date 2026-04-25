from fastapi import APIRouter, Depends

from .config import Settings, get_settings
from .schemas import BootstrapSummary, HealthResponse, ServiceInfo

router = APIRouter()


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
        ],
    )

