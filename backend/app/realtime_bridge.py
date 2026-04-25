from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable

import av
from getstream.video.rtc.track_util import PcmData
from PIL import Image
from vision_agents.core.llm.events import (
    RealtimeAgentSpeechTranscriptionEvent,
    RealtimeAudioOutputDoneEvent,
    RealtimeDisconnectedEvent,
    RealtimeErrorEvent,
    RealtimeUserSpeechTranscriptionEvent,
)
from vision_agents.core.utils.video_forwarder import VideoForwarder
from vision_agents.core.utils.video_track import QueuedVideoTrack

from .agent_factory import _build_processors, build_realtime_llm
from .config import Settings
from .pipeline_bridge import FastWhisperPipelineBridge
from .session_manager import session_manager

logger = logging.getLogger(__name__)

JsonEmitter = Callable[[dict[str, object]], Awaitable[None]]


class VisionSessionBridge:
    def __init__(
        self,
        *,
        session_id: str,
        settings: Settings,
        emit: JsonEmitter,
    ) -> None:
        self.session_id = session_id
        self.settings = settings
        self._emit = emit
        self._llm: object | None = None
        self._video_track: QueuedVideoTrack | None = None
        self._video_forwarder: VideoForwarder | None = None
        self._processors: list[object] = []
        self._started = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._audio_chunks_seen = 0
        self._video_frames_seen = 0
        self._text_messages_seen = 0

    @property
    def started(self) -> bool:
        return self._started and not self._closed

    async def start(self) -> None:
        async with self._lock:
            if self.started:
                return

            llm = build_realtime_llm(self.settings)
            logger.info(
                "bridge start session_id=%s provider=%s processor_fps=%s realtime_video_fps=%s",
                self.session_id,
                self.settings.realtime_provider,
                self.settings.processor_fps,
                self.settings.realtime_video_fps,
            )
            llm.set_instructions(self.settings.agent_instructions)
            self._subscribe_to_events(llm)

            await llm.connect()
            logger.info("bridge provider connected session_id=%s", self.session_id)

            video_fps = max(self.settings.realtime_video_fps, self.settings.processor_fps, 1)
            self._video_track = QueuedVideoTrack(width=640, height=360, fps=video_fps)
            self._video_forwarder = VideoForwarder(
                self._video_track,
                max_buffer=10,
                fps=float(video_fps),
                name=f"bridge_{self.session_id}",
            )

            processors = _build_processors(self.settings)
            logger.info(
                "bridge processors built session_id=%s count=%s names=%s",
                self.session_id,
                len(processors),
                ",".join(getattr(processor, "name", processor.__class__.__name__) for processor in processors) or "none",
            )
            for processor in processors:
                await processor.process_video(
                    self._video_track,
                    participant_id=self.session_id,
                    shared_forwarder=self._video_forwarder,
                )

            await llm.watch_video_track(
                self._video_track,
                shared_forwarder=self._video_forwarder,
            )
            logger.info("bridge video track watching session_id=%s", self.session_id)

            self._llm = llm
            self._processors = processors
            self._started = True
            self._closed = False
            await self._publish_processor_signals()

    async def send_initial_prompt(self) -> None:
        if not self.started:
            return
        logger.info("bridge initial prompt session_id=%s", self.session_id)
        prompt = (
            "You are now live in a first aid smart glasses session. "
            "Greet the wearer in one short sentence and ask them to show the patient."
        )
        await self._llm.simple_response(prompt)

    async def send_audio(self, audio_bytes: bytes) -> None:
        if not self.started or not audio_bytes:
            return
        self._audio_chunks_seen += 1
        if self._audio_chunks_seen in {1, 2, 5, 10} or self._audio_chunks_seen % 25 == 0:
            logger.info(
                "bridge audio session_id=%s chunk_count=%s bytes=%s",
                self.session_id,
                self._audio_chunks_seen,
                len(audio_bytes),
            )

        pcm = PcmData.from_bytes(
            audio_bytes,
            sample_rate=16000,
            format="s16",
            channels=1,
        )
        if self.settings.realtime_provider == "openai":
            pcm = pcm.resample(target_sample_rate=48000, target_channels=1)
        await self._llm.simple_audio_response(pcm)

    async def send_video_frame(self, image_bytes: bytes) -> None:
        if not self.started or not image_bytes or self._video_track is None:
            return
        self._video_frames_seen += 1
        if self._video_frames_seen in {1, 2, 5, 10} or self._video_frames_seen % 25 == 0:
            logger.info(
                "bridge video session_id=%s frame_count=%s bytes=%s",
                self.session_id,
                self._video_frames_seen,
                len(image_bytes),
            )

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            logger.warning(
                "bridge invalid video frame session_id=%s bytes=%s",
                self.session_id,
                len(image_bytes),
                exc_info=True,
            )
            return
        frame = av.VideoFrame.from_image(image)
        await self._video_track.add_frame(frame)
        await self._publish_processor_signals()

    async def send_text(self, text: str) -> None:
        if not self.started:
            return
        prompt = text.strip()
        if not prompt:
            return
        self._text_messages_seen += 1
        logger.info(
            "bridge text session_id=%s text_count=%s chars=%s text=%r",
            self.session_id,
            self._text_messages_seen,
            len(prompt),
            prompt[:200],
        )

        processor_context = self._processor_context()
        if processor_context:
            prompt = f"{processor_context}\n\nUser request: {prompt}"

        await self._llm.simple_response(prompt)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            logger.info(
                "bridge close session_id=%s audio_chunks=%s video_frames=%s text_messages=%s",
                self.session_id,
                self._audio_chunks_seen,
                self._video_frames_seen,
                self._text_messages_seen,
            )
            self._closed = True
            self._started = False

            if self._video_forwarder is not None:
                await self._video_forwarder.stop()
                self._video_forwarder = None

            if self._video_track is not None:
                self._video_track.stop()
                self._video_track = None

            for processor in self._processors:
                close = getattr(processor, "close", None)
                if close is not None:
                    await close()
            self._processors.clear()

            if self._llm is not None:
                await self._llm.close()
                self._llm = None

    def _processor_context(self) -> str:
        parts: list[str] = []
        for processor in self._processors:
            latest_signal = getattr(processor, "latest_signal", None)
            if latest_signal is None:
                continue
            message = getattr(latest_signal, "message", "")
            score = getattr(latest_signal, "score", None)
            threshold = getattr(latest_signal, "threshold", None)
            over_threshold = getattr(latest_signal, "over_threshold", None)
            parts.append(
                "Processor context: "
                f"{processor.name} score={score} threshold={threshold} "
                f"over_threshold={over_threshold}. {message}"
            )
        return "\n".join(parts)

    async def _publish_processor_signals(self) -> None:
        for processor in self._processors:
            latest_signal = getattr(processor, "latest_signal", None)
            if latest_signal is None:
                continue
            payload = {
                "name": getattr(processor, "name", processor.__class__.__name__),
                "score": getattr(latest_signal, "score", None),
                "threshold": getattr(latest_signal, "threshold", None),
                "over_threshold": getattr(latest_signal, "over_threshold", None),
                "message": getattr(latest_signal, "message", ""),
            }
            session_manager.update_processor_signal(
                self.session_id,
                payload["name"],
                payload,
            )
            session_manager.append_debug_event(
                self.session_id,
                "processor_signal",
                payload,
            )

    def _subscribe_to_events(self, llm: object) -> None:
        @llm.events.subscribe
        async def on_user_transcript(event: RealtimeUserSpeechTranscriptionEvent) -> None:
            logger.info(
                "bridge user transcript session_id=%s chars=%s text=%r",
                self.session_id,
                len(event.text),
                event.text[:200],
            )
            session_manager.update_input_transcript(self.session_id, event.text)
            session_manager.append_debug_event(
                self.session_id,
                "input_transcription",
                {"text": event.text},
            )
            await self._safe_emit(
                {
                    "serverContent": {
                        "inputTranscription": {"text": event.text},
                    }
                }
            )

        @llm.events.subscribe
        async def on_agent_transcript(
            event: RealtimeAgentSpeechTranscriptionEvent,
        ) -> None:
            logger.info(
                "bridge agent transcript session_id=%s chars=%s text=%r",
                self.session_id,
                len(event.text),
                event.text[:200],
            )
            session_manager.update_output_transcript(self.session_id, event.text)
            session_manager.append_debug_event(
                self.session_id,
                "output_transcription",
                {"text": event.text},
            )
            await self._safe_emit(
                {
                    "serverContent": {
                        "outputTranscription": {"text": event.text},
                    }
                }
            )

        @llm.events.subscribe
        async def on_turn_complete(event: RealtimeAudioOutputDoneEvent) -> None:
            del event
            logger.info("bridge turn complete session_id=%s", self.session_id)
            session_manager.append_debug_event(
                self.session_id,
                "turn_complete",
                {},
            )
            session_manager.complete_turn(self.session_id)
            await self._safe_emit({"serverContent": {"turnComplete": True}})

        @llm.events.subscribe
        async def on_bridge_disconnect(
            event: RealtimeDisconnectedEvent | RealtimeErrorEvent,
        ) -> None:
            message = getattr(event, "reason", None) or getattr(event, "error_message", None)
            logger.warning(
                "bridge disconnect session_id=%s message=%r",
                self.session_id,
                message or "Realtime bridge disconnected",
            )
            session_manager.append_debug_event(
                self.session_id,
                "bridge_error",
                {"message": message or "Realtime bridge disconnected"},
            )
            await self._safe_emit(
                {
                    "type": "bridge_error",
                    "message": message or "Realtime bridge disconnected",
                }
            )

    async def _safe_emit(self, payload: dict[str, object]) -> None:
        if self._closed:
            return
        try:
            await self._emit(payload)
        except Exception:
            logger.exception("Failed to emit realtime bridge payload")


class VisionBridgeManager:
    def __init__(self) -> None:
        self._bridges: dict[str, object] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        session_id: str,
        settings: Settings,
        emit: JsonEmitter,
    ) -> object:
        async with self._lock:
            bridge = self._bridges.get(session_id)
            if bridge is not None:
                return bridge

            if settings.speech_pipeline == "fast_whisper_pipeline":
                bridge = FastWhisperPipelineBridge(
                    session_id=session_id,
                    settings=settings,
                    emit=emit,
                )
            else:
                bridge = VisionSessionBridge(
                    session_id=session_id,
                    settings=settings,
                    emit=emit,
                )
            self._bridges[session_id] = bridge

        try:
            await bridge.start()
            return bridge
        except Exception:
            async with self._lock:
                self._bridges.pop(session_id, None)
            raise

    async def get(self, session_id: str) -> object | None:
        async with self._lock:
            return self._bridges.get(session_id)

    async def close(self, session_id: str) -> None:
        async with self._lock:
            bridge = self._bridges.pop(session_id, None)
        if bridge is not None:
            await bridge.close()


vision_bridge_manager = VisionBridgeManager()
