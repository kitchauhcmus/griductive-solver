"""Serve one local match. Only explicitly listed files and actions are routable."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..roster import BY_SLUG
from .game import Match, ROOT
from .portraits import MIME, portrait_index

STATIC = Path(__file__).parent / "static"
FILES = {
    "/": (STATIC / "index.html", "text/html; charset=utf-8"),
    "/static/app.css": (STATIC / "app.css", "text/css; charset=utf-8"),
    "/static/js/card_art.js": (STATIC / "js/card_art.js", "text/javascript; charset=utf-8"),
    "/static/js/app.js": (STATIC / "js/app.js", "text/javascript; charset=utf-8"),
    "/assets/stadium": (ROOT / "assets/backgrounds/stadium.jpg", "image/jpeg"),
    "/credits": (ROOT / "assets/CREDITS.md", "text/plain; charset=utf-8"),
}
ACTIONS = {"load", "restart", "verdict", "hint", "step", "solve", "uniqueness", "clue-highlight"}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body=b"", media="application/octet-stream"):
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def json(self, data, status=200):
        self.reply(status, json.dumps(data).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        match = self.server.match
        if path in ("/api/state", "/api/puzzles"):
            with match.lock:
                result = match.snapshot() if path == "/api/state" else match.catalog()
            self.json(result)
        elif path.startswith("/assets/players/"):
            slug = path.removeprefix("/assets/players/").casefold()
            if slug not in BY_SLUG:
                return self.json({"error": "Unknown player"}, 404)
            file = portrait_index(match.portraits).get(slug)
            if file:
                try:
                    return self.reply(200, file.read_bytes(), MIME[file.suffix.lower()])
                except FileNotFoundError:
                    pass
            self.reply(204)
        elif path in FILES:
            file, media = FILES[path]
            self.reply(200, file.read_bytes(), media)
        elif path == "/favicon.ico":
            self.reply(204)
        else:
            self.json({"error": "Unknown route"}, 404)

    do_HEAD = do_GET

    def do_POST(self):
        action = urlsplit(self.path).path
        if action not in {f"/api/{a}" for a in ACTIONS}:
            return self.json({"error": "Unknown route"}, 404)
        if self.headers.get_content_type() != "application/json":
            return self.json({"error": "Expected JSON"}, 415)
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            return self.json({"error": "Use the local game tab"}, 403)
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 <= size <= 16384:
                return self.json({"error": "Invalid request size"}, 413)
            data = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            with self.server.match.lock:
                result = self.server.match.action(action.rsplit("/", 1)[1], data)
            self.json(result)
        except (KeyError, ValueError, TypeError) as exc:
            self.json({"error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        if args and str(args[1])[:1] in {"4", "5"}:
            super().log_message(fmt, *args)


def make_server(initial, *, portraits=None):
    match = Match(Path(initial), **({"portraits": portraits} if portraits is not None else {}))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.match = match
    return server
