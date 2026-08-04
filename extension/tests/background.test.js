/* background.js — the service worker: context menus, API calls, and the
 * message routing content.js and the popup depend on. */

import assert from "node:assert/strict";
import vm from "node:vm";
import { describe, it } from "node:test";

import { readSource } from "./helpers.js";

/**
 * Load background.js into a sandbox with a fake `chrome` and `fetch`.
 *
 * It registers its listeners at load time, so they are captured here and then
 * invoked directly, the way Chrome would.
 */
function loadWorker({ fetchImpl, storage = {}, tabs = [{ id: 7 }], captureSize } = {}) {
  const calls = [];
  const menus = [];
  const messageListeners = [];
  const menuClickListeners = [];
  const installListeners = [];
  const tabMessages = [];

  const chrome = {
    runtime: {
      onInstalled: { addListener: (fn) => installListeners.push(fn) },
      onMessage: { addListener: (fn) => messageListeners.push(fn) },
    },
    storage: {
      sync: {
        get: async (key) => (key in storage ? { [key]: storage[key] } : {}),
        set: async (values) => Object.assign(storage, values),
      },
    },
    contextMenus: {
      removeAll: (done) => done(),
      create: (definition) => menus.push(definition),
      onClicked: { addListener: (fn) => menuClickListeners.push(fn) },
    },
    tabs: {
      query: async () => tabs,
      get: async (id) => ({ id, windowId: 1 }),
      sendMessage: (tabId, message) => tabMessages.push({ tabId, message }),
      captureVisibleTab: async () => "data:image/png;base64,FAKE",
    },
  };

  // The capture path uses browser drawing APIs Node doesn't have. The fakes
  // reproduce only the geometry the crop logic depends on.
  const bitmap = captureSize || { width: 1280, height: 800 };
  const drawCalls = [];

  const sandboxExtras = {
    createImageBitmap: async () => bitmap,
    OffscreenCanvas: class {
      constructor(width, height) {
        this.width = width;
        this.height = height;
      }
      getContext() {
        return { drawImage: (...args) => drawCalls.push(args) };
      }
      async convertToBlob() {
        return new Blob(["cropped"], { type: "image/png" });
      }
    },
  };

  const fetchStub = async (url, options) => {
    // The worker re-fetches the capture's data URL to get a blob; that's
    // plumbing, not an API call worth asserting on.
    if (typeof url === "string" && url.startsWith("data:")) {
      return { ok: true, blob: async () => new Blob(["png"], { type: "image/png" }) };
    }

    calls.push({ url, options });
    return fetchImpl
      ? fetchImpl(url, options)
      : jsonResponse({ ok: true });
  };

  const sandbox = {
    chrome,
    fetch: fetchStub,
    FormData: globalThis.FormData,
    Blob: globalThis.Blob,
    console,
    setTimeout,
    URL,
    ...sandboxExtras,
  };

  vm.createContext(sandbox);
  vm.runInContext(readSource("background.js"), sandbox);

  installListeners.forEach((fn) => fn());

  /** Invoke the onMessage listener and resolve what it sends back. */
  const send = (message, sender = {}) =>
    new Promise((resolve) => {
      messageListeners[0](message, sender, resolve);
    });

  return { calls, menus, menuClickListeners, tabMessages, send, storage, drawCalls };
}

function jsonResponse(body, ok = true) {
  return { ok, json: async () => body };
}

function blobResponse(blob, ok = true) {
  return { ok, blob: async () => blob };
}

describe("context menus", () => {
  it("registers a menu item for selections and for images", () => {
    const { menus } = loadWorker();

    const contexts = menus.flatMap((menu) => menu.contexts);
    assert.ok(contexts.includes("selection"));
    assert.ok(contexts.includes("image"));
  });

  it("forwards a selected text click to the tab", () => {
    const { menuClickListeners, tabMessages } = loadWorker();

    menuClickListeners[0](
      { menuItemId: "adinsight-analyze-selection", selectionText: "act now, only 3 left" },
      { id: 7 }
    );

    assert.equal(tabMessages.length, 1);
    assert.equal(tabMessages[0].tabId, 7);
    assert.equal(tabMessages[0].message.payload.text, "act now, only 3 left");
  });

  it("forwards an image click to the tab", () => {
    const { menuClickListeners, tabMessages } = loadWorker();

    menuClickListeners[0](
      { menuItemId: "adinsight-analyze-image", srcUrl: "https://cdn.example.com/ad.png" },
      { id: 7 }
    );

    assert.equal(tabMessages[0].message.payload.imageUrl, "https://cdn.example.com/ad.png");
  });

  it("ignores a click with no tab", () => {
    const { menuClickListeners, tabMessages } = loadWorker();

    menuClickListeners[0]({ menuItemId: "adinsight-analyze-selection", selectionText: "x" }, null);

    assert.equal(tabMessages.length, 0);
  });
});

describe("analyzeText", () => {
  it("posts JSON to the analyze endpoint", async () => {
    const worker = loadWorker({
      fetchImpl: () => jsonResponse({ summary: { count: 2 } }),
    });

    const result = await worker.send({ type: "analyzeText", text: "act now" });

    assert.equal(result.ok, true);
    assert.deepEqual(result.data, { summary: { count: 2 } });

    const call = worker.calls[0];
    assert.equal(call.url, "http://127.0.0.1:5000/api/analyze");
    assert.equal(call.options.method, "POST");
    assert.equal(JSON.parse(call.options.body).text, "act now");
  });

  it("uses the configured server address", async () => {
    const worker = loadWorker({
      storage: { apiBase: "http://192.168.0.5:5000/" },
      fetchImpl: () => jsonResponse({}),
    });

    await worker.send({ type: "analyzeText", text: "act now" });

    assert.equal(worker.calls[0].url, "http://192.168.0.5:5000/api/analyze");
  });

  it("passes a non-2xx response through with ok=false", async () => {
    const worker = loadWorker({
      fetchImpl: () => jsonResponse({ error: "Paste some ad text first." }, false),
    });

    const result = await worker.send({ type: "analyzeText", text: " " });

    assert.equal(result.ok, false);
    assert.equal(result.data.error, "Paste some ad text first.");
  });
});

describe("analyzeImage", () => {
  it("downloads the image, then posts it as a file", async () => {
    const worker = loadWorker({
      fetchImpl: (url) =>
        url.startsWith("https://cdn")
          ? blobResponse(new Blob(["fake-png"], { type: "image/png" }))
          : jsonResponse({ source: { mode: "image" } }),
    });

    const result = await worker.send({
      type: "analyzeImage",
      imageUrl: "https://cdn.example.com/ad.png",
    });

    assert.equal(result.ok, true);
    assert.equal(worker.calls.length, 2);
    assert.ok(worker.calls[1].options.body instanceof FormData);
    assert.ok(worker.calls[1].options.body.get("image"));
  });

  it("rejects a URL that isn't an image", async () => {
    const worker = loadWorker({
      fetchImpl: () => blobResponse(new Blob(["<html>"], { type: "text/html" })),
    });

    const result = await worker.send({
      type: "analyzeImage",
      imageUrl: "https://example.com/page.html",
    });

    assert.equal(result.ok, false);
    assert.match(result.error, /isn't an image/);
  });

  it("reports a failed download", async () => {
    const worker = loadWorker({
      fetchImpl: () => ({ ok: false, blob: async () => null }),
    });

    const result = await worker.send({
      type: "analyzeImage",
      imageUrl: "https://cdn.example.com/missing.png",
    });

    assert.equal(result.ok, false);
    assert.match(result.error, /Couldn't download/);
  });
});

describe("failure handling", () => {
  it("turns a dead server into a start-the-server message", async () => {
    const worker = loadWorker({
      fetchImpl: () => {
        throw new Error("Failed to fetch");
      },
    });

    const result = await worker.send({ type: "analyzeText", text: "act now" });

    assert.equal(result.ok, false);
    assert.match(result.error, /python app\/server\.py/);
  });

  it("reports an unknown message type", async () => {
    const worker = loadWorker();
    const result = await worker.send({ type: "nonsense" });

    assert.equal(result.ok, false);
    assert.match(result.error, /Unknown message/);
  });
});

describe("popup routing", () => {
  it("pushes pasted text into the active tab", async () => {
    const worker = loadWorker();
    const result = await worker.send({ type: "openPanelWithText", text: "act now" });

    assert.equal(result.ok, true);
    assert.equal(worker.tabMessages[0].message.type, "analyze");
    assert.equal(worker.tabMessages[0].message.payload.text, "act now");
  });

  it("starts pick mode in the active tab", async () => {
    const worker = loadWorker();
    const result = await worker.send({ type: "startPicking" });

    assert.equal(result.ok, true);
    assert.equal(worker.tabMessages[0].message.type, "startPicking");
  });

  it("reports when there is no usable tab", async () => {
    const worker = loadWorker({ tabs: [] });
    const result = await worker.send({ type: "startPicking" });

    assert.equal(result.ok, false);
  });
});

describe("region capture (video / iframe ads)", () => {
  const SENDER = { tab: { id: 7 } };
  const REGION = { left: 100, top: 200, width: 600, height: 300, devicePixelRatio: 2, gapMs: 0 };

  it("registers the screenshot context-menu item on every context", () => {
    const { menus } = loadWorker();
    const capture = menus.find((menu) => menu.id === "adinsight-capture-region");

    assert.ok(capture, "capture menu item missing");
    // Spread: the array was built in the worker's vm realm, whose Array
    // prototype differs from the test's, and deepStrictEqual checks prototypes.
    assert.deepEqual([...capture.contexts], ["all"]);
  });

  it("forwards the menu click to the content script", () => {
    const { menuClickListeners, tabMessages } = loadWorker();

    menuClickListeners[0]({ menuItemId: "adinsight-capture-region" }, { id: 7 });

    assert.equal(tabMessages[0].message.type, "captureRequested");
  });

  it("crops in device pixels using the reported DPR", async () => {
    const worker = loadWorker({ captureSize: { width: 2560, height: 1600 } });

    const captured = await worker.send({ type: "captureRegion", region: REGION }, SENDER);

    assert.equal(captured.ok, true);

    // drawImage(bitmap, sx, sy, sw, sh, ...) — region * DPR 2.
    const [, sx, sy, sw, sh] = worker.drawCalls[0];
    assert.deepEqual([sx, sy, sw, sh], [200, 400, 1200, 600]);
  });

  it("clamps a region hanging off the bitmap", async () => {
    // Bitmap is 1000px wide; the region at DPR 2 would need 1400.
    const worker = loadWorker({ captureSize: { width: 1000, height: 1600 } });

    const captured = await worker.send(
      { type: "captureRegion", region: { left: 100, top: 0, width: 600, height: 300, devicePixelRatio: 2, gapMs: 0 } },
      SENDER
    );

    assert.equal(captured.ok, true);
    const [, sx, , sw] = worker.drawCalls[0];
    assert.equal(sx, 200);
    assert.equal(sw, 800); // 1000 - 200, not 1200
  });

  it("refuses a region too small to read", async () => {
    const worker = loadWorker();

    const captured = await worker.send(
      { type: "captureRegion", region: { left: 0, top: 0, width: 10, height: 10, devicePixelRatio: 1, gapMs: 0 } },
      SENDER
    );

    assert.equal(captured.ok, false);
    assert.match(captured.error, /too small/);
  });

  it("bursts several frames so animated ads aren't caught mid-transition", async () => {
    const worker = loadWorker();

    const captured = await worker.send({ type: "captureRegion", region: REGION }, SENDER);

    assert.equal(captured.ok, true);
    assert.equal(captured.frames, 3);
    assert.equal(worker.drawCalls.length, 3, "expected one crop per frame");
  });

  it("phase 2 posts every captured frame to the analyze endpoint", async () => {
    const worker = loadWorker({
      fetchImpl: () => jsonResponse({ source: { mode: "image" } }),
    });

    await worker.send({ type: "captureRegion", region: REGION }, SENDER);
    const result = await worker.send({ type: "analyzeCapture" }, SENDER);

    assert.equal(result.ok, true);
    assert.equal(worker.calls[0].url, "http://127.0.0.1:5000/api/analyze");
    assert.ok(worker.calls[0].options.body instanceof FormData);
    assert.equal(worker.calls[0].options.body.getAll("image").length, 3);
  });

  it("phase 2 without a capture reports expiry, not a crash", async () => {
    const worker = loadWorker();

    const result = await worker.send({ type: "analyzeCapture" }, SENDER);

    assert.equal(result.ok, false);
    assert.match(result.error, /expired/);
  });

  it("a capture from one tab cannot be analyzed from another", async () => {
    const worker = loadWorker();

    await worker.send({ type: "captureRegion", region: REGION }, SENDER);
    const result = await worker.send({ type: "analyzeCapture" }, { tab: { id: 99 } });

    assert.equal(result.ok, false);
    assert.match(result.error, /expired/);
  });
});

describe("health", () => {
  it("reads the server's health endpoint", async () => {
    const worker = loadWorker({
      fetchImpl: () => jsonResponse({ model_ready: true, ocr_backend: "rapidocr" }),
    });

    const result = await worker.send({ type: "health" });

    assert.equal(worker.calls[0].url, "http://127.0.0.1:5000/api/health");
    assert.equal(result.data.model_ready, true);
  });
});
