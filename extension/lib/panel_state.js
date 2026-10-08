// Pure reducer for the side panel. No DOM here, so node can test it.
//
// initialState() -> {
//   callId: null, band: "PASS", voice: { label: "no_signs", windows: 0 },
//   transcript: [],            // last 20 lines: { chunkIndex, text }
//   asks: [],                  // unique ask chips: { askType, reasonCode, label }
//   reasonCodes: [], suggestedLine: null, status: null,
//   seal: { state: "idle", employeeId: null, name: null, claimed: false,
//           epochsSealed: 0, epochsWithSpeech: 0 }   // Satyapan Seal chip (docs/SEAL.md)
// }
// applyEvent(state, event) -> NEW state (never mutate). Event shapes: schemas/LiveEvent.schema.json
//   "voice"      -> state.voice = { label, windows: windowIndex + 1 }   (never store score)
//   "transcript" -> append, keep last 20
//   "ask"        -> add chip if askType not present; label from ASK_LABELS
//   "band"       -> band, reasonCodes, suggestedLine
//   "status"     -> status message
//   "seal"       -> seal chip: state acquiring | sealed | not_sealed | lost, who, epoch counts
//                   (never stores z or any score; "not_sealed" is never shown as "fake")
// ASK_LABELS: A1 "New account", A2 "OTP / password", A3 "Remote-access app", A4 "Secrecy",
//             A5 "Bypass approval", A6 "Gift card / crypto", A7 "Bank details changed"

export const ASK_LABELS = {
  A1: "New account",
  A2: "OTP / password",
  A3: "Remote-access app",
  A4: "Secrecy",
  A5: "Bypass approval",
  A6: "Gift card / crypto",
  A7: "Bank details changed",
};

export const SEAL_STATES = ["idle", "acquiring", "sealed", "not_sealed", "lost"];

export function initialSeal() {
  return {
    state: "idle",
    employeeId: null,
    name: null,
    claimed: false,
    epochsSealed: 0,
    epochsWithSpeech: 0,
  };
}

export function initialState() {
  return {
    callId: null,
    band: "PASS",
    voice: { label: "no_signs", windows: 0 },
    transcript: [],
    asks: [],
    reasonCodes: [],
    suggestedLine: null,
    status: null,
    seal: initialSeal(),
  };
}

export function applyEvent(state, event) {
  if (!event || !event.type) return state;

  const next = {
    ...state,
    voice: { ...state.voice },
    transcript: [...state.transcript],
    asks: [...state.asks],
    reasonCodes: [...state.reasonCodes],
    seal: { ...(state.seal || initialSeal()) },
  };

  if (event.call_id || event.callId) {
    next.callId = event.call_id || event.callId;
  }

  switch (event.type) {
    case "voice": {
      const windowIndex = event.window_index ?? event.windowIndex ?? 0;
      next.voice = {
        label: event.label || "no_signs",
        windows: windowIndex + 1,
      };
      break;
    }

    case "transcript": {
      const chunkIndex = event.chunk_index ?? event.chunkIndex ?? next.transcript.length;
      const text = event.text || "";
      const updated = [...next.transcript, { chunkIndex, text }];
      next.transcript = updated.slice(-20);
      break;
    }

    case "ask": {
      const askType = event.ask_type || event.askType;
      const reasonCode = event.reason_code || event.reasonCode || "";
      if (askType && !next.asks.some((a) => a.askType === askType)) {
        next.asks = [
          ...next.asks,
          {
            askType,
            reasonCode,
            label: ASK_LABELS[askType] || askType,
          },
        ];
      }
      break;
    }

    case "band": {
      if (event.band) next.band = event.band;
      if (event.reason_codes || event.reasonCodes) {
        next.reasonCodes = [...(event.reason_codes || event.reasonCodes)];
      }
      if (event.suggested_line !== undefined || event.suggestedLine !== undefined) {
        next.suggestedLine = event.suggested_line ?? event.suggestedLine;
      }
      break;
    }

    case "status": {
      next.status = event.message || event.status || null;
      break;
    }

    case "seal": {
      const st = SEAL_STATES.includes(event.state) ? event.state : "idle";
      next.seal = {
        state: st,
        employeeId: event.employee_id ?? event.employeeId ?? next.seal.employeeId,
        name: event.display_name ?? event.name ?? next.seal.name,
        claimed: Boolean(event.claimed ?? next.seal.claimed),
        epochsSealed: event.epochs_sealed ?? event.epochsSealed ?? next.seal.epochsSealed,
        epochsWithSpeech:
          event.epochs_with_speech ?? event.epochsWithSpeech ?? next.seal.epochsWithSpeech,
      };
      break;
    }

    default:
      break;
  }

  return next;
}
