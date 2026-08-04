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

    // Sit INSIDE the ad, along its bottom edge. Overlapping the ad means the
    // pointer never has to leave the ad's box to reach the button, so the
    // hover can't be stolen by whatever sits next to the ad on the page. Only
    // an ad too short to contain the pill gets it placed just below instead.
    let top;

    if (rect.height >= height + 20) {
      top = rect.bottom - height - 10;
    } else if (rect.bottom + 8 <= maxTop) {
      top = rect.bottom + 8;
    } else {
      top = rect.top - height - 8;
    }

    const left = Math.max(8, Math.min(rect.left + rect.width / 2 - width / 2, maxLeft));

    // Whichever spot was chosen, the pill must end up inside the viewport --
    // a tall ad half off screen can leave no edge with room.
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
    const payload = pillPayload;
    hidePill();

    if (!payload) return;

    if (payload.captureElement) {
      // Unreadable ad (iframe / video): screenshot it. Measure at click time,
      // not hover time -- the page may have scrolled in between.
      runCapture(payload.captureElement.getBoundingClientRect());
    } else {
      analyze(payload);
    }
  });

  /* ── Trigger 1: hovering something that looks like an ad ────── */

  // Iframes serving from these hosts are display ads; their contents are
  // unreadable (cross-origin), but their on-screen box is capturable.
  const AD_FRAME_PATTERN =
    /doubleclick|googlesyndication|safeframe|adsystem|amazon-adsystem|criteo|taboola|outbrain|adnxs|yieldmo|rubiconproject/i;

  function isSensibleSlotSize(rect) {
    // Big enough to be a real slot, small enough not to be the whole page.
    // The floor accommodates the small standard banner sizes — 320x50 and
    // 468x60 are everywhere — while still excluding tracking pixels and
    // sliver iframes.
    if (rect.width < 100 || rect.height < 40) return false;
    if (rect.width > window.innerWidth * 0.95 && rect.height > window.innerHeight * 0.9) {
      return false;
    }
    return true;
  }

  // The words sites are required to put on native ads. A block carrying one of
  // these as a short, standalone label is an ad regardless of its class names,
  // which is what makes detection work on sites (Yahoo among them) whose
  // markup never says "ad".
  const SPONSOR_LABELS = new Set([
    "ad", "ads", "advertisement", "sponsored", "promoted", "paid content",
    "paid post", "partner content", "sponsored content", "sponsored by",
  ]);

  function hasSponsoredLabel(element) {
    // Only short-tag descendants, capped, so hovering a huge container stays
    // cheap. The label itself is always a tiny element.
    const nodes = element.querySelectorAll("span, small, sup, b, p, div, a");
    const limit = Math.min(nodes.length, 60);

    for (let index = 0; index < limit; index += 1) {
      const node = nodes[index];
      // A label has no element children and almost no text.
      if (node.childElementCount !== 0) continue;

      const text = (node.textContent || "").trim().toLowerCase().replace(/[:·|]+$/, "").trim();
      if (text.length <= 20 && SPONSOR_LABELS.has(text)) return true;
    }

    return false;
  }

  /** The nearest hovered ancestor that reads as a labeled native ad. */
  function labeledAdContainer(target) {
    let node = target;
    let depth = 0;

    while (node && node !== document.body && depth < 8) {
      const rect = node.getBoundingClientRect();

      // Stop growing once the candidate stops looking like a card.
      if (rect.width > window.innerWidth * 0.95 && rect.height > window.innerHeight * 0.9) {
        return null;
      }

      if (isSensibleSlotSize(rect) && hasSponsoredLabel(node)) return node;

      node = node.parentElement;
      depth += 1;
    }

    return null;
  }

  function isPlausibleAd(element) {
    if (!isSensibleSlotSize(element.getBoundingClientRect())) return false;

    // Needs enough words for the classifier to have anything to read.
    return (element.innerText || "").trim().length >= 40;
  }

  function isAdFrame(element) {
    if (!element || element.tagName !== "IFRAME") return false;
    const identity = (element.src || "") + (element.id || "") + (element.name || "");
    return AD_FRAME_PATTERN.test(identity);
  }

  /** The capturable ad element for a hover target, or null. */
  function captureCandidate(target) {
    // Hovering the ad iframe itself: the parent page gets a mouseover on the
    // iframe *element* when the pointer enters its box (events inside it stay
    // inside it, but entry is observable — enough to offer the pill).
    if (isAdFrame(target) && isSensibleSlotSize(target.getBoundingClientRect())) {
      return target;
    }

    if (target.tagName === "VIDEO" && isSensibleSlotSize(target.getBoundingClientRect())) {
      return target;
    }

    // Hovering an ad-marked container that has no readable text (Yahoo's
    // pattern: the wrapper matches, the words live in a cross-origin iframe
    // inside it). Capturable if it holds an ad iframe or video.
    let container = null;
    try {
      container = target.closest && target.closest(AD_SELECTOR);
    } catch (error) {
      return null;
    }

    if (container && isSensibleSlotSize(container.getBoundingClientRect())) {
      const inner = container.querySelector("iframe, video");
      if (inner) return container;
    }

    return null;
  }

  document.addEventListener(
    "mouseover",
    (event) => {
      const target = event.target;
      if (!target || typeof target.closest !== "function") return;
      if (host.contains(target)) return;

      // Readable ads first: text is cheaper and more reliable than OCR.
      let candidate = null;
      try {
        candidate = target.closest(AD_SELECTOR);
      } catch (error) {
        return; // Malformed selector support varies; fail quiet.
      }

      if (candidate && isPlausibleAd(candidate)) {
        cancelHide();
        showPill(candidate.getBoundingClientRect(), {
          text: candidate.innerText.trim(),
        });
        return;
      }

      // Native ads with no ad-ish markup, found by the visible "Sponsored" /
      // "Ad" label they are required to carry (Yahoo's feed items, most
      // publishers' partner content).
      const labeled = labeledAdContainer(target);

      if (labeled && (labeled.innerText || "").trim().length >= 40) {
        cancelHide();
        showPill(labeled.getBoundingClientRect(), {
          text: labeled.innerText.trim(),
        });
        return;
      }

      // Unreadable ads (iframe / video / text-less ad container): same pill,
      // but clicking it takes the screenshot path.
      const capturable = captureCandidate(target);

      if (capturable) {
        cancelHide();
        showPill(capturable.getBoundingClientRect(), { captureElement: capturable });
        return;
      }

      if (labeled) {
        // Labeled but wordless (image-only native ad): capture it.
        cancelHide();
        showPill(labeled.getBoundingClientRect(), { captureElement: labeled });
      }
    },
    true
  );

  document.addEventListener(
    "mouseout",
    (event) => {
      if (host.contains(event.target)) return;

      // The pointer entering a cross-origin iframe is INVISIBLE to this page:
      // every mouse event while over the ad goes to the ad's own document, so
      // the mouseover path above never fires for exactly the ads that matter
      // most. The one signal the parent does get is this mouseout, whose
      // relatedTarget is the iframe being entered. (Verified live on Yahoo:
      // synthetic mouseover on the iframe shows the pill, a real pointer
      // never delivers one.)
      const entering = event.relatedTarget;

      if (entering && !host.contains(entering)) {
        const capturable = captureCandidate(entering);

        if (capturable) {
          cancelHide();
          showPill(capturable.getBoundingClientRect(), { captureElement: capturable });
          return;
        }
      }

      scheduleHide();
    },
    true
  );

  /* ── Trigger 1b: hover sensors over ad iframes ──────────────── */

  /* A pointer over a cross-origin iframe delivers NO events to this page —
   * verified live: entering Yahoo's ad iframe produced nothing, not even a
   * boundary mouseout. No listener can see it. So for detected ad iframes we
   * lay our own transparent sensor over the ad's box; the sensor is ours, sits
   * above the iframe, and receives real events unconditionally.
   *
   * The sensor also intercepts clicks on the ad, turning them into analysis
   * instead of navigation. For this tool that is the point, not a side effect:
   * the audience is people one impulse-click away from a scam, and the
   * wireframe's whole interaction is "the ad gets an explain button". */

  const sensors = new Map(); // ad element -> sensor div

  function syncSensors() {
    const frames = document.querySelectorAll("iframe, video");
    const wanted = new Set();

    frames.forEach((element) => {
      const isAd =
        element.tagName === "VIDEO" ? false : isAdFrame(element);
      if (!isAd) return;

      const rect = element.getBoundingClientRect();
      if (!isSensibleSlotSize(rect) || !isOnScreen(rect)) return;

      wanted.add(element);

      let sensor = sensors.get(element);

      if (!sensor) {
        sensor = document.createElement("div");
        sensor.className = "ai-sensor";

        sensor.addEventListener("mouseenter", () => {
          cancelHide();
          showPill(element.getBoundingClientRect(), { captureElement: element });
        });

        sensor.addEventListener("mouseleave", scheduleHide);

        sensor.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          hidePill();
          runCapture(element.getBoundingClientRect());
        });

        wrap.append(sensor);
        sensors.set(element, sensor);
      }

      sensor.style.left = `${rect.left}px`;
      sensor.style.top = `${rect.top}px`;
      sensor.style.width = `${rect.width}px`;
      sensor.style.height = `${rect.height}px`;
      sensor.hidden = false;
    });

    // Drop sensors whose ad went away or scrolled out.
    sensors.forEach((sensor, element) => {
      if (!wanted.has(element)) {
        if (!document.contains(element)) {
          sensor.remove();
          sensors.delete(element);
        } else {
          sensor.hidden = true;
        }
      }
    });
  }

  // Ads load late and move with the page; keep sensors in step by reacting to
  // the DOM instead of polling. An ad appearing is a childList mutation; ads
  // moving is a scroll or resize. The debounce coalesces mutation storms
  // (SPA pages fire hundreds per second while hydrating).
  let syncTimer = null;

  function queueSync() {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(syncSensors, 300);
  }

  syncSensors();

  new MutationObserver(queueSync).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  window.addEventListener("scroll", syncSensors, { passive: true });
  window.addEventListener("resize", syncSensors);

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

  /* ── Trigger 4: screenshot capture (video / iframe ads) ─────── */

  /* Display ads usually live in cross-origin iframes, and video ads have no
   * text to read even when they don't -- a content script can see neither.
   * But it *can* see where they are on screen. On right-click we remember the
   * spot; when the user picks "Analyze this ad by screenshot", the worker
   * photographs the tab and crops to the block under that spot. A playing
   * video contributes its current frame, which is what the user was looking
   * at when they right-clicked. */

  let lastContextClick = null;

  document.addEventListener(
    "contextmenu",
    (event) => {
      lastContextClick = {
        x: event.clientX,
        y: event.clientY,
        target: event.target,
      };
    },
    true
  );

  function captureTargetRect() {
    if (!lastContextClick) return null;

    const { x, y, target } = lastContextClick;

    // Prefer the iframe or video whose box contains the click -- that IS the
    // ad on the sites this path exists for. elementFromPoint sees the iframe
    // element itself (never its contents), which is exactly what we want. The
    // remembered event target is the fallback when the point lookup misses
    // (or isn't implemented, as in test DOMs).
    const fromPoint =
      typeof document.elementFromPoint === "function"
        ? document.elementFromPoint(x, y)
        : null;
    const under = fromPoint || target;

    let node = under;
    while (node && node !== document.body) {
      const tag = node.tagName;

      if (tag === "IFRAME" || tag === "VIDEO" || tag === "OBJECT" || tag === "EMBED") {
        return node.getBoundingClientRect();
      }

      let adContainer = null;
      try {
        adContainer = node.matches && node.matches(AD_SELECTOR) ? node : null;
      } catch (error) {
        /* selector support varies; fall through */
      }

      if (adContainer) return node.getBoundingClientRect();

      node = node.parentElement;
    }

    // Nothing ad-shaped in the ancestry: fall back to the nearest block with
    // real size, so the crop is the thing clicked rather than the whole page.
    let block = under;
    while (block && block !== document.body) {
      const rect = block.getBoundingClientRect();
      if (rect.width >= 120 && rect.height >= 80) return rect;
      block = block.parentElement;
    }

    return null;
  }

  async function captureAndAnalyze() {
    const rect = captureTargetRect();

    if (!rect) {
      showError("Right-click on the ad itself, then choose the screenshot option again.");
      return;
    }

    await runCapture(rect);
  }

  async function runCapture(rect) {
    // Keep ALL of our UI hidden through phase 1, so the screenshot can never
    // contain our own pill or panel. Phase 1 is only the screenshot + crop
    // (~100ms), so there is no meaningful feedback gap.
    hidePill();

    if (!panel.hidden) {
      closePanel();
      // closePanel's slide-out takes 200ms before it sets hidden; wait it out
      // or a re-analysis of an ad under the panel photographs the old panel.
      await new Promise((resolve) => setTimeout(resolve, 260));
    }

    // Setting hidden only *requests* a repaint; captureVisibleTab grabs the
    // compositor's current frame, which can still show the pill. Wait for a
    // painted frame plus a little compositor slack — without this the live
    // capture OCR'd our own button's label into the ad's text.
    await new Promise((resolve) =>
      requestAnimationFrame(() => setTimeout(resolve, 90))
    );

    const region = {
      left: Math.max(0, rect.left),
      top: Math.max(0, rect.top),
      width: Math.min(rect.width, window.innerWidth - Math.max(0, rect.left)),
      height: Math.min(rect.height, window.innerHeight - Math.max(0, rect.top)),
      devicePixelRatio: window.devicePixelRatio || 1,
    };

    let captured;

    try {
      captured = await chrome.runtime.sendMessage({ type: "captureRegion", region: region });
    } catch (error) {
      showError("The extension couldn't reach its background worker. Try reloading the page.");
      return;
    }

    if (!captured || !captured.ok) {
      showError((captured && captured.error) || "Couldn't photograph that ad.");
      return;
    }

    // Screenshot is taken -- now the slow part, with the busy panel up.
    $(".ai-busy-copy").textContent = "Reading the words off that ad…";
    openPanel("busy");

    let response;

    try {
      response = await chrome.runtime.sendMessage({ type: "analyzeCapture" });
    } catch (error) {
      showError("The extension couldn't reach its background worker. Try reloading the page.");
      return;
    }

    if (!response || !response.ok) {
      showError(
        (response && (response.error || (response.data && response.data.error))) ||
          "Couldn't analyze that capture."
      );
      return;
    }

    render(response.data);
  }

  /* ── Trigger 5: the context menu / popup (from background.js) ─ */

  chrome.runtime.onMessage.addListener((message) => {
    if (!message) return;

    if (message.type === "analyze") analyze(message.payload);
    if (message.type === "startPicking") startPicking();
    if (message.type === "captureRequested") captureAndAnalyze();
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
