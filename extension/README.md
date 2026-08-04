# extension/ — AdInsight browser extension

The second input surface from the wireframe: instead of pasting an ad into the
app, the user analyzes it in place, on the page where they met it. The overlay
panel is the same one the app shows.

Chrome / Edge, Manifest V3. Unpacked — it is a course demo, not a store listing.

## Load it

1. Start the backend (the extension is a front end for the same API):

   ```bash
   python app/server.py
   ```

2. Open `chrome://extensions`, turn on **Developer mode**, click **Load
   unpacked**, and choose this `extension/` folder.

3. Open the demo page the server hosts:

   <http://127.0.0.1:5000/demo-page>

That page is an ordinary-looking news article with a sponsored block in it —
a fixed target so a demo never depends on finding a live ad.

## Three ways to analyze an ad

| Action | What happens |
|---|---|
| **Hover a sponsored block** | An *Analyze this ad* button floats over it — the wireframe's interaction |
| **Toolbar → Pick an ad on this page** | Hover *anything*; it outlines under the cursor, click to analyze |
| **Select any text** | The same button appears over the selection |
| **Right-click an ad image** | Context menu → *Analyze this ad image* → OCR, then the model |
| **Toolbar icon** | Popup with a paste box, server status, and the API address |

Hovering works automatically only on blocks whose markup says "ad". **Pick
mode** is the guaranteed path on sites that mark things up differently — it
outlines whatever is under the cursor and analyzes it on click, and it
suppresses the click so picking an ad never follows the ad's link. `Esc`
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

57 tests over `content.js` and `background.js`, using Node's built-in runner
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

- **Ads inside cross-origin iframes can't be read.** Most programmatic ad slots
  are third-party iframes, and a content script cannot reach into them. Those
  need the right-click-the-image path, or a screenshot through the app.
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
