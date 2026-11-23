"""Open the zero-build football board in the default browser."""
from pathlib import Path
from threading import Timer
import webbrowser

from .web.server import make_server


def run_gui(initial_puzzle: Path) -> int:
    with make_server(initial_puzzle) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Griductive Football Edition  {url}\nPress Ctrl+C to stop.", flush=True)
        Timer(0.2, webbrowser.open, args=(url,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0
