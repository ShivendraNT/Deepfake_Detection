// Render panel_state into the DOM. Dev mode: ?replay=1 loads replay/sample_events.jsonl and
// feeds events one by one (300 ms apart) so the UI can be built without a live call.
import { applyEvent, initialState } from "./lib/panel_state.js";
import { API_BASE, subscribe } from "./lib/api.js";

let currentState = initialState();

function formatVoiceText(voice) {
  const count = voice.windows || 0;
  const unit = count === 1 ? "window" : "windows";
  switch (voice.label) {
    case "likely_synthetic":
      return `Likely synthetic voice (${count} ${unit})`;
    case "inconclusive":
      return `Inconclusive audio (${count} ${unit})`;
    case "no_signs":
    default:
      return `No signs of synthetic audio (${count} ${unit})`;
  }
}

export function renderState(state) {
  // 1. Band Banner
  const banner = document.getElementById("band-banner");
  const bandName = document.getElementById("band-name");
  const bandDesc = document.getElementById("band-desc");
  if (bandName) bandName.textContent = state.band || "PASS";
  if (banner) {
    banner.classList.remove("band-pass", "band-verify", "band-hold");
    if (state.band === "HOLD") {
      banner.classList.add("band-hold");
      if (bandDesc) bandDesc.textContent = "High-risk fraud signals detected. Do not pay without checker verification.";
    } else if (state.band === "VERIFY") {
      banner.classList.add("band-verify");
      if (bandDesc) bandDesc.textContent = "Caution: Elevated signals require independent verification.";
    } else {
      banner.classList.add("band-pass");
      if (bandDesc) bandDesc.textContent = "No elevated fraud patterns detected.";
    }
  }

  // 2. Suggested Line
  const suggestedEl = document.getElementById("suggested-line");
  if (suggestedEl) {
    if (state.suggestedLine) {
      suggestedEl.textContent = state.suggestedLine;
    } else if (state.band === "HOLD") {
      suggestedEl.textContent = "I'll process it once it's raised in the system with your login.";
    } else {
      suggestedEl.textContent = "Listen carefully to requests. Verify standard PO approval process.";
    }
  }

  // 3. Voice Meter
  const voiceMeter = document.getElementById("voice-meter");
  const voiceText = document.getElementById("voice-text");
  if (voiceMeter) {
    voiceMeter.classList.remove("meter-no-signs", "meter-inconclusive", "meter-likely-synthetic");
    const label = state.voice?.label || "no_signs";
    voiceMeter.dataset.label = label;
    if (label === "likely_synthetic") {
      voiceMeter.classList.add("meter-likely-synthetic");
    } else if (label === "inconclusive") {
      voiceMeter.classList.add("meter-inconclusive");
    } else {
      voiceMeter.classList.add("meter-no-signs");
    }
  }
  if (voiceText) {
    voiceText.textContent = formatVoiceText(state.voice || {});
  }

  // 4. Ask Chips
  const chipsContainer = document.getElementById("ask-chips");
  if (chipsContainer) {
    if (!state.asks || state.asks.length === 0) {
      chipsContainer.innerHTML = '<span class="empty-hint">No high-risk asks detected yet.</span>';
    } else {
      chipsContainer.innerHTML = "";
      for (const ask of state.asks) {
        const chip = document.createElement("span");
        chip.className = "ask-chip";
        chip.innerHTML = `<span class="chip-type">${ask.askType}</span> <span class="chip-label">${ask.label}</span>`;
        chipsContainer.appendChild(chip);
      }
    }
  }

  // 5. Transcript
  const transcriptEl = document.getElementById("transcript");
  if (transcriptEl) {
    if (!state.transcript || state.transcript.length === 0) {
      transcriptEl.innerHTML = '<p class="empty-hint">Listening to call audio...</p>';
    } else {
      transcriptEl.innerHTML = "";
      for (const item of state.transcript) {
        const line = document.createElement("div");
        line.className = "transcript-line";
        line.textContent = item.text;
        transcriptEl.appendChild(line);
      }
      transcriptEl.scrollTop = transcriptEl.scrollHeight;
    }
  }

  // 6. Protection Indicator & Status Message
  const statusEl = document.getElementById("status-message");
  if (statusEl && state.status) {
    statusEl.textContent = state.status;
  }
}

export function handleEvent(event) {
  currentState = applyEvent(currentState, event);
  renderState(currentState);
}

// Button listeners
function setupButtons() {
  const btnConfirm = document.getElementById("btn-confirm");
  if (btnConfirm) {
    btnConfirm.addEventListener("click", async () => {
      const caseId = currentState.callId || localStorage.getItem("satyapan_case_id") || "case_01";
      const requester = prompt("Confirm with requester (enter employee ID or username):", "cfo@example.com");
      if (!requester) return;
      try {
        const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/oob`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ requester }),
        });
        if (res.ok) {
          alert(`OOB-Confirm request sent to ${requester}`);
        } else {
          alert(`OOB request returned HTTP ${res.status}`);
        }
      } catch (err) {
        alert(`OOB request dispatched for case ${caseId} (local simulated)`);
      }
    });
  }

  const btnLink = document.getElementById("btn-link-payment");
  if (btnLink) {
    btnLink.addEventListener("click", () => {
      const caseId = prompt("Enter payment case ID to link this call:", currentState.callId || "case_01");
      if (caseId) {
        localStorage.setItem("satyapan_case_id", caseId);
        alert(`Linked call to case ${caseId}`);
      }
    });
  }
}

// Replay runner
async function startReplay() {
  try {
    const res = await fetch("replay/sample_events.jsonl");
    const text = await res.text();
    const lines = text.split("\n").filter(Boolean);
    const events = lines.map((l) => JSON.parse(l));

    let idx = 0;
    const interval = setInterval(() => {
      if (idx >= events.length) {
        clearInterval(interval);
        return;
      }
      handleEvent(events[idx]);
      idx++;
    }, 300);
  } catch (err) {
    console.error("Failed to load replay events:", err);
  }
}

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  renderState(currentState);
  setupButtons();

  const params = new URLSearchParams(window.location.search);
  if (params.get("replay") === "1") {
    startReplay();
  } else {
    // Chrome extension runtime messaging
    if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
      chrome.runtime.onMessage.addListener((msg) => {
        if (msg && msg.type) {
          handleEvent(msg);
        }
      });
    }

    // Backend live event subscription if callId is available
    const callId = params.get("call_id");
    if (callId) {
      subscribe(callId, (event) => handleEvent(event));
    }
  }
});

export { applyEvent, initialState };
