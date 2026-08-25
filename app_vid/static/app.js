/* AdInsight demo front end.
 *
 * Four ways in — the wireframe's demo ad, pasted text, an uploaded image, and
 * a video or audio ad supplied as a link, a recording, or captured live — all
 * rendering into the same panel. */

(function () {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  // The demo ad's copy, kept identical to the wireframe's mock ad so the
  // classifier sees exactly what the user reads on the left.
  const DEMO_AD =
    "FINAL HOURS: Doctor-recommended MemoryMax Pro reverses memory loss in " +
    "14 days. Only 7 bottles left — 70% off before the supplement ban.";

  const MAX_MEDIA_BYTES = 64 * 1024 * 1024;

  let selectedImage = null;
  let selectedMedia = null;      // file chosen or recorded
  let recorder = null;           // MediaRecorder while capturing
  let recordedChunks = [];
  let recordStartedAt = 0;
  let recordTimer = null;

  /* ── Panel state ────────────────────────────────────────────── */

  function showState(name) {
    $$(".panel-state").forEach((node) =>
      node.classList.toggle("is-active", node.dataset.state === name)
    );
  }

  function showError(message) {
    $("#error-msg").textContent = message;
    showState("error");
  }

  /* ── Mode tabs ──────────────────────────────────────────────── */

  $$(".mode").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".mode").forEach((other) => {
        const active = other === button;
        other.classList.toggle("is-active", active);
        other.setAttribute("aria-selected", String(active));
      });

      $$(".source-view").forEach((view) =>
        view.classList.toggle("is-active", view.dataset.view === button.dataset.mode)
      );

      showState("idle");
    });
  });

  /* ── Image picking ──────────────────────────────────────────── */

  const dropZone = $("#drop-zone");
  const fileInput = $("#ad-image");
  const imageButton = $('[data-analyze="image"]');

  function acceptImage(file) {
    if (!file || !file.type.startsWith("image/")) {
      $("#ocr-note").textContent = "That file isn't an image.";
      return;
    }

    selectedImage = file;

    const preview = $("#preview");
    const image = $("#preview-img");

    if (image.src) URL.revokeObjectURL(image.src);
    image.src = URL.createObjectURL(file);

    $("#preview-name").textContent = file.name;
    preview.hidden = false;

    $("#ocr-note").textContent = "";
    imageButton.disabled = false;
  }

  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", () => acceptImage(fileInput.files[0]));

  ["dragenter", "dragover"].forEach((type) =>
    dropZone.addEventListener(type, (event) => {
      event.preventDefault();
      dropZone.classList.add("is-over");
    })
  );

  ["dragleave", "drop"].forEach((type) =>
    dropZone.addEventListener(type, (event) => {
      event.preventDefault();
      dropZone.classList.remove("is-over");
    })
  );

  dropZone.addEventListener("drop", (event) => {
    acceptImage(event.dataTransfer.files[0]);
  });

  /* ── Video / audio picking ──────────────────────────────────── */

  const mediaDrop = $("#media-drop");
  const mediaInput = $("#ad-media");
  const mediaButton = $('[data-analyze="media"]');

  function acceptMedia(file, label) {
    if (!file) return;

    const isMedia =
      file.type.startsWith("video/") ||
      file.type.startsWith("audio/") ||
      /\.(mp4|mov|webm|mkv|avi|m4v|mp3|wav|m4a|ogg|opus|aac)$/i.test(file.name || "");

    if (!isMedia) {
      $("#media-note").textContent = "That isn't a video or audio file.";
      return;
    }

    if (file.size > MAX_MEDIA_BYTES) {
      $("#media-note").textContent =
        "That file is over 64 MB. A shorter clip, or just the part with the ad, will work.";
      return;
    }

    selectedMedia = file;

    const megabytes = (file.size / 1e6).toFixed(1);
    $("#media-name").textContent = (label || file.name) + " · " + megabytes + " MB";
    $("#media-preview").hidden = false;

    // A link and a file are alternatives, so choosing one clears the other.
    $("#ad-url").value = "";
    $("#media-note").textContent = "";
    mediaButton.disabled = false;
  }

  if (mediaDrop) {
    mediaDrop.addEventListener("click", () => mediaInput.click());

    mediaDrop.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        mediaInput.click();
      }
    });

    mediaInput.addEventListener("change", () => acceptMedia(mediaInput.files[0]));

    ["dragenter", "dragover"].forEach((type) =>
      mediaDrop.addEventListener(type, (event) => {
        event.preventDefault();
        mediaDrop.classList.add("is-over");
      })
    );

    ["dragleave", "drop"].forEach((type) =>
      mediaDrop.addEventListener(type, (event) => {
        event.preventDefault();
        mediaDrop.classList.remove("is-over");
      })
    );

    mediaDrop.addEventListener("drop", (event) => {
      acceptMedia(event.dataTransfer.files[0]);
    });

    // Typing a link is the other way in, so it clears a chosen file.
    $("#ad-url").addEventListener("input", (event) => {
      if (event.target.value.trim()) {
        selectedMedia = null;
        $("#media-preview").hidden = true;
        mediaButton.disabled = true;
      }
    });
  }

  /* ── Recording ──────────────────────────────────────────────── */

  // The microphone hears whatever the speakers play, so the user plays the ad
  // out loud and we capture that. getUserMedia needs a secure context, which
  // localhost satisfies; where it is unavailable the option stays hidden
  // rather than appearing and failing.

  const canRecord =
    typeof navigator !== "undefined" &&
    navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function" &&
    typeof window.MediaRecorder === "function";

  if (canRecord && $("#record-option")) $("#record-option").hidden = false;

  function formatDuration(ms) {
    const total = Math.floor(ms / 1000);
    return Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
  }

  async function startRecording() {
    let stream;

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      $("#media-note").textContent =
        "Couldn't reach the microphone. Check the browser's permission, or upload a recording instead.";
      return;
    }

    recordedChunks = [];
    recorder = new MediaRecorder(stream);

    recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size) recordedChunks.push(event.data);
    });

    recorder.addEventListener("stop", () => {
      stream.getTracks().forEach((track) => track.stop());

      const blob = new Blob(recordedChunks, {
        type: recorder.mimeType || "audio/webm",
      });

      const seconds = Math.round((Date.now() - recordStartedAt) / 1000);

      if (blob.size < 2000) {
        $("#media-note").textContent =
          "That recording was too short to read. Try again while the ad plays.";
        return;
      }

      acceptMedia(
        new File([blob], "recording.webm", { type: blob.type }),
        "Recording · " + seconds + "s"
      );
    });

    recorder.start();
    recordStartedAt = Date.now();

    $("#record-toggle").classList.add("is-recording");
    $("#record-label").textContent = "Stop recording";
    $("#record-time").hidden = false;

    recordTimer = setInterval(() => {
      $("#record-time").textContent = formatDuration(Date.now() - recordStartedAt);
    }, 250);
  }

  function stopRecording() {
    if (recorder && recorder.state !== "inactive") recorder.stop();

    recorder = null;
    clearInterval(recordTimer);

    $("#record-toggle").classList.remove("is-recording");
    $("#record-label").textContent = "Start recording";
    $("#record-time").hidden = true;
  }

  if (canRecord && $("#record-toggle")) {
    $("#record-toggle").addEventListener("click", () => {
      if (recorder && recorder.state === "recording") {
        stopRecording();
      } else {
        startRecording();
      }
    });
  }

  /* ── Example + reset ────────────────────────────────────────── */

  $("[data-example]").addEventListener("click", (event) => {
    $("#ad-text").value = event.currentTarget.dataset.example;
    $("#ad-text").focus();
  });

  $("#again").addEventListener("click", () => showState("idle"));
  $("#close-panel").addEventListener("click", () => showState("idle"));

  /* ── Analyze ────────────────────────────────────────────────── */

  $$("[data-analyze]").forEach((button) => {
    button.addEventListener("click", () => analyze(button.dataset.analyze));
  });

  async function post(endpoint, request, busyCopy) {
    $("#busy-copy").textContent = busyCopy;
    showState("busy");

    try {
      const response = await fetch(endpoint, request);
      const data = await response.json();

      if (!response.ok) {
        showError(data.error || "The server couldn't analyze that ad.");
        return;
      }

      render(data);
    } catch (error) {
      showError("Couldn't reach the server. Is it still running?");
    }
  }

  async function analyze(mode) {
    // Video and audio go to their own endpoint: reading them means fetching,
    // sampling frames and transcribing, which takes long enough that the busy
    // copy should say what is happening rather than leaving a bare spinner.

    if (mode === "url" || (mode === "media" && !selectedMedia)) {
      const url = $("#ad-url").value.trim();

      if (!url) {
        showError("Paste a link, or upload a recording.");
        return;
      }

      await post(
        "/api/analyze-media",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: url }),
        },
        "Fetching the post and reading it — this takes a few seconds…"
      );

      return;
    }

    if (mode === "media") {
      const form = new FormData();
      form.append("media", selectedMedia);

      await post(
        "/api/analyze-media",
        { method: "POST", body: form },
        "Listening to the ad and reading what's on screen…"
      );

      return;
    }

    let request;

    if (mode === "image") {
      if (!selectedImage) {
        showError("Choose an image first.");
        return;
      }

      const form = new FormData();
      form.append("image", selectedImage);

      await post("/api/analyze", { method: "POST", body: form },
                 "Reading the words off your image…");
      return;
    }

    const text = mode === "demo" ? DEMO_AD : $("#ad-text").value.trim();

    if (!text) {
      showError("Paste some ad text first.");
      return;
    }

    request = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    };

    await post("/api/analyze", request, "Reading the ad…");
  }

  /* ── Rendering ──────────────────────────────────────────────── */

  const percent = (value) => Math.round(value * 100) + "%";

  function render(data) {
    // Summary callout
    const callout = $("#summary-callout");
    callout.classList.toggle("is-calm", data.summary.tone === "calm");
    $("#summary-headline").textContent = data.summary.headline;
    $("#summary-msg").textContent = data.summary.message;

    // What was read back. Shown for image and media input, so a bad scan or a
    // poor transcript is visible to the user instead of silently driving the
    // verdict.
    const readBack = $("#read-back");
    const readBackTitle = readBack ? readBack.querySelector(".section-title") : null;

    if (data.source.mode === "media") {
      $("#read-back-text").textContent = "“" + data.text + "”";

      const bits = [];
      const source = data.source;

      if (source.duration) bits.push(Math.round(source.duration) + "s ad");
      if (source.spoken_words) bits.push(source.spoken_words + " words spoken");
      if (source.frame_words) bits.push(source.frame_words + " words on screen");
      if (source.platform) bits.push("from " + source.platform);

      $("#read-back-meta").textContent =
        bits.join(" · ") + ". If this looks wrong, paste the ad's text instead.";

      if (readBackTitle) readBackTitle.textContent = "What we heard and read";
      readBack.hidden = false;
    } else if (data.source.mode === "image" && data.source.ocr) {
      const ocr = data.source.ocr;
      $("#read-back-text").textContent = "“" + data.text + "”";

      const bits = [
        ocr.line_count + (ocr.line_count === 1 ? " line" : " lines") + " read",
      ];

      // The VLM backend reports no per-line score. Saying nothing is better
      // than printing 0%, which would read as a bad scan.
      if (ocr.confidence !== null && ocr.confidence !== undefined) {
        bits.push(percent(ocr.confidence) + " confident");
      }

      if (ocr.repaired) bits.push("spacing repaired");

      $("#read-back-meta").textContent =
        bits.join(" · ") + ". If this looks wrong, paste the text instead.";

      if (readBackTitle) readBackTitle.textContent = "What we read from your image";
      readBack.hidden = false;
    } else {
      readBack.hidden = true;
    }

    // Tactic rows. `uncertain` rows are the model's forced pick on an ad with
    // no trigger phrases — a weak score is not a finding. It still shows in the
    // distribution below.
    const list = $("#tactic-list");
    list.replaceChildren();

    const findings = data.tactics.filter((tactic) => !tactic.uncertain);

    if (findings.length === 0) {
      const empty = document.createElement("li");
      empty.className = "tactic-empty";
      empty.textContent = "No pressure tactics stood out in these words.";
      list.append(empty);
    }

    findings.forEach((tactic) => {
      const item = document.createElement("li");
      item.className = "tactic";

      const dot = document.createElement("span");
      dot.className = "tactic-dot";
      dot.setAttribute("aria-hidden", "true");

      const body = document.createElement("div");

      const name = document.createElement("div");
      name.className = "tactic-name";
      name.append(tactic.display);

      // Badge which signal produced this row — the model's prediction, a
      // literal trigger phrase, or both.
      tactic.sources.forEach((source) => {
        const badge = document.createElement("span");
        badge.className = "src src-" + source;
        badge.textContent = source === "model" ? "model pick" : "phrase found";
        name.append(badge);
      });

      if (tactic.sources.includes("model")) {
        const conf = document.createElement("span");
        conf.className = "conf";
        conf.textContent = percent(tactic.confidence) + " confident";
        name.append(conf);
      }

      const why = document.createElement("p");
      why.className = "tactic-why";
      why.textContent = tactic.explanation;

      body.append(name, why);
      item.append(dot, body);
      list.append(item);
    });

    // ── Timeline ──────────────────────────────────────────────
    //
    // A single label over a whole video hides the shape of the ad: one
    // commonly spends most of its length building credibility and pitches in
    // the final seconds. This says where each tactic sits rather than
    // flattening the ad to one verdict.

    const timelineSection = $("#timeline-section");
    const timeline = data.timeline;

    if (timelineSection && timeline && timeline.windows && timeline.windows.length > 1) {
      const steps = $("#timeline-list");
      steps.replaceChildren();

      $("#timeline-note").textContent =
        "This ad was read in " + timeline.windows.length + " parts, so a tactic " +
        "used in only one part shows as its own step rather than as the whole " +
        "ad's character.";

      timeline.windows.forEach((window) => {
        const item = document.createElement("li");
        item.className = "timeline-step" + (window.uncertain ? " is-uncertain" : "");

        const head = document.createElement("div");
        head.className = "timeline-head";

        const label = document.createElement("span");
        label.className = "timeline-label";
        label.textContent = window.display || window.label;
        head.append(label);

        const note = document.createElement("span");
        note.className = "conf";

        if (window.uncertain) {
          note.textContent = "not sure";
        } else if (window.confidence !== null && window.confidence !== undefined) {
          note.textContent = percent(window.confidence) + " confident";
        }

        if (note.textContent) head.append(note);

        const quote = document.createElement("p");
        quote.className = "timeline-text";
        const text = window.text || "";
        quote.textContent =
          "“" + (text.length > 190 ? text.slice(0, 190) + "…" : text) + "”";

        item.append(head, quote);

        if (window.phrases && window.phrases.length) {
          const phrases = document.createElement("p");
          phrases.className = "timeline-phrases";
          phrases.textContent = "Words that stood out: " + window.phrases.join(", ");
          item.append(phrases);
        }

        steps.append(item);
      });

      timelineSection.hidden = false;
    } else if (timelineSection) {
      timelineSection.hidden = true;
    }

    // ── Review layer ──────────────────────────────────────────
    //
    // Three parts, in the order a reader needs them: what the technical words
    // mean, what people report, and where to read it. The middle section is
    // built only from retrieved passages — nothing here is the model's own
    // opinion of the product.

    const reviews = data.reviews || {};

    $("#review-notice").textContent = reviews.notice || "";
    $("#review-badge").hidden = !reviews.mock;

    const reviewList = $("#review-list");
    reviewList.replaceChildren();

    // 1. Glossary. An ad that leans on enzyme names is persuading with
    // vocabulary, so plain definitions are the direct counter.
    if (reviews.glossary && reviews.glossary.length) {
      const item = document.createElement("li");
      item.className = "review review-glossary";

      const heading = document.createElement("span");
      heading.className = "review-src";
      heading.textContent = "What these words mean";
      item.append(heading);

      const terms = document.createElement("dl");
      terms.className = "glossary";

      reviews.glossary.forEach((entry) => {
        const term = document.createElement("dt");
        term.textContent = entry.term;

        const meaning = document.createElement("dd");
        meaning.textContent = entry.meaning;

        terms.append(term, meaning);
      });

      item.append(terms);
      reviewList.append(item);
    }

    // 2. What people report. Present only when retrieval found enough
    // independent sources to summarise.
    if (reviews.summary) {
      const item = document.createElement("li");
      item.className = "review review-summary";

      const heading = document.createElement("span");
      heading.className = "review-src";
      heading.textContent = "What people are saying";

      const text = document.createElement("p");
      text.className = "review-quote";
      text.textContent = reviews.summary;

      item.append(heading, text);
      reviewList.append(item);
    }

    // 3. Nothing to look up. Reporting that plainly is more use than a guess:
    // for an ad promising a result, the missing name is itself the finding.
    if (reviews.no_entity) {
      const item = document.createElement("li");
      item.className = "review review-empty";

      const text = document.createElement("p");
      text.className = "review-quote";
      text.textContent =
        "There is no company or product name in this ad to look up. " +
        "For an ad promising a result, that is worth noticing on its own — " +
        "a seller willing to be checked will normally say who they are.";

      item.append(text);
      reviewList.append(item);
    }

    // 4. The sources themselves.
    (reviews.items || []).forEach((review) => {
      const item = document.createElement("li");
      item.className = "review";

      const source = document.createElement("span");
      source.className = "review-src";
      source.textContent = review.rating
        ? review.source + " · " + review.rating
        : review.source;

      // Affiliate pages are kept rather than dropped — they are sometimes the
      // most candid source available — but the reader is told.
      if (review.flags && review.flags.length) {
        const flag = document.createElement("span");
        flag.className = "review-flag";
        flag.textContent = review.flags.join(", ");
        source.append(" ", flag);
      }

      const quote = document.createElement("p");
      quote.className = "review-quote";
      quote.textContent = "“" + review.quote + "”";

      item.append(source, quote);

      if (review.url) {
        const link = document.createElement("a");
        link.className = "review-link";
        link.href = review.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Read the discussion →";
        item.append(link);
      }

      reviewList.append(item);
    });

    // Full explanation
    $("#detail-label").textContent = data.prediction.label;
    $("#detail-conf").textContent = percent(data.prediction.confidence);

    const body = $("#dist-table tbody");
    body.replaceChildren();

    data.prediction.distribution.forEach((entry, index) => {
      const row = document.createElement("tr");
      if (index === 0) row.className = "is-top";

      const label = document.createElement("td");
      label.textContent = entry.label;

      const barCell = document.createElement("td");
      const bar = document.createElement("div");
      bar.className = "bar";
      const fill = document.createElement("span");
      fill.style.width = Math.max(entry.confidence * 100, 1) + "%";
      bar.append(fill);
      barCell.append(bar);

      const value = document.createElement("td");
      value.textContent = percent(entry.confidence);

      row.append(label, barCell, value);
      body.append(row);
    });

    showState("result");
  }

  /* ── Surface label ──────────────────────────────────────────── */

  // desktop.py opens the window with ?surface=app. Same UI either way — only
  // the header's description of itself changes, so it stays accurate.
  if (new URLSearchParams(location.search).get("surface") === "app") {
    document.querySelector(".stage-note").textContent =
      "App surface · same panel in the browser extension";
  }

  /* ── Startup health check ───────────────────────────────────── */

  (async function checkHealth() {
    try {
      const response = await fetch("/api/health");
      const health = await response.json();

      const problems = [];

      if (!health.model_ready) {
        problems.push(
          "The model files are missing — they're stored in Git LFS, so run " +
            "<code>git lfs install &amp;&amp; git lfs pull</code>."
        );
      }

      if (!health.ocr_backend) {
        problems.push(
          "No text extraction backend — image uploads won't work. Run " +
            "<code>pip install rapidocr-onnxruntime</code>."
        );
      }

      // The tab is disabled up front rather than failing on the first click.
      if (health.media_ready === false) {
        const tab = document.querySelector('[data-mode="media"]');

        if (tab) {
          tab.disabled = true;
          tab.title =
            "Needs faster-whisper — pip install faster-whisper yt-dlp opencv-python";
        }

        problems.push(
          "Video and audio input is off — run " +
            "<code>pip install faster-whisper yt-dlp opencv-python</code>."
        );
      }

      if (problems.length) {
        const strip = $("#status-strip");
        strip.innerHTML = problems.join("<br>");
        strip.hidden = false;
      }
    } catch (error) {
      /* Health is advisory; the analyze call reports real failures. */
    }
  })();
})();