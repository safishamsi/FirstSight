from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image
from vision_agents.core.processors import VideoProcessor

from ..config import Settings
from ..tools.facial_droop import predict_facial_droop_image

if TYPE_CHECKING:
    import aiortc
    from av import VideoFrame
    from vision_agents.core import Agent
    from vision_agents.core.utils.video_forwarder import VideoForwarder


@dataclass(slots=True)
class FaceDroopSignal:
    score: float
    threshold: float
    over_threshold: bool
    message: str


class FaceDroopProcessor(VideoProcessor):
    name = "face_droop_processor"

    def __init__(self, settings: Settings, fps: int = 2, threshold: float = 0.5) -> None:
        self.fps = fps
        self.threshold = threshold
        self._settings = settings
        self._forwarder: VideoForwarder | None = None
        self._inflight = False
        self.latest_signal = FaceDroopSignal(
            score=0.0,
            threshold=threshold,
            over_threshold=False,
            message=self._unconfigured_message(),
        )

    def attach_agent(self, agent: "Agent") -> None:
        self._agent = agent

    async def process_video(
        self,
        track: "aiortc.VideoStreamTrack",
        participant_id: str | None,
        shared_forwarder: "VideoForwarder" | None = None,
    ) -> None:
        del track
        del participant_id
        self._forwarder = shared_forwarder
        if self._forwarder is None:
            return

        self._forwarder.add_frame_handler(
            self._handle_frame,
            fps=float(self.fps),
            name=self.name,
        )

    async def close(self) -> None:
        return None

    async def _handle_frame(self, frame: "VideoFrame") -> None:
        if not self._settings.facial_droop_api_url:
            self.latest_signal = FaceDroopSignal(
                score=0.0,
                threshold=self.threshold,
                over_threshold=False,
                message=self._unconfigured_message(),
            )
            return
        if self._inflight:
            return

        self._inflight = True
        try:
            rgb = frame.to_ndarray(format="rgb24")
            buffer = io.BytesIO()
            Image.fromarray(rgb).save(buffer, format="JPEG", quality=85)
            result = await predict_facial_droop_image(
                buffer.getvalue(),
                self._settings,
                filename="face-droop-frame.jpg",
            )
            if not result.face_detected:
                self.latest_signal = FaceDroopSignal(
                    score=0.0,
                    threshold=self.threshold,
                    over_threshold=False,
                    message="No face detected for droop analysis.",
                )
                return

            score = float(result.droop_probability or 0.0)
            severity = result.severity or "unknown"
            asymmetry = result.asymmetry_score if result.asymmetry_score is not None else 0.0
            self.latest_signal = FaceDroopSignal(
                score=score,
                threshold=self.threshold,
                over_threshold=bool(result.is_drooping),
                message=(
                    f"Facial droop check severity={severity} "
                    f"prob={score:.2f} asymmetry={asymmetry:.3f}."
                ),
            )
        except Exception as exc:
            self.latest_signal = FaceDroopSignal(
                score=0.0,
                threshold=self.threshold,
                over_threshold=False,
                message=f"Facial droop service error: {exc}",
            )
        finally:
            self._inflight = False

    def _unconfigured_message(self) -> str:
        return (
            "Facial droop processor enabled but FACIAL_DROOP_API_URL is not configured."
        )
