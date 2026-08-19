/* Test harness: a jsdom page plus a fake `chrome`, so content.js and
 * background.js can run outside a browser.
 *
 * Two jsdom gaps have to be papered over:
 *
 *   - `innerText` isn't implemented. content.js uses it everywhere to decide
 *     whether a block holds enough text, so it's shimmed to textContent.
 *   - jsdom does no layout, so `getBoundingClientRect` returns zeros. Tests
 *     that care about geometry stub it per element via `setRect`.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const HERE = dirname(fileURLToPath(import.meta.url));
export const EXTENSION_DIR = join(HERE, "..");

export function readSource(name) {
  return readFileSync(join(EXTENSION_DIR, name), "utf8");
}

/** A page with a sponsored ad block and ordinary article text. */
export const PAGE_HTML = `<!DOCTYPE html><html><body>
  <article>
    <h1>What researchers know about memory</h1>
    <p id="prose">Mild forgetfulness is a normal part of aging, and researchers
      have spent decades separating ordinary change from early signs of
      something more serious.</p>
    <div class="ad-slot" id="ad">
      <p class="sponsored">Sponsored</p>
      <h3>NeuroVital Labs</h3>
      <p class="copy">FINAL HOURS: Doctor-recommended MemoryMax Pro reverses
        memory loss in 14 days. Only 7 bottles left.</p>
      <a href="https://example.com/buy" id="cta">Shop Now</a>
    </div>
    <div id="tiny" class="ad-slot">Ad</div>
  </article>
</body></html>`;

/** Force an element's layout box, since jsdom computes none. */
export function setRect(element, rect) {
  const box = {
    x: rect.left,
    y: rect.top,
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    right: rect.left + rect.width,
    bottom: rect.top + rect.height,
    toJSON() {
      return this;
    },
  };

  element.getBoundingClientRect = () => box;
  return box;
}

/**
 * Build the environment content.js expects.
 *
 * `respond` receives the message content.js sends and returns the fake API
 * reply, standing in for background.js.
 */
export function createEnvironment({ html = PAGE_HTML, respond, hoverEnabled = true } = {}) {
  const dom = new JSDOM(html, {
    runScripts: "outside-only",
    pretendToBeVisual: true,
    url: "https://news.example.com/article",
  });

  const { window } = dom;

  Object.defineProperty(window.HTMLElement.prototype, "innerText", {
    get() {
      return this.textContent;
    },
    configurable: true,
  });

  window.innerWidth = 1280;
  window.innerHeight = 800;

  const sent = [];
  const messageListeners = [];
  const storageListeners = [];
  const storageState = { hoverEnabled };

  window.chrome = {
    runtime: {
      getURL: (path) => `chrome-extension://test/${path}`,
      onMessage: {
        addListener: (fn) => messageListeners.push(fn),
      },
      sendMessage: async (message) => {
        sent.push(message);
        return respond
          ? respond(message)
          : { ok: true, data: analysisFixture() };
      },
    },
    storage: {
      sync: {
        get: async (defaults) => ({ ...defaults, ...storageState }),
        set: async (values) => Object.assign(storageState, values),
      },
      onChanged: {
        addListener: (fn) => storageListeners.push(fn),
      },
    },
  };

  window.eval(readSource("content.js"));

  // The content script arms itself from chrome.storage asynchronously; tests
  // dispatch events synchronously right after injection, which would race the
  // microtask. Deliver the armed state through the onChanged path instead,
  // which registers synchronously during injection.
  if (hoverEnabled) {
    storageListeners.forEach((fn) =>
      fn({ hoverEnabled: { newValue: true } }, "sync")
    );
  }

  const host = window.document.getElementById("adinsight-root");

  return {
    dom,
    window,
    document: window.document,
    host,
    shadow: host && host.shadowRoot,
    sent,
    /** Deliver a message as background.js would. */
    dispatchRuntimeMessage: (message) =>
      messageListeners.forEach((fn) => fn(message)),
    /** Flip the popup's hover toggle, as chrome.storage.onChanged reports it. */
    setHoverEnabled: (value) =>
      storageListeners.forEach((fn) =>
        fn({ hoverEnabled: { newValue: value } }, "sync")
      ),
  };
}

/** Wait for the microtasks/timers content.js schedules. */
export function tick(window, ms = 30) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function mouse(window, element, type, extra = {}) {
  element.dispatchEvent(
    new window.MouseEvent(type, { bubbles: true, cancelable: true, ...extra })
  );
}

export function key(window, target, keyName) {
  target.dispatchEvent(
    new window.KeyboardEvent("keydown", {
      key: keyName,
      bubbles: true,
      cancelable: true,
    })
  );
}

/** A representative /api/analyze response for the wireframe ad. */
export function analysisFixture(overrides = {}) {
  return {
    text: "FINAL HOURS: Doctor-recommended MemoryMax Pro reverses memory loss.",
    source: { mode: "text" },
    prediction: {
      label: "Authority Manipulation",
      confidence: 0.8988,
      truncated: false,
      distribution: [
        { label: "Authority Manipulation", confidence: 0.8988 },
        { label: "Social Proof", confidence: 0.03 },
        { label: "Urgency", confidence: 0.02 },
        { label: "Fear Appeals", confidence: 0.02 },
        { label: "Exaggerated Claims", confidence: 0.01 },
        { label: "FOMO", confidence: 0.01 },
        { label: "Scarcity", confidence: 0.0112 },
      ],
    },
    tactics: [
      {
        label: "Authority Manipulation",
        display: "Authority",
        confidence: 0.8988,
        sources: ["model", "phrase"],
        phrases: [{ text: "Doctor-recommended", start: 13, end: 31 }],
        explanation: '"Doctor-recommended," but no doctor or study is named.',
        uncertain: false,
      },
      {
        label: "Urgency",
        display: "Urgency",
        confidence: 0.02,
        sources: ["phrase"],
        phrases: [{ text: "FINAL HOURS", start: 0, end: 11 }],
        explanation: '"FINAL HOURS" is there to rush you. Real offers keep.',
        uncertain: false,
      },
    ],
    summary: {
      tone: "caution",
      headline: "Take your time.",
      message: "This ad uses 2 pressure tactics. Nothing requires a decision today.",
      count: 2,
    },
    ...overrides,
  };
}
