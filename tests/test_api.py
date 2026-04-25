"""
FastAPI endpoint tests using TestClient (no ONNX model required for most tests).
"""
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_jpeg_bytes(width=100, height=100) -> bytes:
    arr = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def mock_model():
    m = MagicMock()
    m.threshold = 0.5
    m.sensitivity = 0.90
    m.specificity = 0.85
    m.predict.return_value = {
        "droop_probability": 0.83,
        "is_drooping": True,
        "severity": "severe",
        "confidence": 0.72,
        "face_detected": True,
    }
    return m


@pytest.fixture
def client(mock_model):
    from app.main import app, _model
    import app.main as main_module

    with patch.object(main_module, "_model", mock_model):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c, mock_model


def test_health_endpoint(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_predict_returns_valid_schema(client):
    c, _ = client
    jpeg = _make_jpeg_bytes()
    resp = c.post("/predict", files={"file": ("face.jpg", jpeg, "image/jpeg")})
    assert resp.status_code == 200
    data = resp.json()
    assert "droop_probability" in data
    assert "is_drooping" in data
    assert "severity" in data
    assert "confidence" in data
    assert "face_detected" in data


def test_predict_unsupported_content_type(client):
    c, _ = client
    resp = c.post("/predict", files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")})
    assert resp.status_code == 422


def test_predict_no_face_detected(client):
    c, mock = client
    mock.predict.return_value = {
        "droop_probability": None,
        "is_drooping": None,
        "severity": None,
        "confidence": None,
        "face_detected": False,
    }
    jpeg = _make_jpeg_bytes()
    resp = c.post("/predict", files={"file": ("noface.jpg", jpeg, "image/jpeg")})
    assert resp.status_code == 200
    assert resp.json()["face_detected"] is False


def test_threshold_endpoint(client):
    c, mock = client
    resp = c.get("/threshold")
    assert resp.status_code == 200
    data = resp.json()
    assert "threshold" in data
    assert "sensitivity" in data
    assert "specificity" in data
    assert 0.0 <= data["threshold"] <= 1.0
