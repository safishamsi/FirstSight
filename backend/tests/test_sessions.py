from fastapi.testclient import TestClient

from app.main import app


def test_session_websocket_tracks_ingest_counts() -> None:
    client = TestClient(app)

    create_response = client.post("/sessions")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session_ready"

        websocket.send_json({"type": "video_frame", "mime_type": "image/jpeg"})
        video_ack = websocket.receive_json()
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
