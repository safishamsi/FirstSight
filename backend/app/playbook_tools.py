from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings
from .incident_state import ChecklistItem
from .session_manager import session_manager
from .tools.facial_droop import predict_session_latest_frame


@dataclass(slots=True)
class ToolExecutionResult:
    tool_name: str
    status: str
    summary: str
    payload: dict[str, object]
    should_advance: bool
    overlays: list[dict[str, object]] | None = None
    spatial_context_summary: str | None = None


def _latest_frame_base64(session_id: str) -> str:
    record = session_manager.get(session_id)
    if record is None or record.latest_preview_frame is None:
        raise ValueError("Preview frame not available")
    return base64.b64encode(record.latest_preview_frame).decode("ascii")


def _vision_tool_request(
    *,
    settings: Settings,
    endpoint: str,
    payload: dict[str, object],
) -> dict[str, object]:
    base_url = settings.vision_tool_base_url.strip().rstrip("/")
    if not base_url:
        raise RuntimeError("VISION_TOOL_BASE_URL is not configured")
    headers = {"Content-Type": "application/json"}
    if settings.vision_tool_auth_token.strip():
        headers["Authorization"] = f"Bearer {settings.vision_tool_auth_token.strip()}"
    request = Request(
        f"{base_url}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.vision_tool_timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vision tool HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Vision tool network error: {exc.reason}") from exc


def _gemini_visual_assess(
    *,
    settings: Settings,
    session_id: str,
    prompt: str,
) -> dict[str, object]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    image_base64 = _latest_frame_base64(session_id)
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You are assessing a first-aid scene from a wearable camera frame. "
                            "Return JSON only with keys: status, confidence, summary. "
                            "status must be one of positive, negative, unclear. "
                            f"{prompt}"
                        )
                    },
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_base64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseJsonSchema": {
                "type": "OBJECT",
                "properties": {
                    "status": {
                        "type": "STRING",
                        "enum": ["positive", "negative", "unclear"],
                    },
                    "confidence": {"type": "NUMBER"},
                    "summary": {"type": "STRING"},
                },
                "required": ["status", "confidence", "summary"],
            },
        },
    }
    request = Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_llm_model}:generateContent?key={settings.gemini_api_key}"
        ),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.vision_tool_timeout_s) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini visual HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Gemini visual network error: {exc.reason}") from exc

    data = json.loads(raw)
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    if not text:
        raise RuntimeError("Gemini visual returned no structured response")
    return json.loads(text)


def _box_overlay_from_detection(
    *,
    detection: dict[str, object],
    label: str,
) -> list[dict[str, object]]:
    bbox = detection.get("bbox")
    if not isinstance(bbox, dict):
        return []
    try:
        x = float(bbox["x"])
        y = float(bbox["y"])
        width = float(bbox["width"])
        height = float(bbox["height"])
    except (KeyError, TypeError, ValueError):
        return []
    return [
        {
            "id": f"tool-box-{label}",
            "kind": "box",
            "label": label,
            "color": "#52E0FF",
            "source": detection.get("provider", "vision_tool"),
            "box": {
                "xmin": x * 1000.0,
                "ymin": y * 1000.0,
                "xmax": (x + width) * 1000.0,
                "ymax": (y + height) * 1000.0,
            },
        }
    ]


async def execute_step_tool(
    session_id: str,
    step: ChecklistItem,
    settings: Settings,
) -> ToolExecutionResult:
    tool_name = (step.tool_name or "").strip()
    if tool_name == "facial_droop":
        prediction = await predict_session_latest_frame(session_id, settings)
        if not prediction.face_detected:
            return ToolExecutionResult(
                tool_name=tool_name,
                status="unclear",
                summary="I could not get a clear face view for the droop check.",
                payload=prediction.to_dict(),
                should_advance=False,
            )
        if prediction.is_drooping is True:
            summary = "The facial droop check looks suspicious for asymmetry."
            status = "positive"
        elif prediction.is_drooping is False:
            summary = "The facial droop check did not find obvious asymmetry."
            status = "negative"
        else:
            summary = "The facial droop check was inconclusive."
            status = "unclear"
        return ToolExecutionResult(
            tool_name=tool_name,
            status=status,
            summary=summary,
            payload=prediction.to_dict(),
            should_advance=status != "unclear",
        )

    if tool_name == "spatial_query":
        result = _gemini_visual_assess(
            settings=settings,
            session_id=session_id,
            prompt=step.tool_prompt or "Assess the current first-aid scene.",
        )
        status = str(result.get("status", "unclear"))
        summary = str(result.get("summary", "The spatial check was inconclusive.")).strip()
        return ToolExecutionResult(
            tool_name=tool_name,
            status=status,
            summary=summary,
            payload=result,
            should_advance=True,
        )

    if tool_name in {"box_query", "point_query"}:
        query = (step.tool_query or step.label or "").strip()
        if not query:
            raise RuntimeError("No spatial query is configured for this step")
        result = _vision_tool_request(
            settings=settings,
            endpoint="/locate-object",
            payload={
                "query": query,
                "includeSegmentation": False,
                "imageBase64": _latest_frame_base64(session_id),
            },
        )
        found = bool(result.get("found"))
        label = str(result.get("label") or query)
        if found:
            summary = f"I found a likely {label} and marked it on screen."
            status = "positive"
        else:
            summary = str(result.get("message") or f"I do not see a clear {query} in view yet.")
            status = "negative"
        overlays = _box_overlay_from_detection(detection=result, label=label)
        return ToolExecutionResult(
            tool_name=tool_name,
            status=status,
            summary=summary,
            payload=result,
            should_advance=True,
            overlays=overlays if tool_name == "box_query" else None,
            spatial_context_summary=summary,
        )

    raise RuntimeError(f"Unsupported playbook tool: {tool_name or 'none'}")
