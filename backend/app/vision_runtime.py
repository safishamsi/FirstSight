from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from uuid import uuid4

from getstream import AsyncStream
from getstream.models import UserRequest
from vision_agents.core import AgentLauncher

from .agent_events import SpatialToolResultEvent
from .agent_factory import build_agent
from .config import Settings

logger = logging.getLogger(__name__)

_CALL_ID_PATTERN = re.compile(r"[^a-z0-9_-]+")


def _normalize_id(value: str, *, fallback_prefix: str) -> str:
    normalized = _CALL_ID_PATTERN.sub("-", value.strip().lower()).strip("-")
    if normalized:
        return normalized
    return f"{fallback_prefix}-{uuid4().hex[:8]}"


@dataclass(slots=True)
class AgentBootstrap:
    call_id: str
    call_type: str
    call_cid: str
    agent_session_id: str
    stream_api_key: str
    stream_user_id: str
    stream_user_token: str


class VisionRuntime:
    def __init__(self) -> None:
        self._launcher: AgentLauncher | None = None
        self._stream_admin: AsyncStream | None = None
        self._settings_key: tuple[str, str, str, str] | None = None
        self._lock = asyncio.Lock()

    async def ensure_started(self, settings: Settings) -> AgentLauncher:
        async with self._lock:
            settings_key = (
                settings.realtime_provider,
                settings.stream_api_key,
                settings.stream_api_secret,
                settings.agent_user_id,
            )
            if self._launcher is not None and self._settings_key == settings_key:
                return self._launcher

            if self._launcher is not None:
                await self._launcher.stop()

            self._launcher = AgentLauncher(
                create_agent=lambda **kwargs: build_agent(settings),
                join_call=self._join_call,
                max_sessions_per_call=1,
                max_concurrent_sessions=10,
                agent_idle_timeout=120.0,
            )
            await self._launcher.start()
            self._stream_admin = AsyncStream(
                api_key=settings.stream_api_key,
                api_secret=settings.stream_api_secret,
                user_agent="droopdetection-backend",
            )
            self._settings_key = settings_key
            logger.info("Vision runtime started for provider=%s", settings.realtime_provider)
            return self._launcher

    async def stop(self) -> None:
        async with self._lock:
            if self._launcher is not None:
                await self._launcher.stop()
            self._launcher = None
            self._stream_admin = None
            self._settings_key = None

    async def bootstrap(
        self,
        settings: Settings,
        *,
        user_id: str,
        user_name: str | None,
        call_id: str | None,
        call_type: str,
    ) -> AgentBootstrap:
        launcher = await self.ensure_started(settings)
        stream_admin = self._stream_admin
        if stream_admin is None:
            raise RuntimeError("Stream admin client is not initialized")

        normalized_user_id = _normalize_id(user_id, fallback_prefix="wearer")
        normalized_call_id = _normalize_id(call_id or f"call-{uuid4().hex[:8]}", fallback_prefix="call")
        normalized_call_type = _normalize_id(call_type, fallback_prefix="default")
        call_cid = f"{normalized_call_type}:{normalized_call_id}"

        await stream_admin.upsert_users(
            UserRequest(
                id=normalized_user_id,
                name=(user_name or normalized_user_id)[:128],
                role="user",
                custom={"source": "droopdetection-android"},
            )
        )
        stream_user_token = stream_admin.create_call_token(
            normalized_user_id,
            call_cids=[call_cid],
            role="user",
        )

        session = await launcher.start_session(
            call_id=normalized_call_id,
            call_type=normalized_call_type,
        )
        return AgentBootstrap(
            call_id=normalized_call_id,
            call_type=normalized_call_type,
            call_cid=call_cid,
            agent_session_id=session.id,
            stream_api_key=settings.stream_api_key,
            stream_user_id=normalized_user_id,
            stream_user_token=stream_user_token,
        )

    async def get_session_info(
        self,
        *,
        call_id: str,
        session_id: str,
    ) -> object:
        if self._launcher is None:
            raise RuntimeError("Vision runtime is not started")
        return await self._launcher.get_session_info(call_id, session_id)

    async def emit_spatial_tool_result(
        self,
        *,
        agent_session_id: str,
        backend_session_id: str,
        overlays: list[dict[str, object]],
        context_summary: str | None,
        ttl_ms: int | None,
        mode: str,
        replace: bool,
        mirror_to_session: bool = True,
    ) -> bool:
        if self._launcher is None:
            return False

        session = self._launcher.get_session(agent_session_id)
        if session is None:
            return False

        session.agent.events.register(SpatialToolResultEvent)
        session.agent.events.send(
            SpatialToolResultEvent(
                backend_session_id=backend_session_id,
                overlays=overlays,
                context_summary=context_summary,
                ttl_ms=ttl_ms,
                mode=mode,
                replace=replace,
                mirror_to_session=mirror_to_session,
            )
        )
        await session.agent.events.wait(timeout=1.0)
        logger.info(
            "Emitted spatial tool result event agent_session_id=%s backend_session_id=%s overlays=%s",
            agent_session_id,
            backend_session_id,
            len(overlays),
        )
        return True

    @staticmethod
    async def _join_call(agent: object, call_type: str, call_id: str, **kwargs: object) -> None:
        del kwargs
        call = await agent.create_call(call_type, call_id)
        async with agent.join(call):
            await agent.simple_response(
                "You are connected to the droopdetection backend. Give concise safety guidance."
            )
            await agent.finish()


vision_runtime = VisionRuntime()
