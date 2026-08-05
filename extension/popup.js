/* Popup: server status, a paste-text fallback, and the API address setting.
 *
 * The popup never calls the API itself — it hands work to the service worker,
 * which owns every network call (see background.js). */

const DEFAULT_API = "http://127.0.0.1:5000";

const statusBox = document.getElementById("status");
const statusText = document.getElementById("status-text");
const textArea = document.getElementById("text");
const goButton = document.getElementById("go");
const apiInput = document.getElementById("api");
const savedNote = document.getElementById("saved");

function setStatus(kind, message) {
  statusBox.className = `status ${kind}`;
  statusText.textContent = message;
}

/* ── Server status ────────────────────────────────────────────── */

(async function check() {
  const stored = await chrome.storage.sync.get("apiBase");
  apiInput.value = stored.apiBase || DEFAULT_API;

  let response;

  try {
    response = await chrome.runtime.sendMessage({ type: "health" });
  } catch (error) {
    setStatus("bad", "Extension worker not responding.");
    return;
  }

  if (!response || !response.ok) {
    setStatus("bad", "Server not running. Start: python app/server.py");
    goButton.disabled = true;
    return;
  }

  if (!response.data.model_ready) {
    setStatus("bad", "Server up, but the model isn't trained yet.");
    goButton.disabled = true;
    return;
  }

  const ocr = response.data.ocr_backend
    ? "text + images"
    : "text only (no OCR backend)";

  setStatus("ok", `Connected — ${ocr}.`);
})();

/* ── Analyze pasted text ──────────────────────────────────────── */

goButton.addEventListener("click", async () => {
  const text = textArea.value.trim();

  if (!text) {
    textArea.focus();
    return;
  }

  // The overlay lives in the page, so hand the text to the active tab and
  // close — the result appears in the same panel as every other entry point.
  const response = await chrome.runtime.sendMessage({
    type: "openPanelWithText",
    text: text,
  });

  if (response && response.ok) {
    window.close();
  } else {
    setStatus("bad", "Couldn't reach this tab. Try a normal web page.");
  }
});

textArea.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") goButton.click();
});

/* ── Hover detection toggle ───────────────────────────────────── */

/* Off by default: the extension does nothing on its own while someone is just
 * reading. The toggle arms hover detection everywhere; content scripts pick
 * the change up live through chrome.storage.onChanged — no reload needed. */

const hoverToggle = document.getElementById("hover-toggle");

chrome.storage.sync.get({ hoverEnabled: false }).then((stored) => {
  hoverToggle.checked = stored.hoverEnabled;
});

hoverToggle.addEventListener("change", () => {
  chrome.storage.sync.set({ hoverEnabled: hoverToggle.checked });
});

/* ── Pick an ad on the page ───────────────────────────────────── */

document.getElementById("pick").addEventListener("click", async () => {
  const response = await chrome.runtime.sendMessage({ type: "startPicking" });

  if (response && response.ok) {
    // Close so the page is unobstructed while the user hovers.
    window.close();
  } else {
    setStatus("bad", "Can't pick on this tab. Try a normal web page.");
  }
});

/* ── API address ──────────────────────────────────────────────── */

let saveTimer = null;

apiInput.addEventListener("input", () => {
  clearTimeout(saveTimer);

  saveTimer = setTimeout(async () => {
    const value = apiInput.value.trim() || DEFAULT_API;
    await chrome.storage.sync.set({ apiBase: value });

    savedNote.hidden = false;
    setTimeout(() => {
      savedNote.hidden = true;
    }, 1500);
  }, 400);
});
