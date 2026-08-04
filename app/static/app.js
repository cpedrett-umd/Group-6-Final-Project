/* AdInsight demo front end.
 *
 * Three ways in — the wireframe's demo ad, pasted text, an uploaded image —
 * all POST to /api/analyze and render into the same panel. */

(function () {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  // The demo ad's copy, kept identical to the wireframe's mock ad so the
  // classifier sees exactly what the user reads on the left.
  const DEMO_AD =
    "FINAL HOURS: Doctor-recommended MemoryMax Pro reverses memory loss in " +
    "14 days. Only 7 bottles left — 70% off before the supplement ban.";

  let selectedImage = null;

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

  async function analyze(mode) {
    let request;

    if (mode === "image") {
      if (!selectedImage) {
        showError("Choose an image first.");
        return;
      }

      const form = new FormData();
      form.append("image", selectedImage);
      request = { method: "POST", body: form };

      $("#busy-copy").textContent = "Reading the words off your image…";
    } else {
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

      $("#busy-copy").textContent = "Reading the ad…";
    }

    showState("busy");

    try {
      const response = await fetch("/api/analyze", request);
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

  /* ── Rendering ──────────────────────────────────────────────── */

  const percent = (value) => Math.round(value * 100) + "%";

  function render(data) {
    // Summary callout
    const callout = $("#summary-callout");
    callout.classList.toggle("is-calm", data.summary.tone === "calm");
    $("#summary-headline").textContent = data.summary.headline;
    $("#summary-msg").textContent = data.summary.message;

    // What OCR read back — only shown for image input, so a bad scan is
    // visible to the user instead of silently driving the verdict.
    const readBack = $("#read-back");

    if (data.source.mode === "image" && data.source.ocr) {
      const ocr = data.source.ocr;
      $("#read-back-text").textContent = "“" + data.text + "”";

      const bits = [
        ocr.line_count + (ocr.line_count === 1 ? " line" : " lines") + " read",
        percent(ocr.confidence) + " confident",
      ];

      if (ocr.repaired) bits.push("spacing repaired");

      $("#read-back-meta").textContent =
        bits.join(" · ") + ". If this looks wrong, paste the text instead.";
      readBack.hidden = false;
    } else {
      readBack.hidden = true;
    }

    // Tactic rows. `uncertain` rows are the model's forced pick on an ad with
    // no trigger phrases — the label set has no "neutral" option, so a weak
    // score is not a finding. It still shows in the distribution below.
    const list = $("#tactic-list");
    list.replaceChildren();

    const findings = data.tactics.filter((tactic) => !tactic.uncertain);

    if (findings.length === 0) {
      const empty = document.createElement("li");
      empty.className = "tactic-empty";
      empty.textContent =
        "No pressure tactics stood out in these words.";
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

    // Review layer (stub)
    $("#review-notice").textContent = data.reviews.notice || "";
    $("#review-badge").hidden = !data.reviews.mock;

    const reviewList = $("#review-list");
    reviewList.replaceChildren();

    data.reviews.items.forEach((review) => {
      const item = document.createElement("li");
      item.className = "review";

      const source = document.createElement("span");
      source.className = "review-src";
      source.textContent = review.rating
        ? review.source + " · " + review.rating
        : review.source;

      const quote = document.createElement("p");
      quote.className = "review-quote";
      quote.textContent = "“" + review.quote + "”";

      item.append(source, quote);
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
          "No OCR backend — image uploads won't work. Run <code>pip install rapidocr-onnxruntime</code>."
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
