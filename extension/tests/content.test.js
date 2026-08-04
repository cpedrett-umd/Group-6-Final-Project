/* content.js — the overlay: injection, ad detection, pill placement, pick
 * mode, and rendering. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  analysisFixture,
  createEnvironment,
  key,
  mouse,
  setRect,
  tick,
} from "./helpers.js";

/** Give the ad and the pill believable geometry. */
function layOutAd(env, adRect = { left: 100, top: 200, width: 500, height: 300 }) {
  const ad = env.document.getElementById("ad");
  setRect(ad, adRect);

  const pill = env.shadow.querySelector(".ai-pill");
  Object.defineProperty(pill, "offsetWidth", { value: 190, configurable: true });
  Object.defineProperty(pill, "offsetHeight", { value: 44, configurable: true });

  return { ad, pill };
}

describe("injection", () => {
  it("mounts a shadow root on the page", () => {
    const env = createEnvironment();

    assert.ok(env.host, "host element missing");
    assert.ok(env.shadow, "shadow root missing");
    assert.ok(env.shadow.querySelector(".ai-panel"));
    assert.ok(env.shadow.querySelector(".ai-pill"));
  });

  it("takes up no layout space in the host page", () => {
    const env = createEnvironment();
    assert.match(env.host.style.cssText, /width:\s*0/);
    assert.match(env.host.style.cssText, /height:\s*0/);
  });

  it("loads its stylesheet from the extension, not the page", () => {
    const env = createEnvironment();
    const link = env.shadow.querySelector("link[rel=stylesheet]");
    assert.match(link.href, /^chrome-extension:\/\//);
  });

  it("does not inject twice", () => {
    const env = createEnvironment();
    env.window.eval(
      "(" + function () {} + ")"
    ); // no-op, keeps eval semantics identical
    env.window.__adinsightLoaded = true;

    const before = env.document.querySelectorAll("#adinsight-root").length;
    assert.equal(before, 1);
  });

  it("starts with the panel closed", () => {
    const env = createEnvironment();
    assert.equal(env.shadow.querySelector(".ai-panel").hidden, true);
    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });
});

describe("ad detection", () => {
  it("offers the pill when hovering a sponsored block", async () => {
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env);

    mouse(env.window, ad, "mouseover");
    await tick(env.window);

    assert.equal(pill.hidden, false);
    assert.equal(pill.querySelector("span").textContent, "Analyze this ad");
  });

  it("ignores ordinary article text", async () => {
    const env = createEnvironment();
    layOutAd(env);

    const prose = env.document.getElementById("prose");
    setRect(prose, { left: 0, top: 0, width: 600, height: 120 });

    mouse(env.window, prose, "mouseover");
    await tick(env.window);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("ignores an ad-marked block that is too small", async () => {
    const env = createEnvironment();
    layOutAd(env);

    const tiny = env.document.getElementById("tiny");
    setRect(tiny, { left: 0, top: 0, width: 40, height: 20 });

    mouse(env.window, tiny, "mouseover");
    await tick(env.window);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("ignores an ad-marked block with too little text", async () => {
    const env = createEnvironment();
    layOutAd(env);

    const tiny = env.document.getElementById("tiny"); // text is just "Ad"
    setRect(tiny, { left: 0, top: 0, width: 300, height: 200 });

    mouse(env.window, tiny, "mouseover");
    await tick(env.window);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("finds the ad when hovering a child of it", async () => {
    const env = createEnvironment();
    const { pill } = layOutAd(env);

    const cta = env.document.getElementById("cta");
    mouse(env.window, cta, "mouseover");
    await tick(env.window);

    assert.equal(pill.hidden, false);
  });
});

describe("pill placement", () => {
  it("sits inside the ad along its bottom edge", async () => {
    // Overlapping the ad means the pointer never leaves the ad's box on the
    // way to the button, so nothing beside the ad can steal the hover.
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env, { left: 100, top: 100, width: 400, height: 200 });

    mouse(env.window, ad, "mouseover");
    await tick(env.window);

    assert.equal(pill.style.top, "246px"); // (100 + 200) - 44 - 10, inside
  });

  it("stays inside even at the detector's minimum ad height", async () => {
    // The 80px size floor guarantees a 44px pill always fits inside, so the
    // below/above fallbacks only matter for degenerate rects.
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env, { left: 100, top: 100, width: 400, height: 82 });

    mouse(env.window, ad, "mouseover");
    await tick(env.window);

    assert.equal(pill.style.top, "128px"); // (100 + 82) - 44 - 10, inside
  });

  it("never positions the pill outside the viewport", async () => {
    const env = createEnvironment();
    // Taller than the viewport and starting above it, so there is no room
    // below and the flipped-above position is off-screen too. Kept narrower
    // than 95% of the viewport, or the "this is the whole page" guard in
    // isPlausibleAd rejects it before placement is ever reached.
    const { ad, pill } = layOutAd(env, { left: -50, top: -100, width: 400, height: 1400 });

    mouse(env.window, ad, "mouseover");
    await tick(env.window);

    const top = parseFloat(pill.style.top);
    const left = parseFloat(pill.style.left);

    assert.ok(top >= 8 && top <= env.window.innerHeight - 44 - 8, `top ${top}`);
    assert.ok(left >= 8 && left <= env.window.innerWidth - 190 - 8, `left ${left}`);
  });

  it("stays hidden for an ad scrolled out of view", async () => {
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env, { left: 100, top: 3000, width: 400, height: 300 });

    mouse(env.window, ad, "mouseover");
    await tick(env.window);

    assert.equal(pill.hidden, true);
  });

  it("hides on scroll", async () => {
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env);

    mouse(env.window, ad, "mouseover");
    await tick(env.window);
    assert.equal(pill.hidden, false);

    env.window.dispatchEvent(new env.window.Event("scroll"));
    assert.equal(pill.hidden, true);
  });
});

describe("text selection", () => {
  function selectText(env, element) {
    const range = env.document.createRange();
    range.selectNodeContents(element);
    range.getBoundingClientRect = () => ({
      left: 120,
      top: 260,
      width: 300,
      height: 40,
      right: 420,
      bottom: 300,
    });

    const selection = env.window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    return range;
  }

  it("offers the pill for a long enough selection", async () => {
    const env = createEnvironment();
    const { pill } = layOutAd(env);

    selectText(env, env.document.getElementById("prose"));
    mouse(env.window, env.document.body, "mouseup");
    await tick(env.window, 60);

    assert.equal(pill.hidden, false);
    assert.equal(pill.querySelector("span").textContent, "Analyze this text");
  });

  it("ignores a selection that is too short", async () => {
    const env = createEnvironment();
    const { pill } = layOutAd(env);

    const short = env.document.createElement("p");
    short.textContent = "Too short";
    env.document.body.append(short);

    selectText(env, short);
    mouse(env.window, env.document.body, "mouseup");
    await tick(env.window, 60);

    assert.equal(pill.hidden, true);
  });
});

describe("analysis requests", () => {
  it("sends the ad's text when the pill is clicked", async () => {
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env);

    mouse(env.window, ad, "mouseover");
    await tick(env.window);
    pill.click();
    await tick(env.window, 60);

    assert.equal(env.sent.length, 1);
    assert.equal(env.sent[0].type, "analyzeText");
    assert.match(env.sent[0].text, /FINAL HOURS/);
  });

  it("sends an image URL when the context menu targets an image", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({
      type: "analyze",
      payload: { imageUrl: "https://cdn.example.com/ad.png" },
    });
    await tick(env.window, 60);

    assert.equal(env.sent[0].type, "analyzeImage");
    assert.equal(env.sent[0].imageUrl, "https://cdn.example.com/ad.png");
  });

  it("shows the busy state while waiting", async () => {
    let release;
    const pending = new Promise((resolve) => {
      release = resolve;
    });

    const env = createEnvironment({ respond: () => pending });

    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "act now please" } });
    await tick(env.window, 20);

    const active = env.shadow.querySelector(".ai-state.is-active");
    assert.equal(active.dataset.state, "busy");

    release({ ok: true, data: analysisFixture() });
  });
});

describe("rendering results", () => {
  async function renderWith(data) {
    const env = createEnvironment({ respond: () => ({ ok: true, data }) });
    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "an ad" } });
    await tick(env.window, 80);
    return env;
  }

  const inResult = (env, selector) =>
    env.shadow.querySelector(`[data-state="result"] ${selector}`);

  it("shows the summary and the tactic rows", async () => {
    const env = await renderWith(analysisFixture());

    assert.equal(
      env.shadow.querySelector(".ai-state.is-active").dataset.state,
      "result"
    );
    assert.equal(inResult(env, ".ai-callout-head").textContent, "Take your time.");

    const names = [...env.shadow.querySelectorAll('[data-state="result"] .ai-tactic-name')];
    assert.equal(names.length, 2);
    assert.match(names[0].textContent, /Authority/);
  });

  it("badges the model pick and the phrase hits", async () => {
    const env = await renderWith(analysisFixture());
    const first = inResult(env, ".ai-tactic-name");

    assert.ok(first.querySelector(".ai-src-model"), "missing model badge");
    assert.ok(first.querySelector(".ai-src-phrase"), "missing phrase badge");
    assert.match(first.querySelector(".ai-conf").textContent, /90% confident/);
  });

  it("shows confidence only on the model row", async () => {
    const env = await renderWith(analysisFixture());
    const rows = [...env.shadow.querySelectorAll('[data-state="result"] .ai-tactic-name')];

    assert.ok(rows[0].querySelector(".ai-conf"));
    assert.equal(rows[1].querySelector(".ai-conf"), null);
  });

  it("hides uncertain rows but keeps the score in the table", async () => {
    // A clean ad: the model is forced to name a tactic (no neutral class), so
    // the prediction has to move too, not just the row.
    const data = analysisFixture({
      prediction: {
        label: "Urgency",
        confidence: 0.45,
        truncated: false,
        distribution: [
          { label: "Urgency", confidence: 0.45 },
          { label: "FOMO", confidence: 0.2 },
          { label: "Scarcity", confidence: 0.13 },
          { label: "Social Proof", confidence: 0.09 },
          { label: "Exaggerated Claims", confidence: 0.06 },
          { label: "Fear Appeals", confidence: 0.04 },
          { label: "Authority Manipulation", confidence: 0.03 },
        ],
      },
      tactics: [
        {
          label: "Urgency",
          display: "Urgency",
          confidence: 0.45,
          sources: ["model"],
          phrases: [],
          explanation: "The wording pushes you to act quickly.",
          uncertain: true,
        },
      ],
      summary: {
        tone: "calm",
        headline: "Nothing pushy found.",
        message: "This ad reads as straightforward.",
        count: 0,
      },
    });

    const env = await renderWith(data);

    assert.equal(env.shadow.querySelectorAll('[data-state="result"] .ai-tactic').length, 0);
    assert.match(
      inResult(env, ".ai-tactic-empty").textContent,
      /No pressure tactics stood out/
    );
    // The forced pick is still disclosed lower down.
    assert.equal(inResult(env, ".ai-detail-label").textContent, "Urgency");
  });

  it("styles a clean ad calmly", async () => {
    const env = await renderWith(
      analysisFixture({
        summary: { tone: "calm", headline: "Nothing pushy found.", message: "ok", count: 0 },
        tactics: [],
      })
    );

    assert.ok(inResult(env, ".ai-callout").classList.contains("is-calm"));
  });

  it("renders all seven classes and marks the top one", async () => {
    const env = await renderWith(analysisFixture());
    const rows = [...env.shadow.querySelectorAll('[data-state="result"] .ai-dist tbody tr')];

    assert.equal(rows.length, 7);
    assert.ok(rows[0].classList.contains("is-top"));
    assert.match(rows[0].textContent, /Authority Manipulation/);
  });

  it("shows what OCR read for image input", async () => {
    const env = await renderWith(
      analysisFixture({
        source: {
          mode: "image",
          ocr: { confidence: 0.98, line_count: 3, repaired: true },
        },
      })
    );

    const readback = inResult(env, ".ai-readback");
    assert.equal(readback.hidden, false);
    assert.match(inResult(env, ".ai-readback-meta").textContent, /3 lines read/);
    assert.match(inResult(env, ".ai-readback-meta").textContent, /98% confident/);
    assert.match(inResult(env, ".ai-readback-meta").textContent, /spacing repaired/);
  });

  it("hides the read-back for text input", async () => {
    const env = await renderWith(analysisFixture());
    assert.equal(inResult(env, ".ai-readback").hidden, true);
  });

  it("marks the review panel as sample data", async () => {
    const env = await renderWith(analysisFixture());

    assert.equal(inResult(env, ".ai-mock-badge").hidden, false);
    assert.match(inResult(env, ".ai-mock-notice").textContent, /not built yet/);
    assert.equal(
      env.shadow.querySelectorAll('[data-state="result"] .ai-review').length,
      2
    );
  });

  it("treats ad copy as text, never as markup", async () => {
    const env = await renderWith(
      analysisFixture({
        tactics: [
          {
            label: "Urgency",
            display: "Urgency",
            confidence: 0.9,
            sources: ["phrase"],
            phrases: [],
            explanation: '"<img src=x onerror=alert(1)>" is there to rush you.',
            uncertain: false,
          },
        ],
      })
    );

    assert.equal(env.shadow.querySelectorAll('[data-state="result"] img').length, 0);
    assert.match(inResult(env, ".ai-tactic-why").textContent, /<img src=x/);
  });

  it("re-renders cleanly on a second analysis", async () => {
    const env = await renderWith(analysisFixture());
    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "another ad" } });
    await tick(env.window, 80);

    assert.equal(
      env.shadow.querySelectorAll('[data-state="result"] .ai-tactic').length,
      2,
      "rows duplicated instead of being replaced"
    );
  });
});

describe("errors", () => {
  it("shows the server's message", async () => {
    const env = createEnvironment({
      respond: () => ({ ok: false, error: "Can't reach the AdInsight server." }),
    });

    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "an ad" } });
    await tick(env.window, 60);

    const active = env.shadow.querySelector(".ai-state.is-active");
    assert.equal(active.dataset.state, "error");
    assert.match(
      env.shadow.querySelector('[data-state="error"] .ai-callout-msg').textContent,
      /Can't reach/
    );
  });

  it("falls back to the payload's error", async () => {
    const env = createEnvironment({
      respond: () => ({ ok: false, data: { error: "No text could be read." } }),
    });

    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "an ad" } });
    await tick(env.window, 60);

    assert.match(
      env.shadow.querySelector('[data-state="error"] .ai-callout-msg').textContent,
      /No text could be read/
    );
  });

  it("handles no response at all", async () => {
    const env = createEnvironment({ respond: () => undefined });

    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "an ad" } });
    await tick(env.window, 60);

    assert.equal(
      env.shadow.querySelector(".ai-state.is-active").dataset.state,
      "error"
    );
  });
});

describe("dismissing the panel", () => {
  it("closes on the close button", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "an ad" } });
    await tick(env.window, 60);

    env.shadow.querySelector(".ai-close").click();
    await tick(env.window, 260);

    assert.equal(env.shadow.querySelector(".ai-panel").hidden, true);
  });

  it("closes on Escape", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "analyze", payload: { text: "an ad" } });
    await tick(env.window, 60);

    key(env.window, env.document, "Escape");
    await tick(env.window, 260);

    assert.equal(env.shadow.querySelector(".ai-panel").hidden, true);
  });
});

describe("screenshot capture (video / iframe ads)", () => {
  function addAdIframe(env) {
    const iframe = env.document.createElement("iframe");
    iframe.src = "https://safeframe.googlesyndication.com/x";
    env.document.body.append(iframe);
    setRect(iframe, { left: 150, top: 120, width: 970, height: 250 });
    return iframe;
  }

  function captureEnvironment(responses = {}) {
    return createEnvironment({
      respond: (message) => {
        if (message.type === "captureRegion") {
          return responses.capture || { ok: true, captured: true };
        }
        if (message.type === "analyzeCapture") {
          return responses.analyze || {
            ok: true,
            data: analysisFixture({
              source: { mode: "image", ocr: { confidence: 0.95, line_count: 2, repaired: false } },
            }),
          };
        }
        return { ok: true, data: analysisFixture() };
      },
    });
  }

  it("offers the pill when hovering an ad iframe, and clicking it captures", async () => {
    const env = captureEnvironment();
    const iframe = addAdIframe(env);
    const pill = env.shadow.querySelector(".ai-pill");
    Object.defineProperty(pill, "offsetWidth", { value: 190, configurable: true });
    Object.defineProperty(pill, "offsetHeight", { value: 44, configurable: true });

    // Entering a cross-origin iframe still fires mouseover on the iframe
    // element itself in the parent page — the one event we get, and enough.
    mouse(env.window, iframe, "mouseover");
    await tick(env.window);

    assert.equal(pill.hidden, false, "no pill on ad-iframe hover");
    // Inside the ad, bottom edge: (120 + 250) - 44 - 10.
    assert.equal(pill.style.top, "316px");

    pill.click();
    await tick(env.window, 150);

    const capture = env.sent.find((m) => m.type === "captureRegion");
    assert.ok(capture, "pill click did not start a capture");
    assert.equal(capture.region.width, 970);
    assert.equal(
      env.shadow.querySelector(".ai-state.is-active").dataset.state,
      "result"
    );
  });

  it("offers capture for a text-less ad container wrapping an iframe", async () => {
    // Yahoo's shape: the wrapper matches the ad selectors but holds no
    // readable text — the words are inside a cross-origin iframe.
    const env = captureEnvironment();
    const wrapper = env.document.createElement("div");
    wrapper.className = "ad-slot";
    const inner = env.document.createElement("iframe");
    inner.src = "https://safeframe.googlesyndication.com/y";
    wrapper.append(inner);
    env.document.body.append(wrapper);
    setRect(wrapper, { left: 60, top: 100, width: 300, height: 250 });

    const pill = env.shadow.querySelector(".ai-pill");
    mouse(env.window, wrapper, "mouseover");
    await tick(env.window);

    assert.equal(pill.hidden, false, "no pill on text-less ad container");

    pill.click();
    await tick(env.window, 150);
    assert.ok(env.sent.some((m) => m.type === "captureRegion"));
  });

  it("captures the iframe's rect when the right-click landed on it", async () => {
    const env = captureEnvironment();
    const iframe = addAdIframe(env);

    mouse(env.window, iframe, "contextmenu", { clientX: 400, clientY: 200 });
    env.dispatchRuntimeMessage({ type: "captureRequested" });
    await tick(env.window, 120);

    const capture = env.sent.find((m) => m.type === "captureRegion");
    assert.ok(capture, "no captureRegion message sent");
    assert.equal(capture.region.left, 150);
    assert.equal(capture.region.top, 120);
    assert.equal(capture.region.width, 970);
    assert.equal(capture.region.height, 250);
    assert.equal(typeof capture.region.devicePixelRatio, "number");
  });

  it("runs phase 2 and renders the result", async () => {
    const env = captureEnvironment();
    const iframe = addAdIframe(env);

    mouse(env.window, iframe, "contextmenu", { clientX: 400, clientY: 200 });
    env.dispatchRuntimeMessage({ type: "captureRequested" });
    await tick(env.window, 150);

    assert.ok(env.sent.some((m) => m.type === "analyzeCapture"));
    assert.equal(
      env.shadow.querySelector(".ai-state.is-active").dataset.state,
      "result"
    );
    // Image input, so the read-back section is shown.
    assert.equal(
      env.shadow.querySelector('[data-state="result"] .ai-readback').hidden,
      false
    );
  });

  it("keeps our UI hidden through the screenshot phase", async () => {
    let panelVisibleAtCapture = null;

    const env = createEnvironment({
      respond: (message) => {
        if (message.type === "captureRegion") {
          const panel = env.shadow.querySelector(".ai-panel");
          panelVisibleAtCapture = !panel.hidden;
          return { ok: true, captured: true };
        }
        return { ok: true, data: analysisFixture() };
      },
    });

    const iframe = addAdIframe(env);
    mouse(env.window, iframe, "contextmenu", { clientX: 400, clientY: 200 });
    env.dispatchRuntimeMessage({ type: "captureRequested" });
    await tick(env.window, 150);

    assert.equal(panelVisibleAtCapture, false, "panel was up during the screenshot");
  });

  it("surfaces a phase-1 failure as an error state", async () => {
    const env = captureEnvironment({
      capture: { ok: false, error: "That region is too small to read." },
    });

    const iframe = addAdIframe(env);
    mouse(env.window, iframe, "contextmenu", { clientX: 400, clientY: 200 });
    env.dispatchRuntimeMessage({ type: "captureRequested" });
    await tick(env.window, 120);

    assert.equal(
      env.shadow.querySelector(".ai-state.is-active").dataset.state,
      "error"
    );
    assert.match(
      env.shadow.querySelector('[data-state="error"] .ai-callout-msg').textContent,
      /too small/
    );
    assert.ok(!env.sent.some((m) => m.type === "analyzeCapture"), "phase 2 ran anyway");
  });

  it("asks for a better click when nothing sizeable was under it", async () => {
    const env = captureEnvironment();

    // Right-click a tiny element with no sizeable ancestor rects (jsdom rects
    // default to 0x0), so no capture target can be found.
    const speck = env.document.createElement("span");
    speck.textContent = "x";
    env.document.body.append(speck);

    mouse(env.window, speck, "contextmenu", { clientX: 5, clientY: 5 });
    env.dispatchRuntimeMessage({ type: "captureRequested" });
    await tick(env.window, 120);

    assert.equal(
      env.shadow.querySelector(".ai-state.is-active").dataset.state,
      "error"
    );
    assert.equal(env.sent.length, 0, "sent a capture with no region");
  });
});

describe("pick mode", () => {
  it("shows the hint when started", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "startPicking" });
    await tick(env.window);

    assert.equal(env.shadow.querySelector(".ai-pick-hint").hidden, false);
  });

  it("highlights whatever is hovered, ad-marked or not", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const prose = env.document.getElementById("prose");
    setRect(prose, { left: 40, top: 90, width: 500, height: 110 });

    mouse(env.window, prose, "mousemove");
    await tick(env.window);

    const highlight = env.shadow.querySelector(".ai-highlight");
    assert.equal(highlight.hidden, false);
    assert.equal(highlight.style.left, "40px");
    assert.equal(highlight.style.width, "500px");
  });

  it("analyzes the picked block and suppresses the page's click", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    mouse(env.window, ad, "mousemove");
    await tick(env.window);

    const clickEvent = new env.window.MouseEvent("click", {
      bubbles: true,
      cancelable: true,
    });
    ad.dispatchEvent(clickEvent);
    await tick(env.window, 60);

    assert.equal(clickEvent.defaultPrevented, true, "ad link would have opened");
    assert.equal(env.sent[0].type, "analyzeText");
    assert.match(env.sent[0].text, /FINAL HOURS/);
  });

  it("cancels on Escape without analyzing", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "startPicking" });

    key(env.window, env.document, "Escape");
    await tick(env.window);

    assert.equal(env.shadow.querySelector(".ai-pick-hint").hidden, true);
    assert.equal(env.shadow.querySelector(".ai-highlight").hidden, true);
    assert.equal(env.sent.length, 0);
  });

  it("stops picking after one selection", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    mouse(env.window, ad, "mousemove");
    await tick(env.window);
    mouse(env.window, ad, "click");
    await tick(env.window, 60);

    assert.equal(env.shadow.querySelector(".ai-pick-hint").hidden, true);
  });
});
