from __future__ import annotations

import asyncio
import json

import httpx
import websockets


async def main() -> None:
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        create_response = await client.post("/sessions")
        create_response.raise_for_status()
        session = create_response.json()
        session_id = session["session_id"]
        print("created session", session_id)
        print("missing config", session["missing_configuration"])

        ws_url = f"ws://127.0.0.1:8000/sessions/{session_id}/stream"
        async with websockets.connect(ws_url) as websocket:
            print(await websocket.recv())
            await websocket.send(json.dumps({"type": "video_frame", "mime_type": "image/jpeg"}))
            print(await websocket.recv())
            await websocket.send(json.dumps({"type": "audio_chunk", "mime_type": "audio/pcm"}))
            print(await websocket.recv())

        session_status = await client.get(f"/sessions/{session_id}")
        session_status.raise_for_status()
        print("final status", session_status.json())


if __name__ == "__main__":
    asyncio.run(main())

