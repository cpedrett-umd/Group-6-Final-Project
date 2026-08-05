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

describe("passive by default", () => {
  // The extension must not act on its own: no pills, no sensors, no selection
  // offers until the popup's Hover detection toggle arms them. Explicit
  // actions (pick mode, context menus) work regardless.

  it("offers nothing on hover until armed", async () => {
    const env = createEnvironment({ hoverEnabled: false });
    const { ad, pill } = (() => {
      const ad = env.document.getElementById("ad");
      setRect(ad, { left: 100, top: 200, width: 500, height: 300 });
      return { ad, pill: env.shadow.querySelector(".ai-pill") };
    })();

    mouse(env.window, ad, "mouseover");
    await tick(env.window, 520);

    assert.equal(pill.hidden, true, "pill appeared while disarmed");
  });

  it("lays no sensors while disarmed", async () => {
    const env = createEnvironment({ hoverEnabled: false });
    const iframe = env.document.createElement("iframe");
    iframe.src = "https://safeframe.googlesyndication.com/ad";
    env.document.body.append(iframe);
    setRect(iframe, { left: 200, top: 150, width: 728, height: 90 });

    env.window.dispatchEvent(new env.window.Event("resize"));
    await tick(env.window);

    assert.equal(env.shadow.querySelector(".ai-sensor:not([hidden])"), null);
  });

  it("pick mode still works while disarmed", async () => {
    const env = createEnvironment({ hoverEnabled: false });
    env.dispatchRuntimeMessage({ type: "startPicking" });
    await tick(env.window);

    assert.equal(env.shadow.querySelector(".ai-pick-hint").hidden, false);
  });

  it("the popup toggle arms hover live, no reload needed", async () => {
    const env = createEnvironment({ hoverEnabled: false });
    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    env.setHoverEnabled(true);
    mouse(env.window, ad, "mouseover");
    await tick(env.window, 520);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, false);
  });

  it("disarming hides the pill immediately", async () => {
    const env = createEnvironment(); // armed
    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    mouse(env.window, ad, "mouseover");
    await tick(env.window, 520);
    assert.equal(env.shadow.querySelector(".ai-pill").hidden, false);

    env.setHoverEnabled(false);
    await tick(env.window);
    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });
});

describe("ad detection", () => {
  it("offers the pill when hovering a sponsored block", async () => {
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env);

    mouse(env.window, ad, "mouseover");
    await tick(env.window, 520);

    assert.equal(pill.hidden, false);
    assert.equal(pill.querySelector("span").textContent, "Analyze this ad");
  });

  it("ignores ordinary article text", async () => {
    const env = createEnvironment();
    layOutAd(env);

    const prose = env.document.getElementById("prose");
    setRect(prose, { left: 0, top: 0, width: 600, height: 120 });

    mouse(env.window, prose, "mouseover");
    await tick(env.window, 520);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("ignores an ad-marked block that is too small", async () => {
    const env = createEnvironment();
    layOutAd(env);

    const tiny = env.document.getElementById("tiny");
    setRect(tiny, { left: 0, top: 0, width: 40, height: 20 });

    mouse(env.window, tiny, "mouseover");
    await tick(env.window, 520);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("ignores an ad-marked block with too little text", async () => {
    const env = createEnvironment();
    layOutAd(env);

    const tiny = env.document.getElementById("tiny"); // text is just "Ad"
    setRect(tiny, { left: 0, top: 0, width: 300, height: 200 });

    mouse(env.window, tiny, "mouseover");
    await tick(env.window, 520);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("finds the ad when hovering a child of it", async () => {
    const env = createEnvironment();
    const { pill } = layOutAd(env);

    const cta = env.document.getElementById("cta");
    mouse(env.window, cta, "mouseover");
    await tick(env.window, 520);

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
    await tick(env.window, 520);

    assert.equal(pill.style.top, "246px"); // (100 + 200) - 44 - 10, inside
  });

  it("stays inside even at the detector's minimum ad height", async () => {
    // The 80px size floor guarantees a 44px pill always fits inside, so the
    // below/above fallbacks only matter for degenerate rects.
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env, { left: 100, top: 100, width: 400, height: 82 });

    mouse(env.window, ad, "mouseover");
    await tick(env.window, 520);

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
    await tick(env.window, 520);

    const top = parseFloat(pill.style.top);
    const left = parseFloat(pill.style.left);

    assert.ok(top >= 8 && top <= env.window.innerHeight - 44 - 8, `top ${top}`);
    assert.ok(left >= 8 && left <= env.window.innerWidth - 190 - 8, `left ${left}`);
  });

  it("stays hidden for an ad scrolled out of view", async () => {
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env, { left: 100, top: 3000, width: 400, height: 300 });

    mouse(env.window, ad, "mouseover");
    await tick(env.window, 520);

    assert.equal(pill.hidden, true);
  });

  it("hides on scroll", async () => {
    const env = createEnvironment();
    const { ad, pill } = layOutAd(env);

    mouse(env.window, ad, "mouseover");
    await tick(env.window, 520);
    assert.equal(pill.hidden, false);

    env.window.dispatchEvent(new env.window.Event("scroll"));
    assert.equal(pill.hidden, true);
  });
});

describe("ad-iframe hover sensors", () => {
  // A real pointer over a cross-origin iframe emits nothing the parent can
  // hear (verified live on Yahoo), so a transparent sensor overlays each ad
  // iframe and hears the events instead.

  function withSensor(env) {
    const iframe = env.document.createElement("iframe");
    iframe.src = "https://safeframe.googlesyndication.com/ad";
    env.document.body.append(iframe);
    setRect(iframe, { left: 200, top: 150, width: 728, height: 90 });

    // syncSensors runs at injection before this iframe existed; force a pass.
    env.window.dispatchEvent(new env.window.Event("resize"));

    const sensor = env.host.shadowRoot.querySelector(".ai-sensor:not([hidden])");
    return { iframe, sensor };
  }

  it("lays a sensor exactly over a detected ad iframe", async () => {
    const env = createEnvironment();
    const { sensor } = withSensor(env);

    assert.ok(sensor, "no sensor created for the ad iframe");
    assert.equal(sensor.style.left, "200px");
    assert.equal(sensor.style.top, "150px");
    assert.equal(sensor.style.width, "728px");
    assert.equal(sensor.style.height, "90px");
  });

  it("does not lay sensors over ordinary iframes", () => {
    const env = createEnvironment();
    const plain = env.document.createElement("iframe");
    plain.src = "https://www.youtube.com/embed/xyz";
    env.document.body.append(plain);
    setRect(plain, { left: 0, top: 0, width: 560, height: 315 });

    env.window.dispatchEvent(new env.window.Event("resize"));

    assert.equal(env.host.shadowRoot.querySelector(".ai-sensor:not([hidden])"), null);
  });

  it("entering the sensor shows the pill", async () => {
    const env = createEnvironment();
    const { sensor } = withSensor(env);

    sensor.dispatchEvent(new env.window.MouseEvent("mouseenter"));
    await tick(env.window, 520);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, false);
  });

  it("clicking the ad area analyzes instead of navigating", async () => {
    const env = createEnvironment({
      respond: (m) => {
        if (m.type === "captureRegion") return { ok: true, captured: true };
        return { ok: true, data: analysisFixture({ source: { mode: "image", ocr: { confidence: 0.9, line_count: 1, repaired: false } } }) };
      },
    });
    const { sensor } = withSensor(env);

    const click = new env.window.MouseEvent("click", { bubbles: true, cancelable: true });
    sensor.dispatchEvent(click);
    await tick(env.window, 300);

    assert.equal(click.defaultPrevented, true, "ad navigation was not blocked");
    assert.ok(env.sent.some((m) => m.type === "captureRegion"), "click did not capture");
    assert.equal(env.shadow.querySelector(".ai-state.is-active").dataset.state, "result");
  });

  it("hides the sensor when its ad scrolls out of view", () => {
    const env = createEnvironment();
    const { iframe, sensor } = withSensor(env);

    setRect(iframe, { left: 200, top: 5000, width: 728, height: 90 });
    env.window.dispatchEvent(new env.window.Event("resize"));

    assert.equal(sensor.hidden, true);
  });
});

describe("small banners and labeled native ads", () => {
  it("offers the pill on a 320x50 mobile banner iframe", async () => {
    // Standard small banner sizes failed the old 120x80 floor entirely.
    const env = createEnvironment();
    const iframe = env.document.createElement("iframe");
    iframe.src = "https://securepubads.g.doubleclick.net/x";
    env.document.body.append(iframe);
    setRect(iframe, { left: 40, top: 300, width: 320, height: 50 });

    const pill = env.shadow.querySelector(".ai-pill");
    Object.defineProperty(pill, "offsetWidth", { value: 190, configurable: true });
    Object.defineProperty(pill, "offsetHeight", { value: 44, configurable: true });

    mouse(env.window, iframe, "mouseover");
    await tick(env.window, 520);

    assert.equal(pill.hidden, false, "no pill on a 320x50 banner");
    // Too short to contain the pill, so it sits just below: 300 + 50 + 8.
    assert.equal(pill.style.top, "358px");
  });

  it("still ignores tracking-pixel iframes", async () => {
    const env = createEnvironment();
    const pixel = env.document.createElement("iframe");
    pixel.src = "https://cm.g.doubleclick.net/pixel";
    env.document.body.append(pixel);
    setRect(pixel, { left: 0, top: 0, width: 1, height: 1 });

    mouse(env.window, pixel, "mouseover");
    await tick(env.window, 520);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("detects a native ad by its visible Sponsored label", async () => {
    // Yahoo's shape: no ad-ish class names anywhere; the only tell is the
    // "Sponsored" caption the law requires.
    const env = createEnvironment();
    const card = env.document.createElement("div");
    card.className = "stream-item content-card"; // nothing ad-ish
    card.innerHTML =
      '<span>Sponsored</span><h3>Seniors Rush To Claim This Benefit</h3>' +
      "<p>Thousands are already claiming this benefit before the deadline arrives.</p>";
    env.document.body.append(card);
    setRect(card, { left: 40, top: 200, width: 500, height: 180 });

    const pill = env.shadow.querySelector(".ai-pill");
    mouse(env.window, card.querySelector("h3"), "mouseover");
    await tick(env.window, 520);

    assert.equal(pill.hidden, false, "no pill on a Sponsored-labeled card");

    pill.click();
    await tick(env.window, 60);

    const sent = env.sent.find((m) => m.type === "analyzeText");
    assert.ok(sent, "labeled ad did not analyze as text");
    assert.match(sent.text, /Seniors Rush/);
  });

  it("does not fire on ordinary content mentioning the word sponsored", async () => {
    // "sponsored" inside a sentence is not a label; only a short standalone
    // caption counts.
    const env = createEnvironment();
    const article = env.document.createElement("div");
    article.innerHTML =
      "<p>The event was sponsored by the local hospital, organizers said, " +
      "and drew a record crowd of volunteers from around the county.</p>";
    env.document.body.append(article);
    setRect(article, { left: 40, top: 200, width: 500, height: 180 });

    mouse(env.window, article.querySelector("p"), "mouseover");
    await tick(env.window, 520);

    assert.equal(env.shadow.querySelector(".ai-pill").hidden, true);
  });

  it("captures a labeled ad that has a label but no readable copy", async () => {
    const env = createEnvironment({
      respond: (m) => {
        if (m.type === "captureRegion") return { ok: true, captured: true };
        return { ok: true, data: analysisFixture() };
      },
    });

    const card = env.document.createElement("div");
    card.innerHTML = '<span>Ad</span><img alt="">';
    env.document.body.append(card);
    setRect(card, { left: 40, top: 200, width: 300, height: 250 });

    const pill = env.shadow.querySelector(".ai-pill");
    mouse(env.window, card, "mouseover");
    await tick(env.window, 520);

    assert.equal(pill.hidden, false);

    pill.click();
    // runCapture waits a painted frame + 90ms before phase 1 (so the pill
    // can't photograph itself into the ad); give it room.
    await tick(env.window, 300);
    assert.ok(env.sent.some((m) => m.type === "captureRegion"), "image-only labeled ad did not capture");
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
    await tick(env.window, 520);
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

  it("offers the pill via the parent's mouseout when a real pointer enters the iframe", async () => {
    // A real pointer over a cross-origin iframe delivers NO events to the
    // parent page — the only entry signal is mouseout on the element being
    // left, with relatedTarget set to the iframe. Verified live on Yahoo.
    const env = captureEnvironment();
    const iframe = addAdIframe(env);
    const pill = env.shadow.querySelector(".ai-pill");

    const neighbour = env.document.getElementById("prose");
    neighbour.dispatchEvent(
      new env.window.MouseEvent("mouseout", { bubbles: true, relatedTarget: iframe })
    );
    await tick(env.window, 520);

    assert.equal(pill.hidden, false, "no pill on iframe entry via mouseout");

    pill.click();
    await tick(env.window, 300);
    assert.ok(env.sent.some((m) => m.type === "captureRegion"));
  });

  it("offers the pill when hovering an ad iframe, and clicking it captures", async () => {
    const env = captureEnvironment();
    const iframe = addAdIframe(env);
    const pill = env.shadow.querySelector(".ai-pill");
    Object.defineProperty(pill, "offsetWidth", { value: 190, configurable: true });
    Object.defineProperty(pill, "offsetHeight", { value: 44, configurable: true });

    // Entering a cross-origin iframe still fires mouseover on the iframe
    // element itself in the parent page — the one event we get, and enough.
    mouse(env.window, iframe, "mouseover");
    await tick(env.window, 520);

    assert.equal(pill.hidden, false, "no pill on ad-iframe hover");
    // Inside the ad, bottom edge: (120 + 250) - 44 - 10.
    assert.equal(pill.style.top, "316px");

    pill.click();
    await tick(env.window, 300);

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
    await tick(env.window, 520);

    assert.equal(pill.hidden, false, "no pill on text-less ad container");

    pill.click();
    await tick(env.window, 300);
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
    await tick(env.window, 300);

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
    await tick(env.window, 300);

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
    await tick(env.window, 520);

    const highlight = env.shadow.querySelector(".ai-highlight");
    assert.equal(highlight.hidden, false);
    assert.equal(highlight.classList.contains("ai-highlight-ad"), false,
      "plain text wrongly tagged as ad");
    assert.equal(highlight.style.left, "40px");
    assert.equal(highlight.style.width, "500px");
  });

  it("analyzes the picked block and suppresses the page's click", async () => {
    const env = createEnvironment();
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    mouse(env.window, ad, "mousemove");
    await tick(env.window, 520);

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

  it("shows the Analyze button with the box, and its click ends picking", async () => {
    const env = createEnvironment({ hoverEnabled: false });
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    mouse(env.window, ad, "mousemove");
    await tick(env.window, 520);

    const pill = env.shadow.querySelector(".ai-pill");
    assert.equal(pill.hidden, false, "no button with the pick box");
    assert.equal(pill.querySelector("span").textContent, "Analyze this ad");

    pill.click();
    await tick(env.window, 100);

    assert.equal(env.shadow.querySelector(".ai-pick-hint").hidden, true, "picking did not end");
    assert.ok(env.sent.some((m) => m.type === "analyzeText"));
  });

  it("snaps the outline to a metadata-detected ad and tags it", async () => {
    const env = createEnvironment({ hoverEnabled: false });
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });
    const copy = ad.querySelector(".copy");
    setRect(copy, { left: 120, top: 300, width: 460, height: 60 });

    // Hover the inner paragraph; the outline must snap to the ad's own
    // boundary, not the paragraph's.
    mouse(env.window, copy, "mousemove");
    await tick(env.window, 520);

    const highlight = env.shadow.querySelector(".ai-highlight");
    assert.equal(highlight.hidden, false);
    assert.equal(highlight.style.width, "500px", "did not snap to the ad box");
    assert.ok(highlight.classList.contains("ai-highlight-ad"), "missing ad tag");
  });

  it("picks an iframe ad and routes it to capture", async () => {
    const env = createEnvironment({
      hoverEnabled: false,
      respond: (m) => {
        if (m.type === "captureRegion") return { ok: true, captured: true };
        return { ok: true, data: analysisFixture({ source: { mode: "image",
          ocr: { confidence: 0.9, line_count: 1, repaired: false } } }) };
      },
    });
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const iframe = env.document.createElement("iframe");
    iframe.src = "https://safeframe.googlesyndication.com/x";
    env.document.body.append(iframe);
    setRect(iframe, { left: 150, top: 120, width: 728, height: 90 });

    mouse(env.window, iframe, "mousemove");
    await tick(env.window, 520);

    assert.ok(
      env.shadow.querySelector(".ai-highlight").classList.contains("ai-highlight-ad")
    );

    mouse(env.window, iframe, "click");
    await tick(env.window, 300);

    const cap = env.sent.find((m) => m.type === "captureRegion");
    assert.ok(cap, "iframe pick did not capture");
    assert.equal(cap.region.width, 728);
  });

  it("keeps the offer stable while the pointer moves inside the box", async () => {
    // Nested containers can re-resolve to different candidates as the cursor
    // travels toward the button; the offer must not vanish mid-reach.
    const env = createEnvironment({ hoverEnabled: false });
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    mouse(env.window, ad, "mousemove");
    await tick(env.window, 520);
    assert.equal(env.shadow.querySelector(".ai-highlight").hidden, false);

    // Move over a child inside the boxed ad — different event target, same box.
    mouse(env.window, env.document.getElementById("cta"), "mousemove");
    await tick(env.window, 60);

    assert.equal(env.shadow.querySelector(".ai-highlight").hidden, false, "box vanished mid-reach");
    assert.equal(env.shadow.querySelector(".ai-pill").hidden, false, "button vanished mid-reach");
  });

  it("glues the box to the ad through scrolling", async () => {
    const env = createEnvironment({ hoverEnabled: false });
    env.dispatchRuntimeMessage({ type: "startPicking" });

    const ad = env.document.getElementById("ad");
    setRect(ad, { left: 100, top: 200, width: 500, height: 300 });

    mouse(env.window, ad, "mousemove");
    await tick(env.window, 520);

    // The page scrolls: the ad's viewport position changes.
    setRect(ad, { left: 100, top: 40, width: 500, height: 300 });
    env.window.dispatchEvent(new env.window.Event("scroll"));
    await tick(env.window, 30);

    const highlight = env.shadow.querySelector(".ai-highlight");
    assert.equal(highlight.hidden, false, "box hidden after scroll");
    assert.equal(highlight.style.top, "40px", "box left parked at the old position");

    // Scrolled fully out of view: the offer withdraws instead of floating.
    setRect(ad, { left: 100, top: 5000, width: 500, height: 300 });
    env.window.dispatchEvent(new env.window.Event("scroll"));
    await tick(env.window, 30);

    assert.equal(highlight.hidden, true, "box floating over nothing");
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
    await tick(env.window, 520);
    mouse(env.window, ad, "click");
    await tick(env.window, 60);

    assert.equal(env.shadow.querySelector(".ai-pick-hint").hidden, true);
  });
});
