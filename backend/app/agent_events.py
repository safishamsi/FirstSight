from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from vision_agents.core.events import BaseEvent
from vision_agents.core.processors import Processor

from .session_manager import session_manager

if TYPE_CHECKING:
    from vision_agents.core import Agent


@dataclass
class SpatialToolResultEvent(BaseEvent):
    type: str = field(default="custom.spatial_tool_result", init=False)
    backend_session_id: str = ""
    context_summary: str | None = None
    ttl_ms: int | None = None
    mode: str = "default"
    replace: bool = True
    mirror_to_session: bool = True
    overlays: list[dict[str, Any]] = field(default_factory=list)


class AgentCustomEventBridgeProcessor(Processor):
    name = "custom_event_bridge"

    async def close(self) -> None:
        return None

    def attach_agent(self, agent: "Agent") -> None:
        agent.events.register(SpatialToolResultEvent)

        @agent.events.subscribe
        async def on_spatial_tool_result(event: SpatialToolResultEvent) -> None:
            if event.mirror_to_session:
                session_manager.set_spatial_overlays(
                    event.backend_session_id,
                    event.overlays,
                    context_summary=event.context_summary,
                    replace=event.replace,
                    ttl_ms=event.ttl_ms,
                    mode=event.mode,
                )
            session_manager.append_debug_event(
                event.backend_session_id,
                "agent_custom_event",
                {
                    "event_type": event.type,
                    "overlay_count": len(event.overlays),
                    "context_summary": event.context_summary,
                    "ttl_ms": event.ttl_ms,
                    "mode": event.mode,
                    "mirror_to_session": event.mirror_to_session,
                },
            )
