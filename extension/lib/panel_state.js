// STUB(T10) — see docs/tasks/T10-extension-sidepanel.md. Remove this marker line when done.
//
// Pure reducer for the side panel. No DOM here, so node can test it.
//
// initialState() -> {
//   callId: null, band: "PASS", voice: { label: "no_signs", windows: 0 },
//   transcript: [],            // last 20 lines: { chunkIndex, text }
//   asks: [],                  // unique ask chips: { askType, reasonCode, label }
//   reasonCodes: [], suggestedLine: null, status: null
// }
// applyEvent(state, event) -> NEW state (never mutate). Event shapes: schemas/LiveEvent.schema.json
//   "voice"      -> state.voice = { label, windows: windowIndex + 1 }   (never store score)
//   "transcript" -> append, keep last 20
//   "ask"        -> add chip if askType not present; label from ASK_LABELS
//   "band"       -> band, reasonCodes, suggestedLine
//   "status"     -> status message
// ASK_LABELS: A1 "New account", A2 "OTP / password", A3 "Remote-access app", A4 "Secrecy",
//             A5 "Bypass approval", A6 "Gift card / crypto", A7 "Bank details changed"

export const ASK_LABELS = {};

export function initialState() {
  throw new Error("T10 not implemented");
}

export function applyEvent(_state, _event) {
  throw new Error("T10 not implemented");
}
