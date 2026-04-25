from fastapi.testclient import TestClient

from app.main import app


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


def test_session_websocket_tracks_ingest_counts() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session_ready"

        websocket.send_json({"type": "video_frame", "mime_type": "image/jpeg"})
        first_video_message = websocket.receive_json()
        if "serverContent" in first_video_message:
            assert "Possible stroke check started" in first_video_message["serverContent"]["outputTranscription"]["text"]
            video_ack = websocket.receive_json()
        else:
            video_ack = first_video_message
        assert video_ack["video_frames"] == 1

        websocket.send_json({"type": "audio_chunk", "mime_type": "audio/pcm"})
        audio_ack = websocket.receive_json()
        assert audio_ack["audio_chunks"] == 1

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    payload = status_response.json()
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
        assert "Vision agent backend connected" in welcome["serverContent"]["outputTranscription"]["text"]

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
        demo_guidance = websocket.receive_json()
        assert "Possible stroke check started" in demo_guidance["serverContent"]["outputTranscription"]["text"]
        video_ack = websocket.receive_json()
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
        audio_ack = websocket.receive_json()
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
        server_content = websocket.receive_json()
        assert server_content["serverContent"]["inputTranscription"]["text"] == "help me check the patient"
        assert "Backend adapter received" in server_content["serverContent"]["outputTranscription"]["text"]

        text_ack = websocket.receive_json()
        assert text_ack["received_type"] == "text_message"

    status_response = client.get(f"/sessions/{session_id}")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["video_frames"] == 1
    assert payload["audio_chunks"] == 1
    assert payload["text_messages"] >= 2
