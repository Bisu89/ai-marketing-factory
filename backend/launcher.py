"""Entry point for the packaged desktop build (PyInstaller targets this
file directly -- see AIContentLibrary.spec). Not used by the dev workflow,
which still runs `uvicorn app.main:app --reload` + a separate `npm run dev`
Vite server exactly as before.

Runs the existing FastAPI app in a background thread and opens it in a real
app window via pywebview (not a browser tab), so a customer never sees a
terminal, a URL bar, or has to run two separate dev servers. See
docs/features/14-desktop-packaging.md for the full packaging design.
"""

import socket
import threading
import time

import httpx
import uvicorn
import webview

from app.main import app as fastapi_app

READY_TIMEOUT_SEC = 10.0
POLL_INTERVAL_SEC = 0.1


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}/api/v1/health"
    deadline = time.monotonic() + READY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=0.5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(POLL_INTERVAL_SEC)
    raise RuntimeError(f"Backend server did not become ready within {READY_TIMEOUT_SEC}s")


def main() -> None:
    port = _find_free_port()
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    _wait_until_ready(port)

    webview.create_window(
        "AI Content Library",
        f"http://127.0.0.1:{port}/",
        width=1360,
        height=860,
        min_size=(1024, 700),
    )
    # Blocks until the window is closed by the user.
    webview.start()

    # Signal uvicorn's own graceful-shutdown flag so the FastAPI lifespan's
    # shutdown path runs (DownloadEngine/SceneCutterService/
    # VideoComposerService all stop their worker threads cleanly instead of
    # being killed mid-job when the process exits).
    server.should_exit = True
    server_thread.join(timeout=5)


if __name__ == "__main__":
    main()
