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
});

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

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "analyzeText") {
        sendResponse(await analyzeText(message.text));
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
