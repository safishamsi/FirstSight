from pydantic import BaseModel


class PredictResponse(BaseModel):
    droop_probability: float | None
    is_drooping: bool | None
    severity: str | None  # "none" | "mild" | "severe"
    confidence: float | None
    face_detected: bool
    asymmetry_score: float | None = None
    mouth_asymmetry: float | None = None
    eye_asymmetry: float | None = None
    brow_asymmetry: float | None = None

    model_config = {"json_schema_extra": {
        "example": {
            "droop_probability": 0.83,
            "is_drooping": True,
            "severity": "severe",
            "confidence": 0.72,
            "face_detected": True,
            "asymmetry_score": 0.071,
            "mouth_asymmetry": 0.082,
            "eye_asymmetry": 0.054,
            "brow_asymmetry": 0.063,
        }
    }}


class VideoResponse(BaseModel):
    droop_likelihood: float | None
    """Blended score (0–1): 40% mean probability + 60% fraction of frames flagged."""

    fraction_frames_flagged: float | None
    """Proportion of analyzed frames where droop_probability ≥ threshold."""

    peak_probability: float | None
    """Highest single-frame droop probability observed."""

    temporal_consistency: float | None
    """1.0 = droop signal persistent across all frames; 0.0 = highly variable."""

    is_drooping: bool | None
    severity: str | None  # "none" | "mild" | "severe"

    frames_analyzed: int
    frames_skipped: int
    """Frames where no face was detected."""

    video_duration_s: float | None = None
    median_asymmetry: float | None = None
    """Median combined asymmetry score across frames (0=symmetric, higher=more asymmetric)."""

    model_config = {"json_schema_extra": {
        "example": {
            "droop_likelihood": 0.76,
            "fraction_frames_flagged": 0.82,
            "peak_probability": 0.91,
            "temporal_consistency": 0.85,
            "is_drooping": True,
            "severity": "severe",
            "frames_analyzed": 54,
            "frames_skipped": 3,
            "video_duration_s": 9.5,
            "median_asymmetry": 0.087,
        }
    }}


class HealthResponse(BaseModel):
    status: str
    model: str
    model_loaded: bool


class ThresholdResponse(BaseModel):
    threshold: float
    sensitivity: float
    specificity: float
