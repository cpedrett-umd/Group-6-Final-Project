/* AdInsight overlay — the browser-extension surface.
 *
 * Renders the same panel as the app, over whatever page the user is reading.
 * Everything lives inside a shadow root so the host page's CSS can't reach in
 * and the panel's CSS can't leak out; on a news site with aggressive global
 * styles, an un-isolated overlay is unreadable within seconds.
 *
 * The panel's markup and rendering deliberately mirror app/static/app.js.
 * Sharing one module between the two would need a build step, which is not
 * worth adding to a course demo -- but if the panel's copy changes, it has to
 * change in both places.
 *
 * Three ways to trigger it:
 *   - hover a block that looks like an ad  -> a floating "Analyze this ad" pill
 *   - select text                          -> the same pill, over the selection
 *   - right-click text or an image         -> context menu (see background.js)
 */

(() => {
  "use strict";

  // Guard against double injection (SPA navigations, manual re-injection).
  if (window.__adinsightLoaded) return;
  window.__adinsightLoaded = true;

  const MIN_SELECTION = 20;

  // Markup patterns real ad slots use. Deliberately conservative -- a false
  // positive puts a button on ordinary content, which is worse than missing an
  // ad the user can still select by hand.
  const AD_SELECTOR = [
    '[class*="sponsored" i]',
    '[id*="sponsored" i]',
    '[class*="ad-slot" i]',
    '[id*="ad-slot" i]',
    '[class*="advertisement" i]',
    '[aria-label*="advertisement" i]',
    "ins.adsbygoogle",
    "[data-ad]",
  ].join(",");

  /* ── Shadow host ────────────────────────────────────────────── */

  const host = document.createElement("div");
  host.id = "adinsight-root";
  // Sits above the page but below nothing of ours; the panel manages its own
  // stacking inside the shadow root.
  // Zero-sized so the host itself never affects the page's layout; the pill and
  // panel inside are position:fixed and size themselves.
  host.style.cssText =
    "all: initial; position: fixed; top: 0; left: 0; width: 0; height: 0; z-index: 2147483647;";

  const shadow = host.attachShadow({ mode: "open" });

  const styles = document.createElement("link");
  styles.rel = "stylesheet";
  styles.href = chrome.runtime.getURL("panel.css");
  shadow.append(styles);

  const wrap = document.createElement("div");
  wrap.className = "ai-wrap";
  wrap.innerHTML = `
    <button class="ai-pill" type="button" hidden>
      <svg viewBox="0 0 24 24" width="19" height="19" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2.4"/><line x1="15.5" y1="15.5" x2="21" y2="21" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
      <span>Analyze this ad</span>
    </button>

    <section class="ai-panel" hidden aria-live="polite">
      <header class="ai-head">
        <div class="ai-brand">
          <span class="ai-mark">
            <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2.4"/><line x1="15.5" y1="15.5" x2="21" y2="21" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
          </span>
          <span>AdInsight</span>
        </div>
        <button class="ai-close" type="button" aria-label="Close">&times;</button>
      </header>

      <div class="ai-body">

        <div class="ai-state" data-state="busy">
          <div class="ai-spinner"></div>
          <p class="ai-busy-copy">Reading the ad…</p>
        </div>

        <div class="ai-state" data-state="error">
          <div class="ai-callout ai-callout-error">
            <p class="ai-callout-head">Couldn't analyze that.</p>
            <p class="ai-callout-msg"></p>
          </div>
        </div>

        <div class="ai-state" data-state="result">
          <div class="ai-callout">
            <span class="ai-callout-icon">!</span>
            <div>
              <p class="ai-callout-head"></p>
              <p class="ai-callout-msg"></p>
            </div>
          </div>

          <section class="ai-readback" hidden>
            <h3 class="ai-title">What we read from that image</h3>
            <p class="ai-readback-text"></p>
            <p class="ai-readback-meta"></p>
          </section>

          <section>
            <h3 class="ai-title">What this ad is doing</h3>
            <ul class="ai-tactics"></ul>
          </section>

          <section class="ai-reviews-section">
            <h3 class="ai-title">What real customers say
              <span class="ai-mock-badge">sample data</span>
            </h3>
            <p class="ai-mock-notice"></p>
            <ul class="ai-reviews"></ul>
          </section>

          <details class="ai-detail">
            <summary>Read the full explanation</summary>
            <div class="ai-detail-body">
              <p class="ai-detail-line">
                The model read this ad as <strong class="ai-detail-label"></strong>
                (<span class="ai-detail-conf"></span> confident).
              </p>
              <p class="ai-detail-note">
                Tuned DistilBERT, trained on 3,230 labeled ads. It picks one main
                tactic; the other rows come from trigger phrases found in the ad's
                own words. The training data has no <em>neutral</em> label, so a low
                score with no matching phrase is shown here rather than reported as
                a finding.
              </p>
              <table class="ai-dist"><tbody></tbody></table>
              <p class="ai-disclaimer">
                AdInsight explains persuasion. It does not judge whether a product
                or seller is fraudulent.
              </p>
            </div>
          </details>
        </div>

      </div>
    </section>
  `;

  shadow.append(wrap);
  (document.body || document.documentElement).append(host);

  const pill = shadow.querySelector(".ai-pill");
  const panel = shadow.querySelector(".ai-panel");

  const $ = (selector) => shadow.querySelector(selector);
  const inResult = (selector) => shadow.querySelector(`[data-state="result"] ${selector}`);

  /* ── Panel state ────────────────────────────────────────────── */

  function showState(name) {
    shadow.querySelectorAll(".ai-state").forEach((node) => {
      node.classList.toggle("is-active", node.dataset.state === name);
    });
  }

  function openPanel(state) {
    panel.hidden = false;
    // Next frame, so the transition runs from the off-screen position.
    requestAnimationFrame(() => panel.classList.add("is-open"));
    showState(state);
  }

  function closePanel() {
    panel.classList.remove("is-open");
    setTimeout(() => {
      panel.hidden = true;
    }, 200);
  }

  function showError(message) {
    shadow.querySelector('[data-state="error"] .ai-callout-msg').textContent = message;
    openPanel("error");
  }

  $(".ai-close").addEventListener("click", closePanel);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) closePanel();
  });

  /* ── The floating pill ──────────────────────────────────────── */

  let pillPayload = null;
  let hideTimer = null;

  function isOnScreen(rect) {
    return (
      rect.bottom > 0 &&
      rect.top < window.innerHeight &&
      rect.right > 0 &&
      rect.left < window.innerWidth
    );
  }

  function showPill(rect, payload, label) {
    // A target scrolled out of view would put the pill off-screen, where it
    // still swallows clicks. Only offer it for something the user can see.
    if (!isOnScreen(rect)) {
      hidePill();
      return;
    }

    pillPayload = payload;
    pill.querySelector("span").textContent = label || "Analyze this ad";
    pill.hidden = false;

    // Measure after unhiding so the size is real.
    const width = pill.offsetWidth || 190;
    const height = pill.offsetHeight || 44;

    const maxLeft = window.innerWidth - width - 8;
    const maxTop = window.innerHeight - height - 8;

    let top = rect.bottom + 8;

    // Prefer below the target; flip above when there's no room.
    if (top > maxTop) {
      top = rect.top - height - 8;
    }

    const left = Math.max(8, Math.min(rect.left + rect.width / 2 - width / 2, maxLeft));

    // Whichever side was chosen, the pill must end up inside the viewport --
    // a tall ad can leave neither edge with room.
    pill.style.left = `${left}px`;
    pill.style.top = `${Math.max(8, Math.min(top, maxTop))}px`;
  }

  function hidePill() {
    pill.hidden = true;
    pillPayload = null;
  }

  function scheduleHide() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hidePill, 400);
  }

  function cancelHide() {
    clearTimeout(hideTimer);
  }

  pill.addEventListener("mouseenter", cancelHide);
  pill.addEventListener("mouseleave", scheduleHide);

  pill.addEventListener("click", () => {
    if (pillPayload) analyze(pillPayload);
    hidePill();
  });

  /* ── Trigger 1: hovering something that looks like an ad ────── */

  function isPlausibleAd(element) {
    const rect = element.getBoundingClientRect();

    // Big enough to be a real slot, small enough not to be the whole page.
    if (rect.width < 120 || rect.height < 80) return false;
    if (rect.width > window.innerWidth * 0.95 && rect.height > window.innerHeight * 0.9) {
      return false;
    }

    // Needs enough words for the classifier to have anything to read.
    return (element.innerText || "").trim().length >= 40;
  }

  document.addEventListener(
    "mouseover",
    (event) => {
      const target = event.target;
      if (!target || typeof target.closest !== "function") return;
      if (host.contains(target)) return;

      let candidate = null;
      try {
        candidate = target.closest(AD_SELECTOR);
      } catch (error) {
        return; // Malformed selector support varies; fail quiet.
      }

      if (!candidate || !isPlausibleAd(candidate)) return;

      cancelHide();
      showPill(candidate.getBoundingClientRect(), {
        text: candidate.innerText.trim(),
      });
    },
    true
  );

  document.addEventListener(
    "mouseout",
    (event) => {
      if (host.contains(event.target)) return;
      scheduleHide();
    },
    true
  );

  /* ── Trigger 2: selecting text ──────────────────────────────── */

  document.addEventListener("mouseup", (event) => {
    if (host.contains(event.target)) return;

    // Let the selection settle before reading it.
    setTimeout(() => {
      const selection = window.getSelection();
      const text = selection ? selection.toString().trim() : "";

      if (text.length < MIN_SELECTION) return;

      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();

      if (!rect || (!rect.width && !rect.height)) return;

      cancelHide();
      showPill(rect, { text: text }, "Analyze this text");
    }, 10);
  });

  window.addEventListener("scroll", hidePill, { passive: true });
  window.addEventListener("resize", hidePill);

  /* ── Trigger 3: pick mode — hover anything, click to analyze ── */

  /* Automatic detection only fires on blocks whose markup says "ad". Plenty of
   * sites don't mark them that way, so pick mode is the guaranteed path: it
   * outlines whatever is under the cursor and analyzes it on click.
   *
   * The outline is drawn as our own fixed-position box rather than by setting
   * `style.outline` on the page's element -- mutating the host page's styles
   * can trigger its own layout/observer code. */

  let picking = false;
  let pickTarget = null;

  const highlight = document.createElement("div");
  highlight.className = "ai-highlight";
  highlight.hidden = true;

  const pickHint = document.createElement("div");
  pickHint.className = "ai-pick-hint";
  pickHint.hidden = true;
  pickHint.textContent = "Click an ad to analyze it · Esc to cancel";

  wrap.append(highlight, pickHint);

  function smallestTextBlock(element) {
    // Walk up from the hovered node until there's enough text to classify.
    let node = element;

    while (node && node !== document.body) {
      const text = (node.innerText || "").trim();
      const rect = node.getBoundingClientRect();

      if (text.length >= 25 && rect.width > 60 && rect.height > 24) return node;

      node = node.parentElement;
    }

    return null;
  }

  function startPicking() {
    picking = true;
    pickHint.hidden = false;
    hidePill();
    closePanel();
  }

  function stopPicking() {
    picking = false;
    pickTarget = null;
    highlight.hidden = true;
    pickHint.hidden = true;
  }

  document.addEventListener(
    "mousemove",
    (event) => {
      if (!picking || host.contains(event.target)) return;

      const target = smallestTextBlock(event.target);

      if (!target) {
        highlight.hidden = true;
        pickTarget = null;
        return;
      }

      pickTarget = target;

      const rect = target.getBoundingClientRect();
      highlight.hidden = false;
      highlight.style.left = `${rect.left}px`;
      highlight.style.top = `${rect.top}px`;
      highlight.style.width = `${rect.width}px`;
      highlight.style.height = `${rect.height}px`;
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      if (!picking || host.contains(event.target)) return;

      // Stop the page acting on the click -- picking an ad must not follow
      // the ad's link.
      event.preventDefault();
      event.stopPropagation();

      const target = pickTarget || smallestTextBlock(event.target);

      stopPicking();

      if (target) analyze({ text: (target.innerText || "").trim() });
    },
    true
  );

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && picking) stopPicking();
  });

  /* ── Trigger 4: the context menu / popup (from background.js) ─ */

  chrome.runtime.onMessage.addListener((message) => {
    if (!message) return;

    if (message.type === "analyze") analyze(message.payload);
    if (message.type === "startPicking") startPicking();
  });

  /* ── Analysis ───────────────────────────────────────────────── */

  async function analyze(payload) {
    $(".ai-busy-copy").textContent = payload.imageUrl
      ? "Reading the words off that image…"
      : "Reading the ad…";

    openPanel("busy");

    const request = payload.imageUrl
      ? { type: "analyzeImage", imageUrl: payload.imageUrl }
      : { type: "analyzeText", text: payload.text };

    let response;

    try {
      response = await chrome.runtime.sendMessage(request);
    } catch (error) {
      showError("The extension couldn't reach its background worker. Try reloading the page.");
      return;
    }

    if (!response) {
      showError("No response from the AdInsight server.");
      return;
    }

    if (!response.ok) {
      showError(response.error || (response.data && response.data.error) || "That ad couldn't be analyzed.");
      return;
    }

    render(response.data);
  }

  /* ── Rendering ──────────────────────────────────────────────── */

  const percent = (value) => `${Math.round(value * 100)}%`;

  function render(data) {
    const callout = inResult(".ai-callout");
    callout.classList.toggle("is-calm", data.summary.tone === "calm");
    inResult(".ai-callout-head").textContent = data.summary.headline;
    inResult(".ai-callout-msg").textContent = data.summary.message;

    // Read-back: only for image input, so a bad scan stays visible.
    const readback = inResult(".ai-readback");

    if (data.source.mode === "image" && data.source.ocr) {
      const ocr = data.source.ocr;
      inResult(".ai-readback-text").textContent = `“${data.text}”`;

      const bits = [
        `${ocr.line_count} ${ocr.line_count === 1 ? "line" : "lines"} read`,
        `${percent(ocr.confidence)} confident`,
      ];

      if (ocr.repaired) bits.push("spacing repaired");

      inResult(".ai-readback-meta").textContent =
        `${bits.join(" · ")}. If this looks wrong, select the ad's text instead.`;
      readback.hidden = false;
    } else {
      readback.hidden = true;
    }

    // Tactic rows. `uncertain` rows are the model's forced pick with no phrase
    // evidence — not a finding. Still visible in the distribution below.
    const list = inResult(".ai-tactics");
    list.replaceChildren();

    const findings = data.tactics.filter((tactic) => !tactic.uncertain);

    if (findings.length === 0) {
      const empty = document.createElement("li");
      empty.className = "ai-tactic-empty";
      empty.textContent = "No pressure tactics stood out in these words.";
      list.append(empty);
    }

    findings.forEach((tactic) => {
      const item = document.createElement("li");
      item.className = "ai-tactic";

      const dot = document.createElement("span");
      dot.className = "ai-dot";

      const body = document.createElement("div");

      const name = document.createElement("div");
      name.className = "ai-tactic-name";
      name.append(tactic.display);

      tactic.sources.forEach((source) => {
        const badge = document.createElement("span");
        badge.className = `ai-src ai-src-${source}`;
        badge.textContent = source === "model" ? "model pick" : "phrase found";
        name.append(badge);
      });

      if (tactic.sources.includes("model")) {
        const conf = document.createElement("span");
        conf.className = "ai-conf";
        conf.textContent = `${percent(tactic.confidence)} confident`;
        name.append(conf);
      }

      const why = document.createElement("p");
      why.className = "ai-tactic-why";
      why.textContent = tactic.explanation;

      body.append(name, why);
      item.append(dot, body);
      list.append(item);
    });

    // Review layer (stub)
    inResult(".ai-mock-notice").textContent = data.reviews.notice || "";
    inResult(".ai-mock-badge").hidden = !data.reviews.mock;

    const reviewList = inResult(".ai-reviews");
    reviewList.replaceChildren();

    data.reviews.items.forEach((review) => {
      const item = document.createElement("li");
      item.className = "ai-review";

      const source = document.createElement("span");
      source.className = "ai-review-src";
      source.textContent = review.rating ? `${review.source} · ${review.rating}` : review.source;

      const quote = document.createElement("p");
      quote.className = "ai-review-quote";
      quote.textContent = `“${review.quote}”`;

      item.append(source, quote);
      reviewList.append(item);
    });

    // Full explanation
    inResult(".ai-detail-label").textContent = data.prediction.label;
    inResult(".ai-detail-conf").textContent = percent(data.prediction.confidence);

    const body = inResult(".ai-dist tbody");
    body.replaceChildren();

    data.prediction.distribution.forEach((entry, index) => {
      const row = document.createElement("tr");
      if (index === 0) row.className = "is-top";

      const label = document.createElement("td");
      label.textContent = entry.label;

      const barCell = document.createElement("td");
      const bar = document.createElement("div");
      bar.className = "ai-bar";
      const fill = document.createElement("span");
      fill.style.width = `${Math.max(entry.confidence * 100, 1)}%`;
      bar.append(fill);
      barCell.append(bar);

      const value = document.createElement("td");
      value.textContent = percent(entry.confidence);

      row.append(label, barCell, value);
      body.append(row);
    });

    openPanel("result");
  }
})();
