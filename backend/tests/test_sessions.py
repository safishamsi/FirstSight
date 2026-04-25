import time

from fastapi.testclient import TestClient

from app.main import app


def _receive_until_ack(websocket: object) -> tuple[list[dict[str, object]], dict[str, object]]:
    messages: list[dict[str, object]] = []
    for _ in range(6):
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
