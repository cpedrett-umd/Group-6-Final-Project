# extension/ — AdInsight browser extension

The second input surface from the wireframe: instead of pasting an ad into the
app, the user analyzes it in place, on the page where they met it. The overlay
panel is the same one the app shows.

Chrome / Edge, Manifest V3. Unpacked — it is a course demo, not a store listing.

## Install it

Chrome or Edge. Loaded unpacked — this is a course project, not a store listing.

**1. Start the backend.** The extension is only a front end; the model runs in
the server. It must stay running the whole time you use the extension.

```bash
python app/server.py --warm
```

Run that from the repository root and wait for
`Running on http://127.0.0.1:5000`. Leave the terminal open.

**2. Open the extensions page.** Type **`chrome://extensions`** into the address
bar (`edge://extensions` on Edge). It's also under ⋮ → Extensions → Manage
Extensions.

**3. Turn on Developer mode** — the toggle at the top right. Without it, the
*Load unpacked* button isn't shown.

**4. Click Load unpacked** and select this **`extension/`** folder — the folder
itself, not a file inside it. It's the one containing `manifest.json`. An
*AdInsight* card should appear, version 0.1.0, with no errors.

**5. Pin it.** Click the puzzle-piece icon in the toolbar and pin **AdInsight**.
Easy to skip, but the popup holds *Pick an ad on this page*, the server status,
and the API address setting.

**6. Open the demo page:**

<http://127.0.0.1:5000/demo-page>

That page is an ordinary-looking news article with a sponsored block in it —
a fixed target so a demo never depends on finding a live ad.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Popup says "Server not running" | The backend stopped. Restart `python app/server.py --warm`. |
| Nothing happens when hovering an ad | That block isn't marked up as an ad. Use **Pick an ad on this page**. |
| Panel never appears at all | Reload the page — content scripts only inject at page load. |
| Changes to these files do nothing | Press the reload icon on the AdInsight card, **then** refresh the page. |
| "Service worker (inactive)" | Normal. MV3 workers sleep and wake on demand. |
| Errors button on the card | Click it for the service-worker console; most issues show there. |
| Server is on another port | Set it in the popup under **Server address**. |
| Ad is in an iframe | Cross-origin iframes are unreadable by any extension. Right-click the image, or use pick mode on nearby text. |

## Three ways to analyze an ad

| Action | What happens |
|---|---|
| **Hover any ad** | An *Analyze this ad* button appears along the ad's bottom edge — text ads are read directly; iframe and video ads are **screenshotted** and OCR'd |
| **Toolbar → Pick an ad on this page** | Hover *anything*; it outlines under the cursor, click to analyze |
| **Select any text** | The same button appears over the selection |
| **Right-click an ad** | *Analyze this ad by screenshot* — works on video and iframe ads |
| **Right-click an ad image** | *Analyze this ad image* → downloads the image, OCR, then the model |
| **Toolbar icon** | Popup with a paste box, server status, and the API address |

**How hover decides.** A block whose markup says "ad" and which has readable
text is analyzed as text. An ad **iframe** (DoubleClick, safeframe, Amazon,
Criteo, Taboola…), a **video**, or an ad container whose words live inside a
cross-origin iframe can't be read at all — for those, clicking the button
**screenshots the tab and crops to the ad**, then OCRs the crop. A playing
video contributes whatever frame is showing. The button sits *inside* the ad's
bottom edge, so moving to click it never crosses other page elements that
would steal the hover.

**Pick mode** is the fallback for sponsored content whose markup doesn't say
"ad" — it outlines whatever is under the cursor and analyzes it on click,
suppressing the click so picking an ad never follows the ad's link. `Esc`
cancels.

Results render in a panel that slides in from the right. Press `Esc` or the
`×` to dismiss.

## How the pieces fit

```
background.js   service worker — owns every network call and the context menus
content.js      injects the overlay, detects ads, renders results
panel.css       overlay styles, loaded into the shadow root
popup.html/js   toolbar popup: paste box, status, settings
```

**Why the service worker makes the requests.** A content script's `fetch` obeys
the host page's CORS rules, so calling `127.0.0.1:5000` from inside a news site
would be blocked. The worker's `host_permissions` are not, so `content.js` sends
it a message and it does the network call. Downloading an ad image for OCR works
the same way — hence `<all_urls>` in the manifest, which is what lets the
extension fetch an image hosted on any ad CDN.

**Why a shadow root.** The panel is mounted in a closed-off DOM subtree with its
own stylesheet. Without it, a news site's global CSS reaches into the panel and
makes it unreadable, and the panel's own CSS leaks back out into the article.

**Ad detection is a heuristic.** `AD_SELECTOR` in `content.js` matches the
markup real ad slots tend to use (`sponsored`, `ad-slot`, `ins.adsbygoogle`,
`[data-ad]`), then requires the block to be a plausible size and to hold at
least 40 characters. It will miss ads on sites that name things differently —
that is why text selection exists as the always-available fallback. The
selectors are deliberately narrow: a button on ordinary article text is worse
than a missed ad.

## Tests

56 tests over `content.js` and `background.js`, using Node's built-in runner
plus jsdom. No browser and no running server needed — the `chrome` API and the
network are both faked.

```bash
cd extension/tests && npm install && npm test
```

They cover injection and shadow isolation, ad detection (including the blocks
that must *not* be offered), pill placement and viewport clamping, text
selection, pick mode, result rendering, the uncertain-row filter, error states,
and that ad copy is inserted as text and never as markup.

`node_modules/` is gitignored and confined to `tests/` — the extension itself
ships no dependencies.

## Known limits

- **Cross-origin iframe ads can't be read as text — but they can be
  screenshotted.** A content script cannot reach into a third-party iframe, so
  those ads go through the capture path: the service worker photographs the
  visible tab (`chrome.tabs.captureVisibleTab`), crops to the ad's on-screen
  box, and OCRs the crop. This is also why the whole ad block captures better
  than right-clicking its thumbnail image alone — live-tested on Taboola
  creatives, the thumbnail often carries no words while the block's headline
  carries them all.
- Reload from `chrome://extensions` after editing any file here, then reload
  the page so the content script re-injects.

## Notes

- The panel's markup and rendering mirror [`app/static/app.js`](../app/static/app.js).
  Sharing one module would need a build step, which is not worth adding here —
  but **copy changes have to be made in both places.**
- The API address defaults to `http://127.0.0.1:5000` and is editable in the
  popup, so the extension can point at a teammate's machine on the same network.
- Firefox needs `browser_specific_settings` in the manifest and treats MV3
  service workers differently; this build targets Chrome and Edge.
