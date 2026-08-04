/* AdInsight service worker.
 *
 * Owns two things the content script can't do itself:
 *
 *   1. Network. A content script's fetch is bound by the host page's CORS
 *      rules, so calls to the local API (and to ad-image URLs on third-party
 *      CDNs) are made here, where the extension's host_permissions apply.
 *   2. Context menus, which are a background-only API.
 */

const DEFAULT_API = "http://127.0.0.1:5000";

const MENU_TEXT = "adinsight-analyze-selection";
const MENU_IMAGE = "adinsight-analyze-image";
const MENU_CAPTURE = "adinsight-capture-region";

/* ── Settings ─────────────────────────────────────────────────── */

async function apiBase() {
  const stored = await chrome.storage.sync.get("apiBase");
  return (stored.apiBase || DEFAULT_API).replace(/\/+$/, "");
}

/* ── Context menus ────────────────────────────────────────────── */

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_TEXT,
      title: 'Analyze this ad text with AdInsight',
      contexts: ["selection"],
    });

    chrome.contextMenus.create({
      id: MENU_IMAGE,
      title: "Analyze this ad image with AdInsight",
      contexts: ["image"],
    });

    // Screenshot path: works on ads a content script cannot read at all --
    // cross-origin iframes and playing video ads. Capturing the tab grabs
    // whatever is rendered at that moment (a video's current frame included),
    // and OCR does not care where the pixels came from. Offered on every
    // context, because the ads that need it are precisely the ones we cannot
    // recognise as ads from the outside.
    chrome.contextMenus.create({
      id: MENU_CAPTURE,
      title: "Analyze this ad by screenshot (video / iframe ads)",
      contexts: ["all"],
    });
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab || tab.id === undefined) return;

  if (info.menuItemId === MENU_TEXT && info.selectionText) {
    chrome.tabs.sendMessage(tab.id, {
      type: "analyze",
      payload: { text: info.selectionText },
    });
  }

  if (info.menuItemId === MENU_IMAGE && info.srcUrl) {
    chrome.tabs.sendMessage(tab.id, {
      type: "analyze",
      payload: { imageUrl: info.srcUrl },
    });
  }

  if (info.menuItemId === MENU_CAPTURE) {
    // The content script tracked where the right-click landed and which ad
    // block sits there; it answers with that region and shows its busy panel.
    chrome.tabs.sendMessage(tab.id, { type: "captureRequested" });
  }
});

/* ── Region capture (video / iframe ads) ──────────────────────── */

/**
 * Screenshot the visible tab and crop to `region` (viewport CSS pixels).
 *
 * The capture is in device pixels, so the region is scaled by the DPR the
 * content script measured. Clamping matters: an ad half scrolled off screen
 * yields a rect partly outside the bitmap, and drawImage with negative
 * coordinates silently distorts instead of failing.
 */
/* Two-phase on purpose. Phase 1 (screenshot + crop) runs while the content
 * script keeps its own panel hidden, so our UI can never photograph itself
 * into the ad; it is fast (~100ms) and returns a handle. The content script
 * then shows its busy panel and asks for phase 2, the slow OCR + model call,
 * by handle. */

let _lastCapture = null;

// Animated and video creatives rotate their text, so one frame can catch a
// transition and miss the message entirely. Photograph the slot a few times
// and let the server merge the unique lines. Static ads just contribute the
// same lines each frame and dedupe back to one copy.
const BURST_FRAMES = 3;
const BURST_GAP_MS = 1200;

async function captureOneFrame(windowId, region) {
  const dataUrl = await chrome.tabs.captureVisibleTab(windowId, {
    format: "png",
  });

  const response = await fetch(dataUrl);
  const bitmap = await createImageBitmap(await response.blob());

  // The capture is in device pixels; the region arrives in CSS pixels with the
  // DPR the content script measured. Clamp after scaling: an ad half scrolled
  // off screen yields a rect partly outside the bitmap, and drawImage with
  // out-of-range coordinates distorts silently instead of failing.
  const scale = region.devicePixelRatio || 1;

  const left = Math.max(0, Math.round(region.left * scale));
  const top = Math.max(0, Math.round(region.top * scale));
  let width = Math.round(region.width * scale);
  let height = Math.round(region.height * scale);

  width = Math.min(width, bitmap.width - left);
  height = Math.min(height, bitmap.height - top);

  if (width < 40 || height < 40) {
    throw new Error("That region is too small to read. Scroll the ad fully into view.");
  }

  const canvas = new OffscreenCanvas(width, height);
  canvas.getContext("2d").drawImage(bitmap, left, top, width, height, 0, 0, width, height);

  return canvas.convertToBlob({ type: "image/png" });
}

async function captureRegion(tabId, region) {
  const tab = await chrome.tabs.get(tabId);

  const frames = Math.max(1, region.frames || BURST_FRAMES);
  const gap = region.gapMs === undefined ? BURST_GAP_MS : region.gapMs;

  const blobs = [];

  for (let index = 0; index < frames; index += 1) {
    blobs.push(await captureOneFrame(tab.windowId, region));

    if (index < frames - 1 && gap > 0) {
      await new Promise((resolve) => setTimeout(resolve, gap));
    }
  }

  _lastCapture = { blobs, tabId };

  return { ok: true, captured: true, frames: blobs.length };
}

async function analyzeCapture(tabId) {
  if (!_lastCapture || _lastCapture.tabId !== tabId) {
    // MV3 workers can be torn down between messages; the blobs die with them.
    throw new Error("The capture expired. Right-click the ad and try again.");
  }

  const { blobs } = _lastCapture;
  _lastCapture = null;

  const form = new FormData();
  blobs.forEach((blob, index) => {
    form.append("image", blob, `ad-frame-${index + 1}.png`);
  });

  const apiResponse = await fetch(`${await apiBase()}/api/analyze`, {
    method: "POST",
    body: form,
  });

  return { ok: apiResponse.ok, data: await apiResponse.json() };
}

/* ── API calls ────────────────────────────────────────────────── */

async function analyzeText(text) {
  const response = await fetch(`${await apiBase()}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text }),
  });

  return { ok: response.ok, data: await response.json() };
}

async function analyzeImage(imageUrl) {
  // Data URLs and blob: URLs can't be re-fetched from the worker, but a data
  // URL already carries its bytes, so convert it directly.
  const imageResponse = await fetch(imageUrl);

  if (!imageResponse.ok) {
    throw new Error("Couldn't download that image from the page.");
  }

  const blob = await imageResponse.blob();

  if (!blob.type.startsWith("image/")) {
    throw new Error("That link isn't an image.");
  }

  const form = new FormData();
  form.append("image", blob, "ad-image.png");

  const response = await fetch(`${await apiBase()}/api/analyze`, {
    method: "POST",
    body: form,
  });

  return { ok: response.ok, data: await response.json() };
}

async function health() {
  const response = await fetch(`${await apiBase()}/api/health`);
  return { ok: response.ok, data: await response.json() };
}

/* ── Message routing ──────────────────────────────────────────── */

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "analyzeText") {
        sendResponse(await analyzeText(message.text));
      } else if (message.type === "captureRegion") {
        // Phase 1, from the content script (which knows the ad's screen rect).
        if (!sender.tab || sender.tab.id === undefined) {
          sendResponse({ ok: false, error: "No tab to capture." });
        } else {
          sendResponse(await captureRegion(sender.tab.id, message.region));
        }
      } else if (message.type === "analyzeCapture") {
        // Phase 2: OCR + model on the blob captured a moment ago.
        if (!sender.tab || sender.tab.id === undefined) {
          sendResponse({ ok: false, error: "No tab to capture." });
        } else {
          sendResponse(await analyzeCapture(sender.tab.id));
        }
      } else if (message.type === "analyzeImage") {
        sendResponse(await analyzeImage(message.imageUrl));
      } else if (message.type === "health") {
        sendResponse(await health());
      } else if (message.type === "startPicking") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (tab && tab.id !== undefined) {
          chrome.tabs.sendMessage(tab.id, { type: "startPicking" });
          sendResponse({ ok: true });
        } else {
          sendResponse({ ok: false, error: "No active tab." });
        }
      } else if (message.type === "openPanelWithText") {
        // From the popup: push text into the active tab's overlay.
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (tab && tab.id !== undefined) {
          chrome.tabs.sendMessage(tab.id, {
            type: "analyze",
            payload: { text: message.text },
          });
          sendResponse({ ok: true });
        } else {
          sendResponse({ ok: false, error: "No active tab." });
        }
      } else {
        sendResponse({ ok: false, error: `Unknown message: ${message.type}` });
      }
    } catch (error) {
      // A failed fetch to localhost almost always means the server isn't up.
      sendResponse({
        ok: false,
        error:
          error && error.message === "Failed to fetch"
            ? "Can't reach the AdInsight server. Start it with: python app/server.py"
            : String(error && error.message ? error.message : error),
      });
    }
  })();

  // Keeps the message channel open for the async response above.
  return true;
});
