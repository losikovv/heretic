import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from roster_builder_core import HereticBuilder
from roster_builder_page import PAGE


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "heretic_sheets.sqlite"


def find_port(host, start):
    for port in range(start, start + 50):
        try:
            return ThreadingHTTPServer((host, port), Handler), port
        except OSError:
            continue
    raise OSError(f"No free port found from {start} to {start + 49}")


class Handler(BaseHTTPRequestHandler):
    heretic_builder = None

    def log_message(self, fmt, *args):
        return

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def fail(self, error):
        self.send_json({"error": str(error)}, status=400)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/bootstrap":
                self.send_json(self.heretic_builder.bootstrap())
            elif parsed.path == "/api/detachments":
                self.send_json(self.heretic_builder.detachments(params.get("factionId", [""])[0]))
            elif parsed.path == "/api/datasheets":
                self.send_json(self.heretic_builder.datasheets(
                    params.get("factionId", [""])[0],
                    params.get("detachmentId", [""])[0],
                    params.get("q", [""])[0],
                ))
            elif parsed.path == "/api/roster":
                self.send_json(self.heretic_builder.roster(params.get("id", [""])[0]))
            elif parsed.path == "/api/unit":
                self.send_json(self.heretic_builder.unit_detail(params.get("id", [""])[0]))
            else:
                self.send_json({"error": "Not found"}, status=404)
        except Exception as error:
            self.fail(error)

    def do_POST(self):
        try:
            payload = self.read_json()
            if self.path == "/api/roster/create":
                self.send_json(self.heretic_builder.create_roster(payload))
            elif self.path == "/api/roster/delete":
                self.send_json(self.heretic_builder.delete_roster(payload["id"]))
            elif self.path == "/api/unit/add":
                self.send_json(self.heretic_builder.add_unit(payload["rosterId"], payload["datasheetId"]))
            elif self.path == "/api/unit/delete":
                self.send_json(self.heretic_builder.delete_unit(payload["id"]))
            elif self.path == "/api/unit/composition":
                self.send_json(self.heretic_builder.set_composition(payload["rosterUnitId"], payload["compositionId"]))
            elif self.path == "/api/wargear":
                self.send_json(self.heretic_builder.set_wargear(
                    payload["rosterUnitMiniatureId"],
                    payload["wargearOptionId"],
                    payload.get("count", 0),
                ))
            elif self.path == "/api/unit-wargear":
                self.send_json(self.heretic_builder.set_unit_wargear(
                    payload["rosterUnitId"],
                    payload["wargearOptionId"],
                    payload.get("count", 0),
                ))
            elif self.path == "/api/warlord":
                self.send_json(self.heretic_builder.set_warlord(
                    payload["rosterUnitMiniatureId"],
                    bool(payload.get("enabled")),
                ))
            else:
                self.send_json({"error": "Not found"}, status=404)
        except Exception as error:
            self.fail(error)


def main():
    parser = argparse.ArgumentParser(description="Minimal read/write HereticBuilder")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=4175, help="Preferred port")
    args = parser.parse_args()
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")
    Handler.heretic_builder = HereticBuilder(db_path)
    server, port = find_port(args.host, args.port)
    print(f"HereticBuilder: http://{args.host}:{port}", flush=True)
    print(f"Database: {html.escape(str(db_path))}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
