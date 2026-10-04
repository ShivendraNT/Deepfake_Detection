// PRE-IMPLEMENTED. Tiny client for the local backend (FastAPI on 127.0.0.1:8000).
export const API_BASE = "http://127.0.0.1:8000";

export async function startCall(callId) {
  const r = await fetch(`${API_BASE}/live/${encodeURIComponent(callId)}/start`, { method: "POST" });
  return r.json();
}

export async function postChunk(callId, chunkIndex, blob) {
  const fd = new FormData();
  fd.append("chunk_index", String(chunkIndex));
  fd.append("audio", blob, `chunk-${chunkIndex}.webm`);
  const r = await fetch(`${API_BASE}/live/${encodeURIComponent(callId)}/chunk`, { method: "POST", body: fd });
  return r.json();
}

export async function postVoiceWindows(callId, windows) {
  const r = await fetch(`${API_BASE}/live/${encodeURIComponent(callId)}/voice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(windows),
  });
  return r.json();
}

export function subscribe(callId, onEvent) {
  const es = new EventSource(`${API_BASE}/live/${encodeURIComponent(callId)}/events`);
  es.onmessage = (m) => onEvent(JSON.parse(m.data));
  return () => es.close();
}
