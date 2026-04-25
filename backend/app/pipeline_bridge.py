from __future__ import annotations

import asyncio
import base64
import io
import logging
from collections.abc import Awaitable, Callable

import av
from getstream.video.rtc.track_util import PcmData
from PIL import Image
from vision_agents.core.events import AudioFormat
from vision_agents.core.edge.types import Participant
from vision_agents.core.llm.events import LLMResponseChunkEvent, LLMResponseCompletedEvent
from vision_agents.core.stt.events import STTPartialTranscriptEvent, STTTranscriptEvent
from vision_agents.core.tts.events import TTSAudioEvent, TTSErrorEvent, TTSSynthesisCompleteEvent
from vision_agents.core.utils.video_forwarder import VideoForwarder
from vision_agents.core.utils.video_track import QueuedVideoTrack
from vision_agents.core.warmup import WarmupCache

from .agent_factory import _build_processors, build_stt, build_text_llm, build_tts
from .config import Settings
from .session_manager import session_manager

logger = logging.getLogger(__name__)

JsonEmitter = Callable[[dict[str, object]], Awaitable[None]]
_warmup_cache = WarmupCache()


class FastWhisperPipelineBridge:
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
        self._participant = Participant(
            original=None,
            user_id="wearer",
            id=session_id,
        )
        self._llm = None
        self._stt = None
        self._tts = None
        self._video_track: QueuedVideoTrack | None = None
        self._video_forwarder: VideoForwarder | None = None
        self._processors: list[object] = []
        self._started = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._response_lock = asyncio.Lock()
        self._audio_chunks_seen = 0
        self._video_frames_seen = 0
        self._text_messages_seen = 0
        self._pending_user_text: list[str] = []
        self._turn_task: asyncio.Task[None] | None = None
        self._output_chunks_sent = 0

    @property
    def started(self) -> bool:
        return self._started and not self._closed

    async def start(self) -> None:
        async with self._lock:
            if self.started:
                return

            logger.info(
                "pipeline bridge start session_id=%s stt=fast_whisper llm=%s tts=%s",
                self.session_id,
                self.settings.gemini_llm_model,
                "elevenlabs" if self.settings.elevenlabs_api_key else "android_fallback",
            )

            self._llm = build_text_llm(self.settings)
            self._llm.set_instructions(self.settings.agent_instructions)
            self._subscribe_llm_events(self._llm)

            self._stt = build_stt(self.settings)
            self._subscribe_stt_events(self._stt)
            await self._stt.warmup(_warmup_cache)
            await self._stt.start()

            self._tts = build_tts(self.settings)
            if self._tts is not None:
                self._tts.set_output_format(
                    sample_rate=24000,
                    channels=1,
                    audio_format=AudioFormat.PCM_S16,
                )
                self._subscribe_tts_events(self._tts)
            else:
                session_manager.append_debug_event(
                    self.session_id,
                    "tts_fallback",
                    {"message": "ELEVENLABS_API_KEY missing, Android local TTS fallback active."},
                )

            video_fps = max(self.settings.realtime_video_fps, self.settings.processor_fps, 1)
            self._video_track = QueuedVideoTrack(width=640, height=360, fps=video_fps)
            self._video_forwarder = VideoForwarder(
                self._video_track,
                max_buffer=10,
                fps=float(video_fps),
                name=f"pipeline_{self.session_id}",
            )

            processors = _build_processors(self.settings)
            for processor in processors:
                await processor.process_video(
                    self._video_track,
                    participant_id=self.session_id,
                    shared_forwarder=self._video_forwarder,
                )

            self._processors = processors
            self._started = True
            self._closed = False
            await self._publish_processor_signals()

    async def send_initial_prompt(self) -> None:
        await self._respond_with_text(
            "Greet the wearer in one short sentence and ask them to show the patient."
        )

    async def send_audio(self, audio_bytes: bytes) -> None:
        if not self.started or not audio_bytes:
            return

        self._audio_chunks_seen += 1
        pcm = PcmData.from_bytes(
            audio_bytes,
            sample_rate=16000,
            format="s16",
            channels=1,
        )
        await self._stt.process_audio(pcm, self._participant)

    async def send_video_frame(self, image_bytes: bytes) -> None:
        if not self.started or not image_bytes or self._video_track is None:
            return

        self._video_frames_seen += 1
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            logger.warning(
                "pipeline bridge invalid video frame session_id=%s bytes=%s",
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
        session_manager.update_input_transcript(self.session_id, prompt)
        session_manager.append_debug_event(
            self.session_id,
            "text_message",
            {"text": prompt},
        )
        await self._safe_emit(
            {
                "serverContent": {
                    "inputTranscription": {"text": prompt},
                }
            }
        )
        await self._respond_with_text(prompt)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return

            self._closed = True
            self._started = False

            if self._turn_task is not None:
                self._turn_task.cancel()
                self._turn_task = None

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

            if self._tts is not None:
                await self._tts.close()
                self._tts = None

            if self._stt is not None:
                await self._stt.close()
                self._stt = None

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
            session_manager.update_processor_signal(self.session_id, payload["name"], payload)
            session_manager.append_debug_event(self.session_id, "processor_signal", payload)

    def _subscribe_stt_events(self, stt_component: object) -> None:
        @stt_component.events.subscribe
        async def on_partial_transcript(event: STTPartialTranscriptEvent) -> None:
            session_manager.append_debug_event(
                self.session_id,
                "stt_partial",
                {"text": event.text},
            )

        @stt_component.events.subscribe
        async def on_final_transcript(event: STTTranscriptEvent) -> None:
            text = event.text.strip()
            if not text:
                return

            logger.info(
                "pipeline transcript session_id=%s text=%r",
                self.session_id,
                text[:200],
            )
            session_manager.update_input_transcript(self.session_id, text)
            session_manager.append_debug_event(
                self.session_id,
                "input_transcription",
                {"text": text},
            )
            await self._safe_emit(
                {
                    "serverContent": {
                        "inputTranscription": {"text": text},
                    }
                }
            )
            self._pending_user_text.append(text)
            if self._turn_task is not None:
                self._turn_task.cancel()
            self._turn_task = asyncio.create_task(self._debounced_turn_response())

    def _subscribe_llm_events(self, llm_component: object) -> None:
        @llm_component.events.subscribe
        async def on_llm_chunk(event: LLMResponseChunkEvent) -> None:
            if not event.delta:
                return

            session_manager.update_output_transcript(self.session_id, event.delta)
            session_manager.append_debug_event(
                self.session_id,
                "output_transcription",
                {"text": event.delta},
            )
            await self._safe_emit(
                {
                    "serverContent": {
                        "outputTranscription": {"text": event.delta},
                    }
                }
            )

        @llm_component.events.subscribe
        async def on_llm_complete(event: LLMResponseCompletedEvent) -> None:
            text = event.text.strip()
            if not text:
                return

            session_manager.append_debug_event(
                self.session_id,
                "llm_completed",
                {"text": text},
            )
            if self._tts is None:
                session_manager.complete_turn(self.session_id)
                await self._safe_emit({"serverContent": {"turnComplete": True}})
                return

            await self._tts.send(text, participant=self._participant)

    def _subscribe_tts_events(self, tts_component: object) -> None:
        @tts_component.events.subscribe
        async def on_tts_audio(event: TTSAudioEvent) -> None:
            if event.data is None:
                return

            self._output_chunks_sent += 1
            await self._safe_emit(
                {
                    "audioOutput": {
                        "mimeType": "audio/pcm;rate=24000",
                        "data": base64.b64encode(event.data.to_bytes()).decode("ascii"),
                    }
                }
            )

        @tts_component.events.subscribe
        async def on_tts_complete(event: TTSSynthesisCompleteEvent) -> None:
            session_manager.append_debug_event(
                self.session_id,
                "tts_complete",
                {"synthesis_id": event.synthesis_id},
            )
            session_manager.complete_turn(self.session_id)
            await self._safe_emit({"serverContent": {"turnComplete": True}})

        @tts_component.events.subscribe
        async def on_tts_error(event: TTSErrorEvent) -> None:
            session_manager.append_debug_event(
                self.session_id,
                "tts_error",
                {"message": event.error_message},
            )
            await self._safe_emit(
                {
                    "type": "bridge_error",
                    "message": f"ElevenLabs TTS failed: {event.error_message}",
                }
            )

    async def _debounced_turn_response(self) -> None:
        try:
            await asyncio.sleep(self.settings.pipeline_turn_delay_ms / 1000)
        except asyncio.CancelledError:
            return

        user_text = " ".join(self._pending_user_text).strip()
        self._pending_user_text.clear()
        if not user_text:
            return
        await self._respond_with_text(user_text)

    async def _respond_with_text(self, text: str) -> None:
        async with self._response_lock:
            prompt = text
            processor_context = self._processor_context()
            if processor_context:
                prompt = f"{processor_context}\n\nUser request: {text}"

            try:
                await self._llm.simple_response(prompt, participant=self._participant)
            except Exception as exc:
                logger.exception("pipeline llm failure session_id=%s", self.session_id)
                session_manager.append_debug_event(
                    self.session_id,
                    "bridge_error",
                    {"message": str(exc)},
                )
                await self._safe_emit(
                    {
                        "type": "bridge_error",
                        "message": f"LLM response failed: {exc}",
                    }
                )

    async def _safe_emit(self, payload: dict[str, object]) -> None:
        if self._closed:
            return
        try:
            await self._emit(payload)
        except Exception:
            logger.exception("Failed to emit pipeline bridge payload")
