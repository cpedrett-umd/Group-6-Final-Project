"""Run AdInsight as a desktop app instead of a browser tab.

Same Flask app and the same front end -- this only changes the frame around it.
The server binds to loopback on an OS-assigned port and a native window renders
it, so there is no URL bar, no browser chrome, and nothing to explain about
localhost before a demo starts. It just opens.

    python app/desktop.py

Requires `pywebview` (in requirements.txt). On Windows it renders through
WebView2, which ships with Windows 11; on macOS it uses WebKit, and on Linux
GTK/Qt.
"""
from __future__ import annotations

import argparse
import threading

from werkzeug.serving import make_server

from server import app

WINDOW_TITLE = "AdInsight — Persuasion-Aware Ad Explainer"

# A compact utility window in the shape of a browser-extension popup, not a
# full-page app -- the tool is something you glance at beside an ad, so it
# should not take over the screen. The layout collapses to a single column
# below 940px and tightens further below 520px (see styles.css), so the same
# UI reflows into this width without redesign.
#
# Slightly taller and wider than MetaMask's 360x600, because the type is sized
# for readers 60+ and the tactic list needs the vertical room.
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 760
MIN_SIZE = (360, 520)


class ServerThread(threading.Thread):
    """Flask on a background thread, bound to a port the OS picks for us.

    Port 0 lets the OS assign a free one, so the app never collides with the
    `python app/server.py` instance a teammate may already have running.
    """

    def __init__(self, host="127.0.0.1", port=0):
        super().__init__(daemon=True)
        self._server = make_server(host, port, app, threaded=True)
        self.port = self._server.server_port
        self.host = host

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def run(self):
        self._server.serve_forever()

    def shutdown(self):
        self._server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Run AdInsight as a desktop app.")
    parser.add_argument(
        "--no-warm",
        action="store_true",
        help="skip loading the model at startup (first analysis will be slower)",
    )
    arguments = parser.parse_args()

    import predict
    import webview

    if not predict.is_ready():
        print(
            "\n  Warning: no trained model found.\n"
            "  Build it first:  cd modeling && python train_best.py\n"
        )
    elif not arguments.no_warm:
        # Load before the window opens: a desktop app that stalls for 10s on
        # the first click reads as broken.
        print("Loading model...")
        predict.warm_up()

    server = ServerThread()
    server.start()

    print(f"AdInsight running at {server.url}")

    # surface=app tells the page it isn't in a browser tab, so the header
    # describes itself accurately.
    webview.create_window(
        WINDOW_TITLE,
        f"{server.url}/?surface=app",
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=MIN_SIZE,
    )

    # Blocks until the window closes; the daemon server thread dies with it.
    webview.start()


if __name__ == "__main__":
    main()
