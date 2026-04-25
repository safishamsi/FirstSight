from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vision_agents.core.processors import VideoProcessor

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

    def __init__(self, fps: int = 2, threshold: float = 0.75) -> None:
        self.fps = fps
        self.threshold = threshold
        self._forwarder: VideoForwarder | None = None
        self.latest_signal = FaceDroopSignal(
            score=0.0,
            threshold=threshold,
            over_threshold=False,
            message="Model not yet wired.",
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
        del frame
        # Replace this placeholder with the real droopiness model inference.
        self.latest_signal = FaceDroopSignal(
            score=0.0,
            threshold=self.threshold,
            over_threshold=False,
            message="Placeholder processor active. Connect the droopiness model here.",
        )
