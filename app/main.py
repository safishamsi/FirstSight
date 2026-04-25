from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.config import settings
from app.inference import DroopModel
from app.schemas import HealthResponse, PredictResponse, ThresholdResponse, VideoResponse
from app.video import analyze_video_file

_model: DroopModel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    model_path = settings.model_path_resolved()
    threshold_path = settings.threshold_path_resolved()

    if not model_path.exists():
        raise RuntimeError(
            f"ONNX model not found at {model_path}. "
            "Run scripts/export_onnx.py first."
        )
    if not threshold_path.exists():
        raise RuntimeError(
            f"Threshold file not found at {threshold_path}. "
            "Run evaluate.py first."
        )

    _model = DroopModel(
        model_path=str(model_path),
        threshold_path=str(threshold_path),
        image_size=settings.image_size,
    )
    yield
    _model = None


app = FastAPI(
    title="Droop Detection API",
    description="Detects mouth droopiness from an uploaded image. "
                "Returns probability and severity — intended as a screening tool, not a diagnosis.",
    version="0.1.0",
    lifespan=lifespan,
)

# Logfire: auto-instruments all FastAPI requests with trace spans and structured logs.
# Set LOGFIRE_TOKEN env var (from logfire.pydantic.dev) to send to the cloud dashboard.
# Without a token, logs are emitted to stdout only.
logfire.configure(
    service_name="droop-detection",
    # Without LOGFIRE_TOKEN: logs to stdout only.
    # Set LOGFIRE_TOKEN env var to stream traces to logfire.pydantic.dev.
    send_to_logfire="if-token-present",
)
logfire.instrument_fastapi(app)


@app.post("/predict", response_model=PredictResponse)
async def predict(file: UploadFile = File(...)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=422, detail="Unsupported image type. Send JPEG or PNG.")

    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB).")

    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    with logfire.span(
        "droop_inference",
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=len(contents),
    ):
        result = _model.predict(contents)
        logfire.info(
            "prediction",
            face_detected=result["face_detected"],
            droop_probability=result["droop_probability"],
            is_drooping=result["is_drooping"],
            severity=result["severity"],
        )

    return PredictResponse(**result)


_VIDEO_TYPES = ("video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "application/octet-stream")


@app.post("/predict/video", response_model=VideoResponse)
async def predict_video(
    file: UploadFile = File(...),
    sample_fps: float = 6.0,
    max_frames: int = 90,
):
    """
    Analyze a video for mouth droopiness using temporal aggregation.

    Samples frames at `sample_fps`, runs per-frame inference, and returns a
    blended `droop_likelihood` score. Persistent droop across frames → high score.

    - **sample_fps**: frames per second to sample (default 6, max 30)
    - **max_frames**: cap on frames processed (default 90 = 15 s at 6 fps)
    """
    if file.content_type not in _VIDEO_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{file.content_type}'. Send MP4, MOV, AVI, or WebM.",
        )

    contents = await file.read()
    if len(contents) > 200 * 1024 * 1024:  # 200 MB
        raise HTTPException(status_code=413, detail="Video too large (max 200 MB).")

    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    sample_fps = min(max(sample_fps, 1.0), 30.0)
    max_frames = min(max(max_frames, 1), 300)

    with logfire.span(
        "video_inference",
        filename=file.filename,
        sample_fps=sample_fps,
        max_frames=max_frames,
        size_bytes=len(contents),
    ):
        result = analyze_video_file(contents, _model, sample_fps=sample_fps, max_frames=max_frames)
        logfire.info(
            "video_prediction",
            droop_likelihood=result.get("droop_likelihood"),
            fraction_frames_flagged=result.get("fraction_frames_flagged"),
            frames_analyzed=result.get("frames_analyzed"),
            is_drooping=result.get("is_drooping"),
        )

    return VideoResponse(**result)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model="efficientnet_b0_onnx",
        model_loaded=_model is not None,
    )


@app.get("/threshold", response_model=ThresholdResponse)
async def threshold():
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    return ThresholdResponse(
        threshold=_model.threshold,
        sensitivity=_model.sensitivity,
        specificity=_model.specificity,
    )
