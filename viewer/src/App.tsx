import { useEffect, useMemo, useState } from "react";

type DebugEvent = {
  ts: string;
  type: string;
  payload: Record<string, unknown>;
};

type ProcessorSignal = {
  name?: string;
  score?: number;
  threshold?: number;
  over_threshold?: boolean;
  message?: string;
  person_count?: number;
};

type TranscriptTurn = {
  user_text: string;
  assistant_text: string;
};

type SessionStatus = {
  session_id: string;
  provider: string;
  status: string;
  created_at: string;
  last_event_at: string;
  connected_clients: number;
  video_frames: number;
  audio_chunks: number;
  binary_messages: number;
  text_messages: number;
  last_event_type: string | null;
  recent_events: string[];
  latest_user_transcript: string;
  latest_assistant_transcript: string;
  transcript_turns: TranscriptTurn[];
  processor_signals: Record<string, ProcessorSignal>;
  debug_events: DebugEvent[];
  preview_frame_available: boolean;
  preview_frame_updated_at: string | null;
  vision_agent_started: boolean;
  vision_agent_error: string | null;
};

const backendUrl =
  (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${backendUrl}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [selectedSession, setSelectedSession] = useState<SessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isVisible, setIsVisible] = useState<boolean>(document.visibilityState === "visible");
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  useEffect(() => {
    const onVisibilityChange = () => {
      setIsVisible(document.visibilityState === "visible");
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  useEffect(() => {
    if (!isVisible) {
      return;
    }

    let cancelled = false;

    const loadSessions = async () => {
      try {
        const nextSessions = await fetchJson<SessionStatus[]>("/sessions");
        if (cancelled) return;
        setSessions(nextSessions);
        setSelectedSessionId((current) => {
          if (!nextSessions.length) {
            return "";
          }
          if (!current) {
            return nextSessions[0].session_id;
          }
          const stillExists = nextSessions.some((session) => session.session_id === current);
          return stillExists ? current : nextSessions[0].session_id;
        });
        setError(null);
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Failed to load sessions");
        }
      }
    };

    void loadSessions();
    const interval = window.setInterval(() => void loadSessions(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [isVisible]);

  useEffect(() => {
    if (!selectedSessionId || !isVisible) {
      setSelectedSession(null);
      return;
    }

    let cancelled = false;

    const loadSession = async () => {
      try {
        const nextSession = await fetchJson<SessionStatus>(`/sessions/${selectedSessionId}`);
        if (!cancelled) {
          setSelectedSession(nextSession);
          setError(null);
        }
      } catch (nextError) {
        if (!cancelled) {
          if (nextError instanceof Error && nextError.message.startsWith("404")) {
            setSelectedSession(null);
            setSelectedSessionId((current) => (current === selectedSessionId ? "" : current));
            return;
          }
          setError(nextError instanceof Error ? nextError.message : "Failed to load session");
        }
      }
    };

    void loadSession();
    const interval = window.setInterval(() => void loadSession(), 2500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [selectedSessionId, isVisible]);

  const selectedTurn =
    selectedSession?.transcript_turns[selectedSession.transcript_turns.length - 1];

  const processorSignals = useMemo(
    () => Object.values(selectedSession?.processor_signals || {}),
    [selectedSession],
  );

  const previewFrameUrl =
    selectedSessionId && selectedSession?.preview_frame_available
      ? `${backendUrl}/sessions/${selectedSessionId}/frame?ts=${encodeURIComponent(
          selectedSession.preview_frame_updated_at || selectedSession.last_event_at,
        )}`
      : "";

  const zoomPercent = Math.round(zoomLevel * 100);

  return (
    <main className="app-shell">
      <div className="ambient-grid" />

      <section className="studio-shell">
        <header className="studio-header">
          <div className="studio-brand">
            <p className="studio-kicker">Smart Glasses Safety Runtime</p>
            <h1>Realtime CV Overlay Monitor</h1>
          </div>

          <nav className="studio-nav" aria-label="Viewer sections">
            <button className="nav-tab">VIEW</button>
            <button className="nav-tab">STREAMS</button>
            <button className="nav-tab nav-tab-active">DEBUG</button>
          </nav>

          <div className="studio-controls">
            <div className="control-block">
              <span>Backend</span>
              <input value={backendUrl} readOnly />
            </div>
            <div className="control-block">
              <span>Session</span>
              <select
                value={selectedSessionId}
                onChange={(event) => setSelectedSessionId(event.target.value)}
              >
                <option value="">No session selected</option>
                {sessions.map((session) => (
                  <option key={session.session_id} value={session.session_id}>
                    {session.session_id.slice(0, 8)} · {session.status}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </header>

        <div className="studio-body">
          <aside className="rail rail-left">
            <section className="panel panel-tight">
              <div className="section-title">
                <span className="section-label">Runtime</span>
                <strong>{selectedSession?.provider || "offline"}</strong>
              </div>
              <div className="runtime-status">
                <div className={`status-dot status-${selectedSession?.status || "idle"}`} />
                <div>
                  <strong>{selectedSession?.status || "idle"}</strong>
                  <p>
                    {selectedSession?.vision_agent_error
                      ? selectedSession.vision_agent_error
                      : selectedSession?.vision_agent_started
                        ? "Realtime bridge live"
                        : "Waiting for backend session"}
                  </p>
                </div>
              </div>
            </section>

            <section className="panel panel-tight">
              <div className="section-title">
                <span className="section-label">Sessions</span>
                <strong>{sessions.length}</strong>
              </div>
              <div className="session-list">
                {sessions.length ? (
                  sessions.map((session) => (
                    <button
                      key={session.session_id}
                      className={
                        session.session_id === selectedSessionId
                          ? "session-card session-card-active"
                          : "session-card"
                      }
                      onClick={() => setSelectedSessionId(session.session_id)}
                    >
                      <div className="session-card-top">
                        <strong>{session.session_id.slice(0, 8)}</strong>
                        <span>{session.status}</span>
                      </div>
                      <p>{session.provider.toUpperCase()} · {session.video_frames} frames</p>
                    </button>
                  ))
                ) : (
                  <p className="panel-empty">No sessions yet.</p>
                )}
              </div>
            </section>

            <section className="panel panel-tight">
              <div className="section-title">
                <span className="section-label">Last Turn</span>
                <strong>{selectedSession?.transcript_turns.length || 0}</strong>
              </div>
              <TranscriptLine
                label="Wearer"
                text={selectedTurn?.user_text || "No completed user turn yet."}
              />
              <TranscriptLine
                label="Agent"
                text={selectedTurn?.assistant_text || "No completed assistant turn yet."}
              />
            </section>
          </aside>

          <section className="canvas-column">
            <div className="canvas-panel">
              <div className="canvas-stage">
                {previewFrameUrl ? (
                  <div className="canvas-preview-shell">
                    <img
                      className="canvas-preview"
                      style={{ transform: `scale(${zoomLevel})` }}
                      src={previewFrameUrl}
                      alt="Annotated realtime preview"
                    />
                  </div>
                ) : (
                  <div className="canvas-empty">
                    <strong>Awaiting annotated frame</strong>
                    <p>
                      Start a Vision Agent Backend session with the pose overlay processor
                      enabled to see the realtime preview here.
                    </p>
                  </div>
                )}

                <div className="canvas-hud canvas-hud-top">
                  <div className="canvas-hud-group">
                    <div className="telemetry-box telemetry-box-compact">
                      <span>{selectedSession?.video_frames ? "live feed" : "idle feed"}</span>
                      <strong>{selectedSession?.video_frames || 0} frames</strong>
                    </div>
                    <div className="canvas-chip">audio {selectedSession?.audio_chunks || 0}</div>
                    <div className="canvas-chip">text {selectedSession?.text_messages || 0}</div>
                    <div className="canvas-chip">
                      event {selectedSession?.last_event_type || "none"}
                    </div>
                  </div>

                  <div className="canvas-zoom-controls" aria-label="Preview zoom controls">
                    <button
                      className="canvas-zoom-button"
                      type="button"
                      onClick={() => setZoomLevel((current) => Math.max(1, current - 0.2))}
                    >
                      -
                    </button>
                    <button
                      className="canvas-zoom-readout"
                      type="button"
                      onClick={() => setZoomLevel(1)}
                    >
                      {zoomPercent}%
                    </button>
                    <button
                      className="canvas-zoom-button"
                      type="button"
                      onClick={() => setZoomLevel((current) => Math.min(3, current + 0.2))}
                    >
                      +
                    </button>
                  </div>
                </div>

                <div className="canvas-hud canvas-hud-bottom">
                  <div className="dock-card dock-card-overlay">
                    <span className="section-label">Live Wearer</span>
                    <p>
                      {selectedSession?.latest_user_transcript ||
                        latestText(selectedSession?.debug_events, "input_transcription") ||
                        "No live user transcript."}
                    </p>
                  </div>
                  <div className="dock-card dock-card-overlay">
                    <span className="section-label">Live Agent</span>
                    <p>
                      {selectedSession?.latest_assistant_transcript ||
                        latestText(selectedSession?.debug_events, "output_transcription") ||
                        "No live assistant transcript."}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {error ? <section className="panel panel-error">{error}</section> : null}
          </section>

          <aside className="rail rail-right">
            <section className="panel">
              <div className="section-title">
                <span className="section-label">Processor Signals</span>
                <strong>{processorSignals.length}</strong>
              </div>
              {processorSignals.length ? (
                <div className="signal-list">
                  {processorSignals.map((signal) => (
                    <article key={signal.name} className="signal-card">
                      <div className="signal-header">
                        <strong>{signal.name || "processor"}</strong>
                        <span
                          className={
                            signal.over_threshold ? "pill pill-danger" : "pill pill-ok"
                          }
                        >
                          {signal.over_threshold ? "active" : "normal"}
                        </span>
                      </div>
                      <p>{signal.message || "No processor message yet."}</p>
                      <div className="metric-row">
                        <span>people {metricText(signal.person_count)}</span>
                        <span>score {metricText(signal.score)}</span>
                        <span>threshold {metricText(signal.threshold)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="panel-empty">No processor output yet.</p>
              )}
            </section>

            <section className="panel">
              <div className="section-title">
                <span className="section-label">Event Trace</span>
                <strong>{selectedSession?.debug_events.length || 0}</strong>
              </div>
              <div className="event-list">
                {(selectedSession?.debug_events || [])
                  .slice()
                  .reverse()
                  .map((event, index) => (
                    <article key={`${event.ts}-${index}`} className="event-card">
                      <div className="event-header">
                        <strong>{event.type}</strong>
                        <span>{new Date(event.ts).toLocaleTimeString()}</span>
                      </div>
                      <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                    </article>
                  ))}
              </div>
            </section>
          </aside>
        </div>
      </section>
    </main>
  );
}

function TranscriptLine({ label, text }: { label: string; text: string }) {
  return (
    <div className="transcript-line">
      <span>{label}</span>
      <p>{text}</p>
    </div>
  );
}

function latestText(events: DebugEvent[] | undefined, eventType: string): string {
  const match = [...(events || [])].reverse().find((event) => event.type === eventType);
  const text = match?.payload?.text;
  return typeof text === "string" ? text : "";
}

function metricText(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}

export default App;
