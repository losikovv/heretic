import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from roster_builder_assets import DEFAULT_DB, FACTION_IMAGE_ROOT, ICON_ASSETS, STATIC_ROOT, UNIT_IMAGE_ROOT
from roster_builder_codex import (
    render_adeptus_astartes_page,
    render_codex_root_page,
    render_core_faq_page,
    render_core_rule_page,
    render_core_rules_page,
    render_core_rules_rules_page,
    render_core_rules_section_page,
    render_core_stratagems_page,
    render_faction_army_rule_page,
    render_faction_datasheets_page,
    render_faction_detachment_page,
    render_faction_detachments_page,
    render_faction_group_page,
    render_faction_page,
)
from roster_builder_codex_datasheet import render_datasheet_page
from roster_builder_core import HereticBuilder
from roster_builder_templates import render_template


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

    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type=None, status=200):
        if not path.is_file():
            self.send_json({"error": "Not found"}, status=404)
            return
        body = path.read_bytes()
        content_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_png(self, path, status=200):
        self.send_file(path, "image/png", status)

    def send_static(self, request_path):
        static_root = STATIC_ROOT.resolve()
        relative_path = unquote(request_path.removeprefix("/static/"))
        path = (static_root / relative_path).resolve()
        if path == static_root or static_root not in path.parents:
            self.send_json({"error": "Not found"}, status=404)
            return
        self.send_file(path)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def fail(self, error):
        self.send_json({"error": str(error)}, status=400)

    def send_faction_codex_page(self, path):
        parts = path.strip("/").split("/")
        if len(parts) == 3:
            self.send_html(render_faction_page(self.heretic_builder, parts[2]))
        elif len(parts) == 4 and parts[3] == "army-rule":
            self.send_html(render_faction_army_rule_page(self.heretic_builder, parts[2]))
        elif len(parts) == 4 and parts[3] == "detachments":
            self.send_html(render_faction_detachments_page(self.heretic_builder, parts[2]))
        elif len(parts) == 5 and parts[3] == "detachment":
            self.send_html(render_faction_detachment_page(self.heretic_builder, parts[2], parts[4]))
        elif len(parts) == 4 and parts[3] == "datasheets":
            self.send_html(render_faction_datasheets_page(self.heretic_builder, parts[2]))
        elif len(parts) == 5 and parts[3] == "datasheet":
            self.send_html(render_datasheet_page(self.heretic_builder, parts[2], parts[4]))
        else:
            self.send_json({"error": "Not found"}, status=404)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                self.send_html(render_template("home.html"))
            elif parsed.path.startswith("/static/"):
                self.send_static(parsed.path)
            elif parsed.path == "/codex":
                self.send_html(render_codex_root_page())
            elif parsed.path == "/codex/core-rules":
                self.send_html(render_core_rules_page())
            elif parsed.path == "/codex/core-rules/rules":
                self.send_html(render_core_rules_rules_page(self.heretic_builder))
            elif parsed.path == "/codex/core-rules/stratagems":
                self.send_html(render_core_stratagems_page(self.heretic_builder))
            elif parsed.path == "/codex/core-rules/faq":
                self.send_html(render_core_faq_page(self.heretic_builder))
            elif parsed.path.startswith("/codex/core-rules/section/"):
                self.send_html(render_core_rules_section_page(
                    self.heretic_builder,
                    unquote(parsed.path.removeprefix("/codex/core-rules/section/")),
                ))
            elif parsed.path.startswith("/codex/core-rules/rule/"):
                ref = unquote(parsed.path.removeprefix("/codex/core-rules/rule/"))
                # Major rule references are section landing pages with sub-rule buttons.
                import re as _re
                _m = _re.fullmatch(r"(\d{1,2})(?:\.00)?", ref.strip())
                if _m:
                    self.send_response(302)
                    self.send_header("Location", f"/codex/core-rules/section/{int(_m.group(1)):02d}")
                    self.end_headers()
                else:
                    self.send_html(render_core_rule_page(self.heretic_builder, ref))
            elif parsed.path.startswith("/codex/faction/"):
                self.send_faction_codex_page(parsed.path)
            elif parsed.path == "/codex/imperium":
                self.send_html(render_faction_group_page(self.heretic_builder, "imperium"))
            elif parsed.path == "/codex/imperium/adeptus-astartes":
                self.send_html(render_adeptus_astartes_page(self.heretic_builder))
            elif parsed.path == "/codex/chaos":
                self.send_html(render_faction_group_page(self.heretic_builder, "chaos"))
            elif parsed.path == "/codex/xenos":
                self.send_html(render_faction_group_page(self.heretic_builder, "xenos"))
            elif parsed.path in ICON_ASSETS:
                self.send_png(ICON_ASSETS[parsed.path])
            elif parsed.path.startswith("/assets/faction-images/"):
                filename = Path(unquote(parsed.path)).name
                self.send_png(FACTION_IMAGE_ROOT / filename)
            elif parsed.path.startswith("/assets/unit-images/"):
                filename = Path(unquote(parsed.path)).name
                self.send_png(UNIT_IMAGE_ROOT / filename)
            elif parsed.path == "/api/search":
                self.send_json(self.heretic_builder.search(
                    params.get("q", [""])[0],
                    params.get("limit", ["30"])[0],
                ))
            elif parsed.path == "/api/bootstrap":
                self.send_json(self.heretic_builder.bootstrap())
            elif parsed.path == "/api/detachments":
                self.send_json(self.heretic_builder.detachments(params.get("factionId", [""])[0]))
            elif parsed.path == "/api/datasheets":
                self.send_json(self.heretic_builder.datasheets(
                    params.get("factionId", [""])[0],
                    params.get("detachmentIds", [params.get("detachmentId", [""])[0]])[0],
                    params.get("q", [""])[0],
                    params.get("allyType", ["native"])[0],
                ))
            elif parsed.path == "/api/allied-factions":
                self.send_json(self.heretic_builder.allied_factions(params.get("rosterId", [""])[0]))
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
            elif self.path == "/api/roster/detachments":
                self.send_json(self.heretic_builder.set_roster_detachments(
                    payload["rosterId"],
                    payload.get("detachmentIds", []),
                ))
            elif self.path == "/api/unit/add":
                self.send_json(self.heretic_builder.add_unit(
                    payload["rosterId"],
                    payload["datasheetId"],
                    payload.get("allyType", "native"),
                ))
            elif self.path == "/api/unit/delete":
                self.send_json(self.heretic_builder.delete_unit(payload["id"]))
            elif self.path == "/api/unit/composition":
                self.send_json(self.heretic_builder.set_composition(payload["rosterUnitId"], payload["compositionId"]))
            elif self.path == "/api/allegiance":
                self.send_json(self.heretic_builder.set_allegiance_ability(
                    payload["rosterUnitId"],
                    payload["allegianceAbilityId"],
                    bool(payload.get("enabled")),
                ))
            elif self.path == "/api/unit-enhancement":
                self.send_json(self.heretic_builder.set_unit_enhancement(
                    payload["rosterUnitId"],
                    payload["enhancementId"],
                    bool(payload.get("enabled")),
                ))
            elif self.path == "/api/model-enhancement":
                self.send_json(self.heretic_builder.set_miniature_enhancement(
                    payload["rosterUnitMiniatureId"],
                    payload["enhancementId"],
                    bool(payload.get("enabled")),
                ))
            elif self.path == "/api/attached/create":
                self.send_json(self.heretic_builder.create_attached_unit(
                    payload["bodyguardUnitId"],
                    payload["attachedUnitId"],
                    payload.get("attachedType", "leader"),
                ))
            elif self.path == "/api/attached/delete":
                self.send_json(self.heretic_builder.delete_attached_unit(payload["id"]))
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
    print(f"Database: {db_path}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
