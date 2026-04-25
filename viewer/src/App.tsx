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
  transcript_turns: Array<{
    user_text: string;
    assistant_text: string;
  }>;
  processor_signals: Record<string, ProcessorSignal>;
  debug_events: DebugEvent[];
  vision_agent_started: boolean;
  vision_agent_error: string | null;
};

const backendUrl = (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

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

  useEffect(() => {
    let cancelled = false;

    const loadSessions = async () => {
      try {
        const nextSessions = await fetchJson<SessionStatus[]>("/sessions");
        if (cancelled) {
          return;
        }
        setSessions(nextSessions);
        setError(null);
        setSelectedSessionId((current) => current || nextSessions[0]?.session_id || "");
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Failed to load sessions");
        }
      }
    };

    void loadSessions();
    const interval = window.setInterval(() => void loadSessions(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!selectedSessionId) {
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
          setError(nextError instanceof Error ? nextError.message : "Failed to load session");
        }
      }
    };

    void loadSession();
    const interval = window.setInterval(() => void loadSession(), 1000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [selectedSessionId]);

  const processorSignals = useMemo(
    () => Object.values(selectedSession?.processor_signals || {}),
    [selectedSession],
  );
  const lastCompletedTurn =
    selectedSession?.transcript_turns[selectedSession.transcript_turns.length - 1];

  return (
    <main className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">DroopDetection</p>
          <h1>Vision Agent Debug Dashboard</h1>
          <p className="subtitle">
            Live backend sessions, transcripts, and processor state.
          </p>
        </div>
        <div className="hero-controls">
          <label className="field">
            <span>Backend</span>
            <input value={backendUrl} readOnly />
          </label>
          <label className="field">
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
          </label>
        </div>
      </header>

      {error ? <section className="panel error">{error}</section> : null}

      <section className="grid stats-grid">
        <StatCard label="Provider" value={selectedSession?.provider || "idle"} />
        <StatCard label="Status" value={selectedSession?.status || "idle"} />
        <StatCard label="Connected" value={String(selectedSession?.connected_clients || 0)} />
        <StatCard label="Video Frames" value={String(selectedSession?.video_frames || 0)} />
        <StatCard label="Audio Chunks" value={String(selectedSession?.audio_chunks || 0)} />
        <StatCard label="Last Event" value={selectedSession?.last_event_type || "none"} />
      </section>

      <section className="grid content-grid">
        <section className="panel">
          <div className="panel-header">
            <h2>Transcripts</h2>
            <span className="muted">
              {selectedSession?.vision_agent_error
                ? `bridge error: ${selectedSession.vision_agent_error}`
                : selectedSession?.vision_agent_started
                  ? "vision runtime started"
                  : "session adapter only"}
            </span>
          </div>
          <TranscriptBlock
            label="Last User"
            text={lastCompletedTurn?.user_text || "No completed user turn yet."}
          />
          <TranscriptBlock
            label="Last Assistant"
            text={lastCompletedTurn?.assistant_text || "No completed assistant turn yet."}
          />
          <TranscriptBlock
            label="Live User"
            text={selectedSession?.latest_user_transcript || latestText(selectedSession?.debug_events, "input_transcription")}
          />
          <TranscriptBlock
            label="Live Assistant"
            text={selectedSession?.latest_assistant_transcript || latestText(selectedSession?.debug_events, "output_transcription")}
          />
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Processor Signals</h2>
            <span className="muted">{processorSignals.length || 0} active</span>
          </div>
          {processorSignals.length ? (
            <div className="signal-list">
              {processorSignals.map((signal) => (
                <article key={signal.name} className="signal-card">
                  <div className="signal-topline">
                    <strong>{signal.name || "processor"}</strong>
                    <span className={signal.over_threshold ? "pill danger" : "pill ok"}>
                      {signal.over_threshold ? "over threshold" : "normal"}
                    </span>
                  </div>
                  <p>{signal.message || "No processor message yet."}</p>
                  <div className="signal-metrics">
                    <span>score: {formatMetric(signal.score)}</span>
                    <span>threshold: {formatMetric(signal.threshold)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="empty">No processor output yet.</p>
          )}
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Recent Events</h2>
            <span className="muted">{selectedSession?.debug_events.length || 0} retained</span>
          </div>
          <div className="event-list">
            {(selectedSession?.debug_events || []).slice().reverse().map((event, index) => (
              <article key={`${event.ts}-${index}`} className="event-row">
                <div className="event-meta">
                  <strong>{event.type}</strong>
                  <span>{new Date(event.ts).toLocaleTimeString()}</span>
                </div>
                <pre>{JSON.stringify(event.payload, null, 2)}</pre>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function TranscriptBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="transcript-block">
      <span>{label}</span>
      <p>{text || "No transcript yet."}</p>
    </div>
  );
}

function latestText(events: DebugEvent[] | undefined, eventType: string): string {
  const match = [...(events || [])].reverse().find((event) => event.type === eventType);
  const text = match?.payload?.text;
  return typeof text === "string" ? text : "";
}

function formatMetric(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}

export default App;
