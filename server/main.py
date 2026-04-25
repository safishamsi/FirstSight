import sys
import json
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "vendor"))
sys.path.insert(0, str(BASE))

from server.detector import HeadDetector
from server.tracker import HeadTracker
from server.pipeline import HeartRatePipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = HeadDetector(
        cfg_path=str(BASE / "config/yolor_p6_head.cfg"),
        weights_path=str(BASE / "weights/yolor_head.pt"),
        device="cpu",
    )
    app.state.tracker = HeadTracker(config_path=str(BASE / "config/deep_sort.yaml"))
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    mode = websocket.query_params.get("mode", "adult")
    try:
        pipeline = HeartRatePipeline(
            detector=websocket.app.state.detector,
            tracker=websocket.app.state.tracker,
            mode=mode,
        )
    except ValueError as e:
        await websocket.close(code=1008, reason=str(e))
        return

    try:
        while True:
            data = await websocket.receive_bytes()
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            for result in pipeline.process_frame(frame):
                await websocket.send_text(json.dumps({
                    "track_id": result.track_id,
                    "bpm": result.bpm,
                    "confidence": result.confidence,
                    "alert": result.alert,
                }))
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
