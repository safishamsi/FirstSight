#!/usr/bin/env python3
"""
Grounding + guidance service for the CameraAccessAndroid demo.

Endpoints:
  GET  /health
  POST /guide-step
  POST /locate-object

Environment:
  VISION_TOOL_VENV      optional python venv path hint only
  ULTRALYTICS_MODEL     optional fast local model, default: yolo11n.pt
  MOONDREAM_API_KEY     optional, preferred fast detector backend
  GEMINI_API_KEY        optional fallback detector backend
  VISION_TOOL_BACKEND   optional: auto|ultralytics|moondream|gemini (default: auto)
  VISION_TOOL_MODEL     optional Gemini fallback model, default: gemini-3-flash-preview
  VISION_TOOL_HOST      optional, default: 0.0.0.0
  VISION_TOOL_PORT      optional, default: 8765
  VISION_TOOL_TOKEN     optional bearer token for requests
"""

from __future__ import annotations

import json
import os
import base64
import io
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MOONDREAM_API_KEY = os.environ.get("MOONDREAM_API_KEY", "").strip()
MODEL = os.environ.get("VISION_TOOL_MODEL", "gemini-3-flash-preview").strip()
BACKEND = os.environ.get("VISION_TOOL_BACKEND", "auto").strip().lower()
HOST = os.environ.get("VISION_TOOL_HOST", "0.0.0.0").strip()
PORT = int(os.environ.get("VISION_TOOL_PORT", "8765"))
AUTH_TOKEN = os.environ.get("VISION_TOOL_TOKEN", "").strip()
ULTRALYTICS_MODEL = os.environ.get("ULTRALYTICS_MODEL", "yolo11n.pt").strip()
DATA_FILE = Path(__file__).with_name("demo_task_data.json")
DEMO_TASK_DATA = json.loads(DATA_FILE.read_text())
OBJECT_KNOWLEDGE_FILE = Path(__file__).with_name("object_knowledge.json")
OBJECT_KNOWLEDGE = json.loads(OBJECT_KNOWLEDGE_FILE.read_text()) if OBJECT_KNOWLEDGE_FILE.exists() else {}
GUIDANCE_SESSIONS: dict[str, dict[str, Any]] = {}

try:
    from PIL import Image
except Exception:  # noqa: BLE001
    Image = None

try:
    from ultralytics import YOLO
except Exception:  # noqa: BLE001
    YOLO = None

try:
    import moondream as md
except Exception:  # noqa: BLE001
    md = None

_ULTRALYTICS_MODEL_INSTANCE = None
_MOONDREAM_MODEL_INSTANCE = None


@dataclass
class VisionRequest:
    query: str
    include_segmentation: bool
    image_base64: str


class VisionToolHandler(BaseHTTPRequestHandler):
    server_version = "VisionTool/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "backend": select_backend(),
                    "model": MODEL,
                    "authEnabled": bool(AUTH_TOKEN),
                    "moondreamConfigured": bool(MOONDREAM_API_KEY),
                    "geminiConfigured": bool(API_KEY),
                },
            )
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path == "/start-guidance":
            self._handle_start_guidance()
            return
        if self.path == "/inspect-object":
            self._handle_inspect_object()
            return
        if self.path == "/guide-step":
            self._handle_guide_step()
            return
        if self.path == "/advance-step":
            self._handle_advance_step()
            return
        if self.path == "/track-target":
            self._handle_track_target()
            return
        if self.path != "/locate-object":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        if AUTH_TOKEN:
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {AUTH_TOKEN}"
            if header != expected:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return

        try:
            request = self._parse_request()
            result = locate_object(request)
            self._send_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": f"Vision tool failed: {exc}",
                    "provider": "gemini-vision-tool",
                },
            )

    def _handle_guide_step(self) -> None:
        if AUTH_TOKEN:
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {AUTH_TOKEN}"
            if header != expected:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(content_length)
            if not raw:
                raise ValueError("Request body is empty.")
            payload = json.loads(raw.decode("utf-8"))
            result = guide_step(payload)
            self._send_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Guide step failed: {exc}", "provider": "demo-guidance"},
            )

    def _handle_start_guidance(self) -> None:
        if AUTH_TOKEN:
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {AUTH_TOKEN}"
            if header != expected:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            result = start_guidance(payload)
            self._send_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Start guidance failed: {exc}", "provider": "demo-guidance"},
            )

    def _handle_advance_step(self) -> None:
        if AUTH_TOKEN:
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {AUTH_TOKEN}"
            if header != expected:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            result = advance_step(payload)
            self._send_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Advance step failed: {exc}", "provider": "demo-guidance"},
            )

    def _handle_track_target(self) -> None:
        if AUTH_TOKEN:
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {AUTH_TOKEN}"
            if header != expected:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
        try:
            request = self._parse_request()
            result = locate_object(request)
            result["provider"] = f"{result.get('provider', 'tracker')}-track"
            self._send_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Track target failed: {exc}", "provider": "tracking"},
            )

    def _handle_inspect_object(self) -> None:
        if AUTH_TOKEN:
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {AUTH_TOKEN}"
            if header != expected:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            result = inspect_object(payload)
            self._send_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Inspect object failed: {exc}", "provider": "object-info"},
            )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        print(f"[vision-tool] {self.address_string()} - {format % args}")

    def _parse_request(self) -> VisionRequest:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(content_length)
        if not raw:
            raise ValueError("Request body is empty.")
        payload = json.loads(raw.decode("utf-8"))
        query = str(payload.get("query", "")).strip()
        image_base64 = str(payload.get("imageBase64", "")).strip()
        include_segmentation = bool(payload.get("includeSegmentation", False))
        if not query:
            raise ValueError("Missing query.")
        if not image_base64:
            raise ValueError("Missing imageBase64.")
        return VisionRequest(query, include_segmentation, image_base64)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def locate_object(request: VisionRequest) -> dict[str, Any]:
    backend = select_backend()
    if backend == "ultralytics":
        return locate_object_ultralytics(request)
    if backend == "moondream":
        return locate_object_moondream(request)
    if backend == "gemini":
        return locate_object_gemini(request)
    raise RuntimeError(f"Unsupported backend: {backend}")


def locate_object_gemini(request: VisionRequest) -> dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    prompt = build_prompt(request.query, request.include_segmentation)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": request.image_base64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseJsonSchema": response_schema(),
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={API_KEY}"
    )
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Gemini network error: {exc.reason}") from exc

    data = json.loads(raw)
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    if not text:
        raise RuntimeError(f"Gemini returned no text payload: {raw[:500]}")

    parsed = json.loads(text)
    return sanitize_response(parsed, request)


def locate_object_ultralytics(request: VisionRequest) -> dict[str, Any]:
    if YOLO is None or Image is None:
        raise RuntimeError("Ultralytics/Pillow are not installed in this runtime.")

    image = decode_base64_image(request.image_base64)
    model = get_ultralytics_model()
    results = model.predict(image, verbose=False)
    if not results:
        return not_found_response(request.query, "No detections returned by ultralytics.", "ultralytics")

    result = results[0]
    names = result.names
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return not_found_response(request.query, "No objects detected.", "ultralytics")

    normalized_query = normalize_query(request.query)
    best_match = None
    best_score = -1.0

    for idx in range(len(boxes)):
        cls_idx = int(boxes.cls[idx].item())
        label = str(names.get(cls_idx, cls_idx)).lower()
        confidence = float(boxes.conf[idx].item())
        score = label_match_score(normalized_query, label)
        if score > 0 and (score > best_score or (score == best_score and confidence > (best_match or {}).get("confidence", -1))):
            x1, y1, x2, y2 = boxes.xyxy[idx].tolist()
            best_match = {
                "label": label,
                "confidence": confidence,
                "bbox": normalize_xyxy(x1, y1, x2, y2, image.width, image.height),
            }
            best_score = score

    if best_match is None:
        available = [str(names.get(int(boxes.cls[i].item()), "")).lower() for i in range(len(boxes))]
        return not_found_response(
            request.query,
            f"Detected objects did not match query. Available labels: {sorted(set(available))[:8]}",
            "ultralytics",
        )

    bbox = best_match["bbox"]
    return {
        "found": True,
        "label": best_match["label"],
        "confidence": round(best_match["confidence"], 4),
        "bbox": bbox,
        "polygon": rectangle_polygon(bbox) if bbox is not None else [],
        "message": f"Detected {best_match['label']} with ultralytics.",
        "query": request.query,
        "provider": "ultralytics-detect",
    }


def locate_object_moondream(request: VisionRequest) -> dict[str, Any]:
    if not MOONDREAM_API_KEY:
        raise RuntimeError("MOONDREAM_API_KEY is not set.")

    if md is not None and Image is not None:
        image = decode_base64_image(request.image_base64)
        model = get_moondream_model()
        if request.include_segmentation:
            segment_response = model.segment(image, request.query)
            bbox = normalize_moondream_bbox(segment_response.get("bbox"))
            return {
                "found": bbox is not None,
                "label": request.query,
                "confidence": 0.92 if bbox is not None else 0.0,
                "bbox": bbox,
                "polygon": [],
                "message": (
                    f"Segmented {request.query} with Moondream SDK."
                    if bbox is not None
                    else f"Could not segment {request.query} with Moondream SDK."
                ),
                "query": request.query,
                "provider": "moondream-sdk-segment",
            }

        detect_response = model.detect(image, request.query)
        objects = detect_response.get("objects") or []
        bbox = normalize_moondream_bbox(objects[0]) if objects else None
        return {
            "found": bbox is not None,
            "label": request.query,
            "confidence": 0.95 if bbox is not None else 0.0,
            "bbox": bbox,
            "polygon": rectangle_polygon(bbox) if bbox is not None else [],
            "message": (
                f"Detected {request.query} with Moondream SDK."
                if bbox is not None
                else f"Could not detect {request.query} with Moondream SDK."
            ),
            "query": request.query,
            "provider": "moondream-sdk-detect",
        }

    if request.include_segmentation:
        segment_payload = {
            "image_url": f"data:image/jpeg;base64,{request.image_base64}",
            "object": request.query,
        }
        segment_response = moondream_request("/segment", segment_payload, timeout=30)
        bbox = normalize_moondream_bbox(segment_response.get("bbox"))
        return {
            "found": bbox is not None,
            "label": request.query,
            "confidence": 0.9 if bbox is not None else 0.0,
            "bbox": bbox,
            "polygon": [],
            "message": (
                f"Segmented {request.query}." if bbox is not None else f"Could not segment {request.query}."
            ),
            "query": request.query,
            "provider": "moondream-segment",
        }

    detect_payload = {
        "image_url": f"data:image/jpeg;base64,{request.image_base64}",
        "object": request.query,
    }
    detect_response = moondream_request("/detect", detect_payload, timeout=20)
    objects = detect_response.get("objects") or []
    bbox = normalize_moondream_bbox(objects[0]) if objects else None
    return {
        "found": bbox is not None,
        "label": request.query,
        "confidence": 0.92 if bbox is not None else 0.0,
        "bbox": bbox,
        "polygon": rectangle_polygon(bbox) if bbox is not None else [],
        "message": (
            f"Detected {request.query}." if bbox is not None else f"Could not detect {request.query}."
        ),
        "query": request.query,
        "provider": "moondream-detect",
    }


def guide_step(payload: dict[str, Any]) -> dict[str, Any]:
    session = resolve_guidance_session(payload)
    task_name = str(session.get("task") or DEMO_TASK_DATA["task"]).strip()
    step_index = int(session.get("stepIndex", 0))
    observed_label = str(payload.get("observedLabel") or "").strip().lower()
    object_found = bool(payload.get("objectFound", False))

    steps = DEMO_TASK_DATA["steps"]
    if step_index < 0 or step_index >= len(steps):
        raise ValueError("Invalid stepIndex.")

    step = steps[step_index]
    target_queries = step["targetQueries"]
    primary_query = target_queries[0]
    matched = any(query in observed_label or observed_label in query for query in target_queries) if observed_label else False
    step_complete = bool(object_found and matched)
    next_step_index = min(step_index + 1, len(steps) - 1) if step_complete else step_index

    if step_complete:
        instruction = (
            f"Good, that matches the {step['title'].lower()}. "
            f"{step['successHints'][0]}"
        )
    elif object_found and observed_label:
        instruction = (
            f"I found {observed_label}, but for this step I want you to focus on the {primary_query}. "
            f"{step['instruction']}"
        )
    else:
        instruction = step["instruction"]

    response = {
        "sessionId": session["sessionId"],
        "task": task_name,
        "stepIndex": step_index,
        "stepTitle": step["title"],
        "targetQuery": primary_query,
        "instruction": instruction,
        "stepComplete": step_complete,
        "nextStepIndex": next_step_index,
        "notes": list(DEMO_TASK_DATA["docs"]) + list(step["successHints"]),
        "provider": "demo-guidance",
    }
    GUIDANCE_SESSIONS[session["sessionId"]] = {
        **session,
        "task": task_name,
        "stepIndex": step_index,
        "stepTitle": step["title"],
        "targetQuery": primary_query,
        "instruction": instruction,
        "updatedAt": time.time(),
    }
    return response


def start_guidance(payload: dict[str, Any]) -> dict[str, Any]:
    task_name = str(payload.get("task") or DEMO_TASK_DATA["task"]).strip()
    session_id = str(payload.get("sessionId") or f"guidance-{uuid.uuid4().hex[:8]}")
    session = {
        "sessionId": session_id,
        "task": task_name,
        "stepIndex": 0,
        "updatedAt": time.time(),
    }
    GUIDANCE_SESSIONS[session_id] = session
    return guide_step({"sessionId": session_id})


def advance_step(payload: dict[str, Any]) -> dict[str, Any]:
    session = resolve_guidance_session(payload)
    steps = DEMO_TASK_DATA["steps"]
    next_index = min(int(session.get("stepIndex", 0)) + 1, len(steps) - 1)
    session["stepIndex"] = next_index
    session["updatedAt"] = time.time()
    GUIDANCE_SESSIONS[session["sessionId"]] = session
    return guide_step({"sessionId": session["sessionId"]})


def inspect_object(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or payload.get("label") or "").strip().lower()
    image_base64 = str(payload.get("imageBase64") or "").strip()
    if not query and not image_base64:
        raise ValueError("inspect_object requires a query, label, or imageBase64.")

    knowledge = lookup_object_knowledge(query) if query else None

    label = query or "object"
    title = knowledge.get("title") if knowledge else (query.title() if query else "Object")
    description = knowledge.get("description") if knowledge else ""
    used_for = knowledge.get("used_for") if knowledge else ""
    search_results = knowledge.get("search_results") if knowledge else []

    if (not description or not search_results) and image_base64 and md is not None and Image is not None and MOONDREAM_API_KEY:
        image = decode_base64_image(image_base64)
        model = get_moondream_model()
        if not description:
            response = model.query(image, f"What is this {query or 'object'} and what is it used for?")
            description = response.get("answer", "") or description
        if not title:
            title = (query or "Object").title()

    return {
        "label": label,
        "title": title,
        "description": description or f"{title} in the current scene.",
        "used_for": used_for or None,
        "search_results": search_results,
        "provider": "object-info",
    }


def build_prompt(query: str, include_segmentation: bool) -> str:
    segmentation_clause = (
        "If possible, return a polygon with 4 to 12 normalized points tracing the visible object outline. "
        if include_segmentation
        else "Return an empty polygon array. "
    )
    return f"""
You are a visual grounding tool for a live wearable assistant.

Task:
- Look at the image.
- Find the object that best matches this query: "{query}".
- Return only JSON matching the schema.

Rules:
- If the object is visible, set found=true.
- Use normalized coordinates from 0.0 to 1.0.
- bbox uses x, y, width, height.
- Confidence should be between 0 and 1.
- {segmentation_clause}
- If the object is not visible or too ambiguous, set found=false, bbox=null, confidence=0, polygon=[].
- Keep label concise.
- Set provider to "gemini-vision-tool".
""".strip()


def resolve_guidance_session(payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload.get("sessionId") or "default")
    if session_id not in GUIDANCE_SESSIONS:
        GUIDANCE_SESSIONS[session_id] = {
            "sessionId": session_id,
            "task": str(payload.get("task") or DEMO_TASK_DATA["task"]).strip(),
            "stepIndex": int(payload.get("stepIndex", 0)),
            "updatedAt": time.time(),
        }
    session = GUIDANCE_SESSIONS[session_id]
    if "task" in payload and payload["task"]:
        session["task"] = str(payload["task"]).strip()
    if "stepIndex" in payload:
        session["stepIndex"] = int(payload["stepIndex"])
    return session


def lookup_object_knowledge(query: str) -> dict[str, Any] | None:
    if not query:
        return None
    direct = OBJECT_KNOWLEDGE.get(query)
    if direct:
        return direct
    for key, value in OBJECT_KNOWLEDGE.items():
        if key in query or query in key:
            return value
    return None


def moondream_request(path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    url = f"https://api.moondream.ai/v1{path}"
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Moondream-Auth": MOONDREAM_API_KEY,
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Moondream HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Moondream network error: {exc.reason}") from exc
    return json.loads(raw)


def normalize_moondream_bbox(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, dict):
        return None
    try:
        x_min = clamp01(raw["x_min"])
        y_min = clamp01(raw["y_min"])
        x_max = clamp01(raw["x_max"])
        y_max = clamp01(raw["y_max"])
    except Exception:  # noqa: BLE001
        return None
    if x_max <= x_min or y_max <= y_min:
        return None
    return {
        "x": x_min,
        "y": y_min,
        "width": x_max - x_min,
        "height": y_max - y_min,
    }


def select_backend() -> str:
    if BACKEND in {"ultralytics", "moondream", "gemini"}:
        return BACKEND
    if YOLO is not None and Image is not None:
        return "ultralytics"
    if MOONDREAM_API_KEY:
        return "moondream"
    if API_KEY:
        return "gemini"
    return "none"


def get_ultralytics_model():
    global _ULTRALYTICS_MODEL_INSTANCE
    if _ULTRALYTICS_MODEL_INSTANCE is None:
        _ULTRALYTICS_MODEL_INSTANCE = YOLO(ULTRALYTICS_MODEL)
    return _ULTRALYTICS_MODEL_INSTANCE


def get_moondream_model():
    global _MOONDREAM_MODEL_INSTANCE
    if md is None:
        raise RuntimeError("moondream SDK is not installed in this Python environment.")
    if _MOONDREAM_MODEL_INSTANCE is None:
        _MOONDREAM_MODEL_INSTANCE = md.vl(api_key=MOONDREAM_API_KEY)
    return _MOONDREAM_MODEL_INSTANCE


def decode_base64_image(image_base64: str):
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]
    image_bytes = base64.b64decode(image_base64)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def normalize_query(query: str) -> set[str]:
    query = query.lower().strip()
    aliases = {
        "plant": {"plant", "potted plant"},
        "potted plant": {"plant", "potted plant"},
        "bottle": {"bottle"},
        "scissors": {"scissors"},
        "charging cable": {"cable", "wire", "charging cable"},
        "power cable": {"cable", "wire", "power cable"},
        "wire": {"wire", "cable"},
        "person": {"person"},
        "laptop": {"laptop", "computer", "tv", "monitor"},
    }
    for key, values in aliases.items():
        if key in query:
            return values
    return {query}


def label_match_score(query_terms: set[str], label: str) -> float:
    label = label.lower().strip()
    if label in query_terms:
        return 1.0
    for term in query_terms:
        if term in label or label in term:
            return 0.8
    return 0.0


def normalize_xyxy(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> dict[str, float] | None:
    if width <= 0 or height <= 0:
        return None
    left = clamp01(x1 / width)
    top = clamp01(y1 / height)
    right = clamp01(x2 / width)
    bottom = clamp01(y2 / height)
    if right <= left or bottom <= top:
        return None
    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def not_found_response(query: str, message: str, provider: str) -> dict[str, Any]:
    return {
        "found": False,
        "label": query,
        "confidence": 0.0,
        "bbox": None,
        "polygon": [],
        "message": message,
        "query": query,
        "provider": provider,
    }


def response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "found": {"type": "boolean"},
            "label": {"type": "string"},
            "confidence": {"type": "number"},
            "bbox": {
                "type": ["object", "null"],
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                },
                "required": ["x", "y", "width", "height"],
            },
            "polygon": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                    "required": ["x", "y"],
                },
            },
            "message": {"type": "string"},
            "provider": {"type": "string"},
        },
        "required": ["found", "label", "confidence", "bbox", "polygon", "message", "provider"],
    }


def sanitize_response(result: dict[str, Any], request: VisionRequest) -> dict[str, Any]:
    found = bool(result.get("found"))
    bbox = sanitize_bbox(result.get("bbox"))
    confidence = clamp01(result.get("confidence", 0.0))
    polygon = sanitize_polygon(result.get("polygon", []))

    if found and bbox is None:
        found = False

    if request.include_segmentation and found and not polygon and bbox is not None:
        polygon = rectangle_polygon(bbox)

    return {
        "found": found,
        "label": str(result.get("label") or request.query).strip(),
        "confidence": confidence if found else 0.0,
        "bbox": bbox if found else None,
        "polygon": polygon if found else [],
        "message": str(result.get("message") or ("Object found." if found else "Object not found.")),
        "query": request.query,
        "provider": str(result.get("provider") or "gemini-vision-tool"),
    }


def sanitize_bbox(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        x = clamp01(value["x"])
        y = clamp01(value["y"])
        width = clamp01(value["width"])
        height = clamp01(value["height"])
    except Exception:  # noqa: BLE001
        return None
    if width <= 0 or height <= 0:
        return None
    x2 = clamp01(x + width)
    y2 = clamp01(y + height)
    if x2 <= x or y2 <= y:
        return None
    return {"x": x, "y": y, "width": x2 - x, "height": y2 - y}


def sanitize_polygon(value: Any) -> list[dict[str, float]]:
    if not isinstance(value, list):
        return []
    points: list[dict[str, float]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            x = clamp01(item["x"])
            y = clamp01(item["y"])
        except Exception:  # noqa: BLE001
            continue
        points.append({"x": x, "y": y})
    return points


def rectangle_polygon(bbox: dict[str, float]) -> list[dict[str, float]]:
    x, y, width, height = bbox["x"], bbox["y"], bbox["width"], bbox["height"]
    return [
        {"x": x, "y": y},
        {"x": x + width, "y": y},
        {"x": x + width, "y": y + height},
        {"x": x, "y": y + height},
    ]


def clamp01(value: Any) -> float:
    value = float(value)
    return max(0.0, min(1.0, value))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), VisionToolHandler)
    print(f"[vision-tool] listening on http://{HOST}:{PORT} backend={select_backend()} model={MODEL} ultralytics_model={ULTRALYTICS_MODEL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
