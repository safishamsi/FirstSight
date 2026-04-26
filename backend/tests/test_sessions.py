import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from vision_agents.core.events import EventManager

from app.agent_events import AgentCustomEventBridgeProcessor, SpatialToolResultEvent
from app.main import app
from app.guidance_runtime import search_and_optionally_activate_protocol
from app.pipeline_bridge import _extract_retry_delay_seconds
from app.session_manager import session_manager


def _receive_until_ack(websocket: object) -> tuple[list[dict[str, object]], dict[str, object]]:
    messages: list[dict[str, object]] = []
    for _ in range(30):
        message = websocket.receive_json()
        messages.append(message)
        if message.get("type") == "ack":
            return messages, message
    raise AssertionError(f"Did not receive ack message. Received: {messages}")


def _get_session_status_when_settled(client: TestClient, session_id: str) -> dict[str, object]:
    payload: dict[str, object] = {}
    for _ in range(10):
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] == "idle":
            return payload
        time.sleep(0.05)
    return payload


def test_session_create_returns_backend_bootstrap_shape() -> None:
    client = TestClient(app)

    create_response = client.post(
        "/sessions",
        json={
            "user_id": "android-demo-user",
            "user_name": "DroopDetection Demo",
            "call_type": "default",
            "start_agent_session": True,
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["session_id"]
    assert payload["vision_agent_started"] is False
    assert payload["stream_user_id"] == "android-demo-user"
    assert "STREAM_API_KEY" in payload["missing_configuration"]
    assert "STREAM_API_SECRET" in payload["missing_configuration"]


def test_session_runtime_config_is_persisted() -> None:
    client = TestClient(app)

    create_response = client.post(
        "/sessions",
        json={
            "user_id": "android-demo-user",
            "runtime_config": {
                "speech_pipeline": "fast_whisper_pipeline",
                "fast_whisper_model_size": "small",
                "fast_whisper_device": "cpu",
                "pipeline_turn_delay_ms": 900,
                "backend_tts_enabled": False,
            },
        },
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["runtime_config"]["speech_pipeline"] == "fast_whisper_pipeline"
    assert payload["runtime_config"]["fast_whisper_model_size"] == "small"
    assert payload["runtime_config"]["pipeline_turn_delay_ms"] == 900
    assert payload["runtime_config"]["backend_tts_enabled"] is False


def test_session_websocket_tracks_ingest_counts() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session_ready"

        websocket.send_json({"type": "video_frame", "mime_type": "image/jpeg"})
        messages, video_ack = _receive_until_ack(websocket)
        if not ready.get("bridge_active", False):
            server_messages = [message for message in messages if "serverContent" in message]
            assert server_messages
            assert "Possible stroke check started" in server_messages[0]["serverContent"]["outputTranscription"]["text"]
        assert video_ack["video_frames"] == 1

        websocket.send_json({"type": "audio_chunk", "mime_type": "audio/pcm"})
        _, audio_ack = _receive_until_ack(websocket)
        assert audio_ack["audio_chunks"] == 1

    payload = _get_session_status_when_settled(client, session_id)
    assert payload["video_frames"] == 1
    assert payload["audio_chunks"] == 1
    assert payload["status"] == "idle"


def test_session_websocket_accepts_gemini_style_envelopes() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session_ready"

        websocket.send_json({"setup": {"model": "backend-adapter"}})
        setup_complete = websocket.receive_json()
        assert "setupComplete" in setup_complete
        welcome = websocket.receive_json()
        assert welcome["serverContent"]["outputTranscription"]["text"]

        websocket.send_json(
            {
                "realtimeInput": {
                    "video": {
                        "mimeType": "image/jpeg",
                        "data": "ZmFrZQ==",
                    }
                }
            }
        )
        messages, video_ack = _receive_until_ack(websocket)
        if not ready.get("bridge_active", False):
            server_messages = [message for message in messages if "serverContent" in message]
            assert server_messages
            assert "Possible stroke check started" in server_messages[0]["serverContent"]["outputTranscription"]["text"]
        assert video_ack["received_type"] == "video_frame"
        assert video_ack["video_frames"] == 1

        websocket.send_json(
            {
                "realtimeInput": {
                    "audio": {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": "ZmFrZQ==",
                    }
                }
            }
        )
        _, audio_ack = _receive_until_ack(websocket)
        assert audio_ack["received_type"] == "audio_chunk"
        assert audio_ack["audio_chunks"] == 1

        websocket.send_json(
            {
                "clientContent": {
                    "turns": [
                        {
                            "role": "user",
                            "parts": [{"text": "help me check the patient"}],
                        }
                    ]
                }
            }
        )
        messages, text_ack = _receive_until_ack(websocket)
        server_messages = [message for message in messages if "serverContent" in message]
        if ready.get("bridge_active", False):
            assert text_ack["received_type"] == "text_message"
        else:
            assert server_messages
            assert server_messages[0]["serverContent"]["inputTranscription"]["text"] == "help me check the patient"
            assert "Backend adapter received" in server_messages[0]["serverContent"]["outputTranscription"]["text"]
        assert text_ack["received_type"] == "text_message"

    payload = _get_session_status_when_settled(client, session_id)
    assert payload["video_frames"] == 1
    assert payload["audio_chunks"] == 1
    assert payload["text_messages"] >= 2


def test_sessions_list_exposes_debug_state() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
        websocket.receive_json()
        websocket.send_json({"setup": {"model": "backend-adapter"}})
        websocket.receive_json()
        websocket.receive_json()

    list_response = client.get("/sessions")
    assert list_response.status_code == 200
    sessions = list_response.json()
    matching = next(session for session in sessions if session["session_id"] == session_id)
    assert matching["debug_events"]
    assert matching["debug_events"][-1]["type"] in {"stream_closed", "setup", "stream_connected"}


def test_protocols_are_listed() -> None:
    client = TestClient(app)

    response = client.get("/protocols")
    assert response.status_code == 200
    payload = response.json()
    assert any(protocol["id"] == "stroke_fast" for protocol in payload)
    assert any(protocol["id"] == "cpr_unresponsive_adult" for protocol in payload)
    assert any(protocol["id"] == "choking_adult" for protocol in payload)


def test_protocol_search_returns_ranked_hits() -> None:
    client = TestClient(app)

    response = client.get("/protocols/search", params={"q": "cannot breathe choking"})
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["protocol_id"] == "choking_adult"
    assert payload[0]["matched_excerpt"]
    assert payload[0]["score"] > 0


def test_protocol_detail_returns_manual_and_checklist() -> None:
    client = TestClient(app)

    response = client.get("/protocols/stroke_fast")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "stroke_fast"
    assert payload["manual_markdown"]
    assert payload["checklist_template"]
    assert payload["checklist_template"][0]["tool_name"] == "facial_droop"
    assert payload["checklist_template"][0]["requires_user_confirmation"] is True


def test_guide_search_returns_ranked_hits_without_setting_checklist_by_default() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    guide_response = client.post(
        f"/sessions/{session_id}/guide/search",
        json={"query": "possible stroke with face droop"},
    )
    assert guide_response.status_code == 200
    payload = guide_response.json()
    assert payload["activated_protocol_id"] is None
    assert payload["hits"][0]["protocol_id"] == "stroke_fast"
    assert payload["active_checklist"] == []
    assert payload["incident_state"]["active_protocol_id"] is None

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["active_checklist"] == []
    assert status_payload["incident_state"]["active_protocol_id"] is None


def test_checklist_set_overwrites_active_checklist() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    first_set = client.post(
        f"/sessions/{session_id}/checklist/set",
        json={"protocol_id": "stroke_fast", "matched_query": "possible stroke with face droop"},
    )
    assert first_set.status_code == 200
    first_payload = first_set.json()
    assert first_payload["incident_state"]["active_protocol_id"] == "stroke_fast"
    assert first_payload["incident_state"]["active_protocol_title"] == "Stroke FAST Check"
    assert first_payload["active_checklist"]
    assert first_payload["active_checklist"][0]["tool_name"] == "facial_droop"
    assert first_payload["active_checklist"][0]["speak_before"]

    second_set = client.post(
        f"/sessions/{session_id}/checklist/set",
        json={"protocol_id": "cpr_unresponsive_adult", "matched_query": "person on floor and unresponsive"},
    )
    assert second_set.status_code == 200
    second_payload = second_set.json()
    assert second_payload["incident_state"]["active_protocol_id"] == "cpr_unresponsive_adult"
    assert second_payload["incident_state"]["active_protocol_title"] == "Adult CPR For Unresponsive Person"
    assert second_payload["active_checklist"]
    assert second_payload["active_checklist"][0]["source_protocol_id"] == "cpr_unresponsive_adult"


def test_checklist_set_triggers_bridge_guidance_prompt() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    with patch("app.routes.vision_bridge_manager.prompt_guidance", new=AsyncMock(return_value=True)) as mocked_prompt:
        response = client.post(
            f"/sessions/{session_id}/checklist/set",
            json={"protocol_id": "stroke_fast", "matched_query": "possible stroke with face droop"},
        )

    assert response.status_code == 200
    mocked_prompt.assert_awaited_once_with(session_id, reason="a playbook was loaded")


def test_guide_search_activates_checklist_when_requested() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    guide_response = client.post(
        f"/sessions/{session_id}/guide/search",
        json={"query": "possible stroke with face droop", "auto_activate": True},
    )
    assert guide_response.status_code == 200
    payload = guide_response.json()
    assert payload["activated_protocol_id"] == "stroke_fast"
    assert payload["active_checklist"]
    assert payload["incident_state"]["active_protocol_id"] == "stroke_fast"
    assert payload["hits"][0]["protocol_id"] == "stroke_fast"

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["active_checklist"]
    assert status_payload["incident_state"]["active_protocol_id"] == "stroke_fast"
    assert status_payload["incident_state"]["active_protocol_title"] == "Stroke FAST Check"
    assert status_payload["incident_state"]["active_protocol_manual"]


def test_checklist_complete_advances_next_step() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    guide_response = client.post(
        f"/sessions/{session_id}/guide/search",
        json={"query": "person on floor and unresponsive", "auto_activate": True},
    )
    assert guide_response.status_code == 200
    checklist = guide_response.json()["active_checklist"]
    first_item_id = checklist[0]["id"]

    complete_response = client.post(
        f"/sessions/{session_id}/checklist/items/{first_item_id}/complete",
        json={},
    )
    assert complete_response.status_code == 200
    payload = complete_response.json()
    updated_items = payload["active_checklist"]
    assert updated_items[0]["status"] == "done"
    assert any(item["status"] == "active" for item in updated_items[1:])


def test_checklist_complete_next_advances_active_step() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    set_response = client.post(
        f"/sessions/{session_id}/checklist/set",
        json={"protocol_id": "cpr_unresponsive_adult", "matched_query": "person on floor and unresponsive"},
    )
    assert set_response.status_code == 200

    complete_response = client.post(f"/sessions/{session_id}/checklist/next/complete", json={})
    assert complete_response.status_code == 200
    payload = complete_response.json()
    updated_items = payload["active_checklist"]
    assert updated_items[0]["status"] == "done"
    assert any(item["status"] == "active" for item in updated_items[1:])


def test_checklist_complete_returns_404_for_unknown_item() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    guide_response = client.post(
        f"/sessions/{session_id}/guide/search",
        json={"query": "person on floor and unresponsive", "auto_activate": True},
    )
    assert guide_response.status_code == 200

    complete_response = client.post(
        f"/sessions/{session_id}/checklist/items/not-a-real-step/complete",
        json={},
    )
    assert complete_response.status_code == 404
    assert "Checklist item not found" in complete_response.json()["detail"]


def test_spatial_overlay_state_can_be_set_and_cleared() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    set_response = client.post(
        f"/sessions/{session_id}/spatial-overlays",
        json={
            "context_summary": "AED and patient face located.",
            "overlays": [
                {
                    "id": "face-box",
                    "kind": "box",
                    "label": "face",
                    "color": "#52e0ff",
                    "source": "gemini_robotics",
                    "box": {"ymin": 120, "xmin": 410, "ymax": 320, "xmax": 620},
                },
                {
                    "id": "aed-point",
                    "kind": "point",
                    "label": "aed",
                    "color": "#ffcc43",
                    "source": "gemini_robotics",
                    "point": {"y": 640, "x": 830},
                },
            ],
        },
    )
    assert set_response.status_code == 200
    payload = set_response.json()
    assert payload["spatial_context_summary"] == "AED and patient face located."
    assert len(payload["spatial_overlays"]) == 2
    assert payload["spatial_overlays"][0]["kind"] == "box"
    assert payload["spatial_overlays"][1]["kind"] == "point"

    clear_response = client.delete(f"/sessions/{session_id}/spatial-overlays")
    assert clear_response.status_code == 200
    cleared_payload = clear_response.json()
    assert cleared_payload["spatial_context_summary"] is None
    assert cleared_payload["spatial_overlays"] == []


def test_spatial_overlay_expert_scope_defaults_to_timed_hint() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    set_response = client.post(
        f"/sessions/{session_id}/spatial-overlays",
        json={
            "context_summary": "Expert scope: airway inspection path",
            "replace": True,
            "mode": "expert_scope",
            "overlays": [
                {
                    "id": "airway-path",
                    "kind": "trajectory",
                    "label": "airway path",
                    "source": "gemini_robotics",
                    "points": [
                        {"y": 560, "x": 510},
                        {"y": 520, "x": 500},
                        {"y": 470, "x": 485},
                    ],
                }
            ],
        },
    )
    assert set_response.status_code == 200
    payload = set_response.json()
    overlay = payload["spatial_overlays"][0]
    assert overlay["mode"] == "expert_scope"
    assert overlay["emphasis"] == "active"
    assert overlay["expires_at"] is not None


def test_spatial_overlay_expires_after_ttl() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    set_response = client.post(
        f"/sessions/{session_id}/spatial-overlays",
        json={
            "context_summary": "Temporary AED pointer",
            "replace": True,
            "ttl_ms": 10,
            "mode": "expert_scope",
            "overlays": [
                {
                    "id": "aed-point",
                    "kind": "point",
                    "label": "aed",
                    "source": "gemini_robotics",
                    "point": {"y": 640, "x": 830},
                }
            ],
        },
    )
    assert set_response.status_code == 200
    assert set_response.json()["spatial_overlays"]

    time.sleep(0.03)

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["spatial_context_summary"] is None
    assert payload["spatial_overlays"] == []


def test_spatial_overlay_rejects_invalid_ttl() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    set_response = client.post(
        f"/sessions/{session_id}/spatial-overlays",
        json={
            "ttl_ms": 0,
            "overlays": [
                {
                    "id": "aed-point",
                    "kind": "point",
                    "label": "aed",
                    "point": {"y": 640, "x": 830},
                }
            ],
        },
    )
    assert set_response.status_code == 422


def test_spatial_overlay_agent_delivery_returns_immediate_session_state() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    session_manager.update_bootstrap(
        session_id,
        call_id=None,
        call_type=None,
        agent_session_id="agent-session-1",
        stream_user_id=None,
        vision_agent_started=True,
        vision_agent_error=None,
    )

    with patch("app.routes.vision_runtime.emit_spatial_tool_result", new=AsyncMock(return_value=True)) as mocked_emit:
        set_response = client.post(
            f"/sessions/{session_id}/spatial-overlays",
            json={
                "context_summary": "Expert scope: airway inspection path",
                "replace": True,
                "mode": "expert_scope",
                "overlays": [
                    {
                        "id": "airway-path",
                        "kind": "trajectory",
                        "label": "airway path",
                        "points": [
                            {"y": 560, "x": 510},
                            {"y": 520, "x": 500},
                            {"y": 470, "x": 485},
                        ],
                    }
                ],
            },
        )

    assert set_response.status_code == 200
    payload = set_response.json()
    assert payload["spatial_context_summary"] == "Expert scope: airway inspection path"
    assert len(payload["spatial_overlays"]) == 1
    assert payload["spatial_overlays"][0]["label"] == "airway path"
    assert payload["spatial_overlays"][0]["expires_at"] is not None
    mocked_emit.assert_awaited_once()
    assert mocked_emit.await_args.kwargs["mirror_to_session"] is False


def test_spatial_overlay_request_cannot_force_client_supplied_expiry() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    set_response = client.post(
        f"/sessions/{session_id}/spatial-overlays",
        json={
            "ttl_ms": 5000,
            "mode": "expert_scope",
            "overlays": [
                {
                    "id": "aed-point",
                    "kind": "point",
                    "label": "aed",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                    "point": {"y": 640, "x": 830},
                }
            ],
        },
    )
    assert set_response.status_code == 200
    payload = set_response.json()
    expires_at = payload["spatial_overlays"][0]["expires_at"]
    assert expires_at is not None
    assert expires_at != "2099-01-01T00:00:00+00:00"


def test_spatial_tool_result_custom_event_updates_session_state() -> None:
    class FakeAgent:
        def __init__(self) -> None:
            self.events = EventManager()

    async def scenario() -> None:
        record = session_manager.create("gemini")
        agent = FakeAgent()
        processor = AgentCustomEventBridgeProcessor()
        processor.attach_agent(agent)

        agent.events.send(
            SpatialToolResultEvent(
                backend_session_id=record.session_id,
                context_summary="Patient face and AED were located.",
                ttl_ms=5000,
                mode="expert_scope",
                overlays=[
                    {
                        "id": "aed-point",
                        "kind": "point",
                        "label": "aed",
                        "point": {"y": 650, "x": 820},
                    }
                ],
            )
        )
        await agent.events.wait(timeout=1.0)

        updated = session_manager.get(record.session_id)
        assert updated is not None
        assert updated.spatial_context_summary == "Patient face and AED were located."
        assert len(updated.spatial_overlays) == 1
        assert updated.spatial_overlays[0]["label"] == "aed"
        assert updated.spatial_overlays[0]["mode"] == "expert_scope"
        assert updated.spatial_overlays[0]["expires_at"] is not None
        assert any(
            event["type"] == "agent_custom_event"
            for event in updated.debug_events
        )

        await agent.events.shutdown()

    import asyncio

    asyncio.run(scenario())


def test_agent_context_includes_active_step_tooling() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    set_response = client.post(
        f"/sessions/{session_id}/checklist/set",
        json={"protocol_id": "stroke_fast", "matched_query": "possible stroke with face droop"},
    )
    assert set_response.status_code == 200

    context = session_manager.build_agent_context(session_id)
    assert "Suggested tool: facial_droop." in context
    assert "Wait for explicit human readiness before running the tool." in context


def test_speech_guidance_search_does_not_replace_active_protocol() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    guide_response = client.post(
        f"/sessions/{session_id}/guide/search",
        json={"query": "possible stroke with face droop", "auto_activate": True},
    )
    assert guide_response.status_code == 200
    assert guide_response.json()["activated_protocol_id"] == "stroke_fast"

    outcome = search_and_optionally_activate_protocol(
        session_id,
        query="person on floor and unresponsive",
        auto_activate=True,
        allow_replace_active=False,
    )
    assert outcome.activated_title is None

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["incident_state"]["active_protocol_id"] == "stroke_fast"
    assert payload["incident_state"]["active_protocol_title"] == "Stroke FAST Check"


def test_speech_guidance_search_requires_meaningful_match() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    outcome = search_and_optionally_activate_protocol(
        session_id,
        query="help me check the patient",
        auto_activate=True,
        allow_replace_active=False,
    )
    assert outcome.activated_title is None

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["incident_state"]["active_protocol_id"] is None
    assert payload["protocol_hits"][0]["protocol_id"] == "stroke_fast"


def test_extract_retry_delay_seconds_parses_gemini_error_text() -> None:
    error_message = (
        "429 Too Many Requests. {'message': '{"
        "\"error\":{\"message\":\"Quota exceeded. Please retry in 20.938471165s.\","
        "\"details\":[{\"@type\":\"type.googleapis.com/google.rpc.RetryInfo\","
        "\"retryDelay\":\"20s\"}]}}'}"
    )

    assert _extract_retry_delay_seconds(error_message) == 21


def test_session_frame_endpoint_serves_latest_preview_frame() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]
    session_manager.update_preview_frame(session_id, b"fake-jpeg", mime_type="image/jpeg")

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    assert status_response.json()["preview_frame_available"] is True

    frame_response = client.get(f"/sessions/{session_id}/frame")
    assert frame_response.status_code == 200
    assert frame_response.content == b"fake-jpeg"
    assert frame_response.headers["content-type"].startswith("image/jpeg")


def test_facial_droop_tool_analyzes_latest_preview_frame() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]
    session_manager.update_preview_frame(session_id, b"fake-jpeg", mime_type="image/jpeg")

    prediction = {
        "droop_probability": 0.83,
        "is_drooping": True,
        "severity": "severe",
        "confidence": 0.72,
        "face_detected": True,
        "asymmetry_score": 0.071,
        "mouth_asymmetry": 0.082,
        "eye_asymmetry": 0.054,
        "brow_asymmetry": 0.063,
    }
    with patch("app.routes.predict_session_latest_frame", new=AsyncMock()) as mocked_predict:
        from app.tools.facial_droop import FacialDroopPrediction

        mocked_predict.return_value = FacialDroopPrediction(**prediction)
        response = client.post(f"/sessions/{session_id}/tools/facial-droop/latest-frame")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["source"] == "facial_droop_api"
    assert payload["is_drooping"] is True
    assert payload["severity"] == "severe"
