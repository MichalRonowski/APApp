from __future__ import annotations
import threading
import time
import socket
import webbrowser

try:
    import webview  # pywebview
except Exception:
    webview = None

from src.app import app


def _find_free_port(preferred: int = 5000) -> int:
    # Try preferred first
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    # Ask OS for a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_server(port: int) -> None:
    # Use Flask's built-in server in a thread for simplicity.
    # For production stability you can switch to waitress.
    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=port)
    except Exception:
        # Fallback to Flask dev server if waitress unavailable
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main() -> None:
    port = _find_free_port(5000)
    server_th = threading.Thread(target=_run_server, args=(port,), daemon=True)
    server_th.start()

    url = f"http://127.0.0.1:{port}"

    # Optionally wait a moment for server to start
    time.sleep(0.5)

    if webview is not None:
        try:
            webview.create_window("Generator raportów PDF", url)
            webview.start()
            return
        except Exception:
            pass

    # Fallback: open in default browser
    webbrowser.open(url)


if __name__ == "__main__":
    main()
