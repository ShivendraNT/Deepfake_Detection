chrome.action.onClicked.addListener(async (tab) => {
    // 1. User gesture rule: call sidePanel.open and tabCapture before any await
    chrome.sidePanel.open({ tabId: tab.id });
    const streamIdPromise = new Promise(resolve => {
        chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id }, resolve);
    });

    const session = await chrome.storage.session.get(['activeCapture']);
    if (session.activeCapture && session.activeCapture.tabId === tab.id) {
        // Toggle off if clicking same tab
        await stopCapture();
        return;
    }

    const streamId = await streamIdPromise;
    if (!streamId) {
        console.error("No streamId generated:", chrome.runtime.lastError);
        return;
    }

    if (session.activeCapture) {
        // Stop the old one if capturing a different tab
        await stopCapture();
    }

    await ensureOffscreenDocument();

    const callId = "call_" + Date.now();
    await chrome.storage.session.set({ activeCapture: { callId, tabId: tab.id } });

    await chrome.runtime.sendMessage({
        target: "offscreen",
        type: "start-capture",
        streamId,
        callId
    });
});

async function ensureOffscreenDocument() {
    const existingContexts = await chrome.runtime.getContexts({
        contextTypes: ['OFFSCREEN_DOCUMENT'],
        documentUrls: [chrome.runtime.getURL('offscreen.html')]
    });

    if (existingContexts.length > 0) return;

    await chrome.offscreen.createDocument({
        url: 'offscreen.html',
        reasons: ['USER_MEDIA'],
        justification: 'Score tab audio for synthetic voice'
    });
}

async function stopCapture() {
    const session = await chrome.storage.session.get(['activeCapture']);
    if (!session.activeCapture) return;

    await chrome.storage.session.remove(['activeCapture']);
    try {
        await chrome.runtime.sendMessage({ target: "offscreen", type: "stop-capture" });
    } catch (e) {
        // Ignore error if offscreen is already dead
    }
    await closeOffscreenDocument();
}

async function closeOffscreenDocument() {
    const existingContexts = await chrome.runtime.getContexts({
        contextTypes: ['OFFSCREEN_DOCUMENT'],
        documentUrls: [chrome.runtime.getURL('offscreen.html')]
    });
    if (existingContexts.length > 0) {
        await chrome.offscreen.closeDocument();
    }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "stop-capture") {
        stopCapture();
    } else if (message.type === "voice-window") {
        // Relay offscreen -> panel using the D4 shape (LiveEvent shape)
        const liveEvent = {
            type: "voice",
            call_id: message.callId,
            window_index: message.windowIndex,
            label: message.label,
            consecutive_over_hi: message.consecutiveOverHi,
            calibrated: message.calibrated
        };
        chrome.runtime.sendMessage(liveEvent).catch(() => {});
    } else if (message.type === "status") {
        // Relay status to side panel
        chrome.runtime.sendMessage(message).catch(() => {});
    }
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
    const session = await chrome.storage.session.get(['activeCapture']);
    if (session.activeCapture && session.activeCapture.tabId === tabId) {
        await stopCapture();
    }
});
