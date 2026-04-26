from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .incident_state import ChecklistItem
from .playbook_tools import ToolExecutionResult, execute_step_tool
from .session_manager import ChecklistAdvanceNotAvailableError, session_manager

_READINESS_TOKENS = (
    "ready",
    "go ahead",
    "check now",
    "run it",
    "run the check",
    "do the check",
    "yes",
)
_TOOL_EXECUTION_TOKENS = (
    "find",
    "locate",
    "look for",
    "search for",
    "scan",
    "show me",
    "where is",
    "can you see",
    "check it",
    "inspect",
)
_COMPLETION_TOKENS = (
    "done",
    "finished",
    "complete",
    "completed",
    "next",
    "what next",
    "move on",
    "i did",
    "they did",
)
_DECISION_ACK_TOKENS = (
    "yes",
    "yeah",
    "yep",
    "confirmed",
    "calling now",
    "they are",
    "i am",
    "we are",
    "no",
    "normal",
    "slurred",
    "unclear",
    "speech sounds normal",
    "speech is slurred",
)
_GUIDANCE_TOKENS = (
    "what next",
    "next step",
    "what should i do",
    "what do i do",
    "guide me",
)


@dataclass(slots=True)
class OrchestrationOutcome:
    handled: bool
    response_text: str | None = None


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = text.lower().strip()
    return any(phrase in normalized for phrase in phrases)


def _active_step_message(step: ChecklistItem) -> str:
    parts: list[str] = []
    if step.speak_before:
        parts.append(step.speak_before.strip())
    else:
        parts.append(step.label.strip())
    if step.tool_name and step.requires_user_confirmation:
        parts.append("Tell me when you are ready and I will run the check.")
    elif step.kind in {"user_action", "decision"}:
        parts.append("Tell me when that step is done so I can move to the next one.")
    return " ".join(parts)


def _current_step(session_id: str) -> ChecklistItem | None:
    return session_manager.get_active_checklist_item(session_id)


def build_current_step_message(session_id: str) -> str:
    step = _current_step(session_id)
    if step is None:
        return ""
    return _active_step_message(step)


def _compose_followup(session_id: str) -> str:
    next_step = _current_step(session_id)
    if next_step is None:
        return "That checklist is complete. Stay with the patient and keep following emergency instructions."
    return _active_step_message(next_step)


def _next_pending_tool_step(session_id: str) -> ChecklistItem | None:
    record = session_manager.get(session_id)
    if record is None:
        return None
    seen_current = False
    for item in record.active_checklist:
        if item.status == "active":
            seen_current = True
            continue
        if not seen_current:
            continue
        if item.status == "pending" and item.tool_name:
            return item
    return None


async def handle_user_turn(
    session_id: str,
    text: str,
    settings: Settings,
) -> OrchestrationOutcome:
    step = _current_step(session_id)
    if step is None:
        return OrchestrationOutcome(handled=False)

    normalized = text.strip().lower()
    if not normalized:
        return OrchestrationOutcome(handled=False)

    if step.tool_name:
        execute_tool = _contains_any(normalized, _READINESS_TOKENS) or _contains_any(normalized, _TOOL_EXECUTION_TOKENS)
        if _contains_any(normalized, _GUIDANCE_TOKENS) and not execute_tool and not _contains_any(normalized, _COMPLETION_TOKENS):
            return OrchestrationOutcome(
                handled=True,
                response_text=_active_step_message(step),
            )
        if execute_tool or not step.requires_user_confirmation:
            try:
                result = await execute_step_tool(session_id, step, settings)
            except Exception as exc:
                session_manager.append_tool_result(
                    session_id,
                    step_id=step.id,
                    tool_name=step.tool_name,
                    status="error",
                    summary=str(exc),
                    payload={},
                )
                return OrchestrationOutcome(
                    handled=True,
                    response_text=f"I could not run the {step.tool_name} check yet: {exc}",
                )

            session_manager.append_tool_result(
                session_id,
                step_id=step.id,
                tool_name=result.tool_name,
                status=result.status,
                summary=result.summary,
                payload=result.payload,
            )
            if result.overlays:
                session_manager.set_spatial_overlays(
                    session_id,
                    result.overlays,
                    context_summary=result.spatial_context_summary,
                    replace=True,
                    ttl_ms=8000,
                    mode="expert_scope",
                )
            if result.should_advance:
                session_manager.complete_checklist_item(session_id, step.id)
                return OrchestrationOutcome(
                    handled=True,
                    response_text=f"{result.summary} {_compose_followup(session_id)}",
                )
            return OrchestrationOutcome(
                handled=True,
                response_text=f"{result.summary} {_active_step_message(step)}",
            )
        return OrchestrationOutcome(
            handled=True,
            response_text=_active_step_message(step),
        )

    if _contains_any(normalized, _COMPLETION_TOKENS) or (step.kind == "decision" and _contains_any(normalized, _DECISION_ACK_TOKENS)):
        try:
            session_manager.complete_next_checklist_item(session_id)
        except ChecklistAdvanceNotAvailableError:
            return OrchestrationOutcome(
                handled=True,
                response_text="There is no remaining checklist step to advance right now.",
            )
        return OrchestrationOutcome(
            handled=True,
            response_text=_compose_followup(session_id),
        )

    if _contains_any(normalized, _TOOL_EXECUTION_TOKENS):
        next_tool_step = _next_pending_tool_step(session_id)
        if next_tool_step is not None:
            try:
                session_manager.complete_next_checklist_item(session_id)
            except ChecklistAdvanceNotAvailableError:
                return OrchestrationOutcome(handled=False)
            return await handle_user_turn(session_id, text, settings)

    if _contains_any(normalized, _GUIDANCE_TOKENS):
        return OrchestrationOutcome(
            handled=True,
            response_text=_active_step_message(step),
        )

    return OrchestrationOutcome(handled=False)
