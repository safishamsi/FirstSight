import { useCallback, useEffect, useRef, useState } from "react";

const FRAME_FPS = 10;
const FRAME_INTERVAL_MS = 1000 / FRAME_FPS;
const JPEG_QUALITY = 0.7;
const SIGNAL_POLL_MS = 2500;
const WARMUP_SECONDS = 10;

type StreamStatus = "idle" | "connecting" | "streaming" | "error";

type ProcessorSignal = {
  name?: string;
  score?: number;
  threshold?: number;
  over_threshold?: boolean;
  message?: string;
  person_count?: number;
};

type SessionStatus = {
  processor_signals: Record<string, ProcessorSignal>;
};

interface Props {
  backendUrl: string;
}

export function CameraStream({ backendUrl }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const streamStartRef = useRef<number | null>(null);

  const [status, setStatus] = useState<StreamStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frameCount, setFrameCount] = useState(0);
  const [signals, setSignals] = useState<ProcessorSignal[]>([]);
  const [elapsed, setElapsed] = useState(0);

  const stopAll = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    streamStartRef.current = null;
    setStatus("idle");
    setFrameCount(0);
    setSessionId(null);
    setSignals([]);
    setElapsed(0);
  }, []);

  useEffect(() => () => stopAll(), [stopAll]);

  const startSignalPolling = useCallback(
    (sid: string) => {
      const tick = async () => {
        try {
          const res = await fetch(`${backendUrl}/sessions/${sid}`);
          if (!res.ok) return;
          const data = (await res.json()) as SessionStatus;
          setSignals(Object.values(data.processor_signals || {}));
        } catch {
          // ignore transient errors
        }
        if (streamStartRef.current !== null) {
          setElapsed(Math.floor((Date.now() - streamStartRef.current) / 1000));
        }
      };
      void tick();
      pollRef.current = setInterval(() => void tick(), SIGNAL_POLL_MS);
    },
    [backendUrl],
  );

  const start = useCallback(async () => {
    setError(null);
    setStatus("connecting");

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
        audio: false,
      });
      streamRef.current = mediaStream;

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play();
      }

      const res = await fetch(`${backendUrl}/sessions`, { method: "POST" });
      if (!res.ok) throw new Error(`Session create failed: ${res.status}`);
      const session = (await res.json()) as { session_id: string };
      setSessionId(session.session_id);

      const wsUrl = backendUrl.replace(/^http/, "ws");
      const ws = new WebSocket(`${wsUrl}/sessions/${session.session_id}/stream`);
      wsRef.current = ws;

      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("WebSocket connection failed"));
        ws.onclose = (e) => {
          if (e.code !== 1000) reject(new Error(`WebSocket closed: ${e.code}`));
        };
      });

      // After streaming starts, treat unexpected WS close as an error
      ws.onclose = (e) => {
        if (e.code !== 1000) {
          setError(`Connection lost (${e.code}) — click Start Camera to reconnect`);
          setStatus("error");
          stopAll();
        }
      };

      ws.send(JSON.stringify({ setup: {} }));

      const canvas = canvasRef.current!;
      const video = videoRef.current!;
      let localCount = 0;

      streamStartRef.current = Date.now();

      intervalRef.current = setInterval(() => {
        if (ws.readyState !== WebSocket.OPEN) return;
        if (!video.videoWidth) return;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d")!;
        ctx.drawImage(video, 0, 0);

        const dataUrl = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
        const base64 = dataUrl.split(",")[1];

        ws.send(JSON.stringify({ realtimeInput: { video: { data: base64 } } }));

        localCount += 1;
        setFrameCount(localCount);
      }, FRAME_INTERVAL_MS);

      setStatus("streaming");
      startSignalPolling(session.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
      stopAll();
    }
  }, [backendUrl, stopAll, startSignalPolling]);

  const isWarmingUp = status === "streaming" && elapsed < WARMUP_SECONDS;
  const warmupPct = Math.min(100, Math.round((elapsed / WARMUP_SECONDS) * 100));

  return (
    <div className="camera-stream-panel">
      <div className="camera-header">
        <div className="section-title">
          <span className="section-label">Webcam Stream</span>
          {sessionId && <code className="session-chip">{sessionId.slice(0, 8)}</code>}
        </div>
        <div className="camera-controls">
          {status === "idle" || status === "error" ? (
            <button className="btn-start" onClick={start}>
              Start Camera
            </button>
          ) : (
            <button className="btn-stop" onClick={stopAll}>
              Stop
            </button>
          )}
          <span className={`status-badge status-badge-${status}`}>{status}</span>
          {status === "streaming" && (
            <span className="frame-counter">{frameCount} frames</span>
          )}
        </div>
      </div>

      {error && <p className="camera-error">{error}</p>}

      <div className="camera-body">
        <div className="camera-video-wrap">
          <canvas ref={canvasRef} style={{ display: "none" }} />
          <video
            ref={videoRef}
            className="camera-video"
            muted
            playsInline
            style={{
              display: status === "streaming" || status === "connecting" ? "block" : "none",
            }}
          />
          {status === "idle" && (
            <div className="camera-placeholder">
              <strong>Camera not started</strong>
              <p>
                Click <em>Start Camera</em> to stream your webcam to the backend.
                The face droop and heart rate processors will update in real time.
              </p>
            </div>
          )}
        </div>

        <aside className="camera-signals-rail">
          <div className="section-title" style={{ marginBottom: "0.75rem" }}>
            <span className="section-label">Model Results</span>
            {status === "streaming" && (
              <span style={{ fontSize: "0.7rem", color: "#718096" }}>{elapsed}s</span>
            )}
          </div>

          {isWarmingUp ? (
            <div className="camera-warmup">
              <div className="warmup-label">Warming up processors…</div>
              <div className="warmup-bar-track">
                <div className="warmup-bar-fill" style={{ width: `${warmupPct}%` }} />
              </div>
              <div className="warmup-pct">{warmupPct}%</div>
            </div>
          ) : status !== "streaming" ? (
            <p className="panel-empty">Start camera to see model output.</p>
          ) : signals.length === 0 ? (
            <p className="panel-empty">No processor signals yet.</p>
          ) : (
            <div className="signal-list">
              {signals.map((signal) => (
                <SignalCard key={signal.name} signal={signal} />
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function SignalCard({ signal }: { signal: ProcessorSignal }) {
  const alert = signal.over_threshold === true;
  const label = signal.name?.replace(/_processor$/, "").replace(/_/g, " ") ?? "processor";

  return (
    <article className="signal-card">
      <div className="signal-header">
        <strong style={{ textTransform: "capitalize" }}>{label}</strong>
        <span className={alert ? "pill pill-danger" : "pill pill-ok"}>
          {alert ? "ALERT" : "normal"}
        </span>
      </div>
      {signal.message && <p>{signal.message}</p>}
      <div className="metric-row">
        {signal.person_count !== undefined && (
          <span>people {signal.person_count}</span>
        )}
        {signal.score !== undefined && (
          <span>score {signal.score.toFixed(2)}</span>
        )}
        {signal.threshold !== undefined && (
          <span>threshold {signal.threshold.toFixed(2)}</span>
        )}
      </div>
    </article>
  );
}
