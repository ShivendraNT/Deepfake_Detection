// STUB(T07) — see docs/tasks/T07-extension-capture.md. Remove this marker line when done.
//
// Responsibilities (MV3 service worker):
// 1. On action click (user gesture, REQUIRED by tabCapture) on a Meet/Teams tab:
//    a. chrome.sidePanel.open({ tabId })
//    b. const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id })
//    c. ensure the offscreen document exists:
//       chrome.offscreen.createDocument({ url: "offscreen.html",
//         reasons: ["USER_MEDIA"], justification: "Score tab audio for synthetic voice" })
//    d. chrome.runtime.sendMessage({ target: "offscreen", type: "start-capture", streamId, callId })
// 2. Relay messages from offscreen -> side panel ({ type: "voice-window", ... }).
// 3. On "stop-capture": tell offscreen to stop and close it.

chrome.action.onClicked.addListener(async (_tab) => {
  console.warn("Satyapan: T07 not implemented yet");
});
