"""
Mouth-region preprocessing using the MediaPipe Tasks API (mediapipe >= 0.10).

For training: images are already mouth-region crops — no preprocessing needed.
For inference: detect_face_features() runs one MediaPipe pass and returns both
the mouth crop (for CNN) and landmark-based asymmetry scores (for gating).
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = str(Path(__file__).parent / "model" / "face_landmarker.task")

# Outer lip + chin landmarks for mouth bounding box
_MOUTH_INDICES = [
    0, 13, 14, 17,
    61, 291,
    78, 308,
    80, 310, 81, 311,
    82, 312, 87, 317,
    88, 318, 91, 321,
    95, 324, 146, 375,
    178, 405, 181, 402,
    191, 269, 267, 270,
    152,
]

# Asymmetry landmark indices (MediaPipe 478-point face mesh)
_LEFT_MOUTH_CORNER = 61
_RIGHT_MOUTH_CORNER = 291
_NOSE_TIP = 4
_CHIN = 152
_LEFT_EYE_UPPER = 159
_LEFT_EYE_LOWER = 145
_RIGHT_EYE_UPPER = 386
_RIGHT_EYE_LOWER = 374
_LEFT_BROW_INNER = 107
_LEFT_BROW_OUTER = 70
_RIGHT_BROW_INNER = 336
_RIGHT_BROW_OUTER = 300

_landmarker: mp_vision.FaceLandmarker | None = None
_landmarker_model_path: str | None = None


@dataclass
class FaceFeatures:
    mouth_crop: np.ndarray | None        # (H, W, 3) uint8 RGB
    mouth_asymmetry: float = 0.0         # |left_corner.y - right_corner.y| / face_height
    eye_asymmetry: float = 0.0           # |left_opening - right_opening| / max_opening
    brow_asymmetry: float = 0.0          # |left_brow.y - right_brow.y| / face_height
    asymmetry_score: float = 0.0         # weighted combination (0=symmetric, 1=very asymmetric)
    face_detected: bool = False


def _get_landmarker(model_path: str | None = None) -> mp_vision.FaceLandmarker:
    global _landmarker, _landmarker_model_path
    path = model_path or _DEFAULT_MODEL
    if _landmarker is None or _landmarker_model_path != path:
        if not Path(path).exists():
            raise FileNotFoundError(
                f"FaceLandmarker model not found at {path}. "
                "Download it with:\n  curl -sL "
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                "face_landmarker/float16/1/face_landmarker.task -o model/face_landmarker.task"
            )
        options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=path),
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
        )
        _landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        _landmarker_model_path = path
    return _landmarker


def _compute_asymmetry(landmarks) -> tuple[float, float, float, float]:
    """Compute left-right facial asymmetry from 478-point landmarks.

    All measurements are projected onto the face's own nose→chin axis so that
    head tilt does not inflate asymmetry scores on symmetric faces.

    Returns (mouth_asym, eye_asym, brow_asym, combined_score).
    All values in [0, 1]; higher = more asymmetric.
    """
    nose = landmarks[_NOSE_TIP]
    chin = landmarks[_CHIN]

    # Unit vector along the face's vertical axis (nose → chin)
    ax = chin.x - nose.x
    ay = chin.y - nose.y
    face_h = (ax ** 2 + ay ** 2) ** 0.5 + 1e-6
    ax /= face_h
    ay /= face_h

    def proj(lm) -> float:
        """Project landmark onto the face axis; returns signed face-axis coordinate."""
        return (lm.x - nose.x) * ax + (lm.y - nose.y) * ay

    def euc(a, b) -> float:
        """Euclidean distance between two landmarks (rotation-invariant)."""
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    # Mouth: difference in face-axis position of left vs right corners
    mouth_asym = abs(proj(landmarks[_LEFT_MOUTH_CORNER]) - proj(landmarks[_RIGHT_MOUTH_CORNER])) / face_h

    # Eyes: Euclidean opening of each eye (rotation-invariant distance)
    left_eye_h = euc(landmarks[_LEFT_EYE_UPPER], landmarks[_LEFT_EYE_LOWER])
    right_eye_h = euc(landmarks[_RIGHT_EYE_UPPER], landmarks[_RIGHT_EYE_LOWER])
    max_eye = max(left_eye_h, right_eye_h, 1e-6)
    eye_asym = abs(left_eye_h - right_eye_h) / max_eye

    # Brows: difference in face-axis position of average brow height
    left_brow_proj = (proj(landmarks[_LEFT_BROW_INNER]) + proj(landmarks[_LEFT_BROW_OUTER])) / 2
    right_brow_proj = (proj(landmarks[_RIGHT_BROW_INNER]) + proj(landmarks[_RIGHT_BROW_OUTER])) / 2
    brow_asym = abs(left_brow_proj - right_brow_proj) / face_h

    # Weighted combination: mouth is the primary stroke indicator
    combined = 0.5 * mouth_asym + 0.3 * eye_asym + 0.2 * brow_asym
    return float(mouth_asym), float(eye_asym), float(brow_asym), float(combined)


def _load_image(image_input) -> np.ndarray | None:
    import cv2
    if isinstance(image_input, (str, Path)):
        bgr = cv2.imread(str(image_input))
        if bgr is None:
            return None
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    img = np.asarray(image_input)
    if img.ndim == 2:
        import cv2
        return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    if img.shape[2] == 4:
        import cv2
        return cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    return img


def detect_face_features(
    image_input,
    target_size: int = 224,
    padding: float = 0.35,
    model_path: str | None = None,
) -> FaceFeatures:
    """Run one MediaPipe pass; return mouth crop + asymmetry scores.

    Args:
        image_input: numpy array (H, W, 3) RGB uint8, or a file path str/Path.
        target_size: crop edge length in pixels.
        padding: fractional padding around the mouth bounding box.
        model_path: path to face_landmarker.task.

    Returns:
        FaceFeatures with mouth_crop (or None if no face) and asymmetry scores.
    """
    import cv2

    image = _load_image(image_input)
    if image is None:
        return FaceFeatures(mouth_crop=None)

    h, w = image.shape[:2]
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
    result = _get_landmarker(model_path).detect(mp_image)

    if not result.face_landmarks:
        return FaceFeatures(mouth_crop=None)

    landmarks = result.face_landmarks[0]

    # Asymmetry from full face
    mouth_asym, eye_asym, brow_asym, combined = _compute_asymmetry(landmarks)

    # Mouth crop
    xs = [landmarks[i].x * w for i in _MOUTH_INDICES if i < len(landmarks)]
    ys = [landmarks[i].y * h for i in _MOUTH_INDICES if i < len(landmarks)]
    if not xs:
        return FaceFeatures(mouth_crop=None)

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad_x = (x_max - x_min) * padding
    pad_y = (y_max - y_min) * padding
    x1 = max(0, int(x_min - pad_x))
    y1 = max(0, int(y_min - pad_y))
    x2 = min(w, int(x_max + pad_x))
    y2 = min(h, int(y_max + pad_y))

    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return FaceFeatures(mouth_crop=None)

    mouth_crop = cv2.resize(crop, (target_size, target_size), interpolation=cv2.INTER_AREA)

    return FaceFeatures(
        mouth_crop=mouth_crop,
        mouth_asymmetry=mouth_asym,
        eye_asymmetry=eye_asym,
        brow_asymmetry=brow_asym,
        asymmetry_score=combined,
        face_detected=True,
    )


def crop_mouth_region(
    image_input,
    target_size: int = 224,
    padding: float = 0.35,
    model_path: str | None = None,
) -> np.ndarray | None:
    """Backward-compatible wrapper — returns just the mouth crop."""
    return detect_face_features(image_input, target_size, padding, model_path).mouth_crop
