import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from roster_builder_core import HereticBuilder


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "heretic_db.sqlite"


HOME_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HereticTools</title>
  <style>
    :root {
      color-scheme: light;
      --desktop: #008080;
      --window: #c0c0c0;
      --shadow: #404040;
      --mid: #808080;
      --light: #ffffff;
      --ink: #000000;
      --title: #000080;
      --title-hot: #1084d0;
      --yellow: #ffff99;
      --cyan: #00ffff;
      --green: #00a000;
      --red: #b00020;
      --font: Tahoma, "MS Sans Serif", Arial, sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    html {
      min-height: 100%;
      background: var(--desktop);
    }

    body {
      margin: 0;
      min-width: 320px;
      min-height: 100vh;
      min-height: 100svh;
      color: var(--ink);
      background:
        linear-gradient(45deg, rgba(255, 255, 255, .06) 25%, transparent 25%) 0 0 / 16px 16px,
        linear-gradient(45deg, transparent 75%, rgba(0, 0, 0, .08) 75%) 0 0 / 16px 16px,
        var(--desktop);
      font-family: var(--font);
      font-size: 16px;
      letter-spacing: 0;
    }

    button {
      font: inherit;
      letter-spacing: 0;
    }

    .desktop {
      min-height: 100vh;
      min-height: 100svh;
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto;
      gap: 12px;
      padding: max(12px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right)) max(12px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
    }

    .shell {
      width: min(980px, 100%);
      margin: auto;
      background: var(--window);
      border-style: solid;
      border-width: 2px;
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      box-shadow: 1px 1px 0 var(--ink);
    }

    .title-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 30px;
      margin: 2px;
      padding: 3px 4px 3px 8px;
      color: var(--light);
      background: linear-gradient(90deg, var(--title), var(--title-hot));
      font-weight: 700;
    }

    .title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .title-controls {
      display: flex;
      flex: 0 0 auto;
      gap: 3px;
    }

    .title-control {
      width: 22px;
      height: 20px;
      display: grid;
      place-items: center;
      background: var(--window);
      color: var(--ink);
      border-style: solid;
      border-width: 2px;
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      font-size: 12px;
      line-height: 1;
    }

    .menu-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 2px;
      padding: 3px 5px 4px;
      border-bottom: 2px solid var(--mid);
      font-size: 14px;
    }

    .menu-item {
      min-height: 26px;
      padding: 4px 9px;
      border: 1px solid transparent;
    }

    .menu-item:first-letter {
      text-decoration: underline;
    }

    .menu-item:hover {
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      background: #d7d7d7;
    }

    .panel {
      display: grid;
      gap: 18px;
      padding: 22px;
      border-style: solid;
      border-width: 2px;
      border-color: var(--shadow) var(--light) var(--light) var(--shadow);
      margin: 8px;
      background:
        linear-gradient(90deg, rgba(255, 255, 255, .45) 1px, transparent 1px) 0 0 / 8px 8px,
        linear-gradient(0deg, rgba(255, 255, 255, .45) 1px, transparent 1px) 0 0 / 8px 8px,
        #dcdcdc;
    }

    .masthead {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: center;
      gap: 16px;
      min-width: 0;
    }

    .badge {
      width: 76px;
      height: 76px;
      display: grid;
      place-items: center;
      background: var(--yellow);
      border-style: solid;
      border-width: 2px;
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      box-shadow: inset -2px -2px 0 #e0c060, inset 2px 2px 0 #ffffcc;
      font-size: 36px;
      font-weight: 700;
      line-height: 1;
    }

    h1 {
      margin: 0;
      font-size: 40px;
      line-height: 1;
      font-weight: 800;
    }

    .subhead {
      margin: 8px 0 0;
      max-width: 60ch;
      font-size: 16px;
      line-height: 1.45;
    }

    .launch-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .launcher {
      min-width: 0;
      min-height: 154px;
      display: grid;
      align-content: center;
      justify-items: center;
      gap: 12px;
      padding: 16px 10px;
      color: var(--ink);
      background: var(--window);
      border-style: solid;
      border-width: 3px;
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      box-shadow: inset 1px 1px 0 #dfdfdf, 1px 1px 0 var(--ink);
      cursor: pointer;
      text-align: center;
      touch-action: manipulation;
    }

    .launcher:hover {
      background: #d7d7d7;
    }

    .launcher:active,
    .launcher[aria-pressed="true"] {
      border-color: var(--shadow) var(--light) var(--light) var(--shadow);
      box-shadow: inset 2px 2px 0 var(--mid);
      transform: translate(1px, 1px);
    }

    .launcher:focus-visible {
      outline: 2px dotted var(--ink);
      outline-offset: -9px;
    }

    .icon {
      position: relative;
      width: 52px;
      height: 52px;
      image-rendering: pixelated;
    }

    .icon-codex {
      background: #f7e68a;
      border: 3px solid var(--ink);
      box-shadow: inset 9px 0 0 #a00000, inset -4px -4px 0 #caa24a;
    }

    .icon-codex::before {
      content: "";
      position: absolute;
      left: 20px;
      top: 11px;
      width: 22px;
      height: 3px;
      background: var(--ink);
      box-shadow: 0 10px 0 var(--ink), 0 20px 0 var(--ink);
      opacity: .55;
    }

    .icon-builder {
      border: 3px solid var(--ink);
      background:
        linear-gradient(90deg, #d8d8d8 0 45%, transparent 45% 55%, #d8d8d8 55% 100%) 10px 10px / 32px 10px no-repeat,
        linear-gradient(90deg, transparent 0 44%, var(--ink) 44% 56%, transparent 56% 100%) 12px 22px / 28px 18px no-repeat,
        #00a0c8;
      box-shadow: inset -4px -4px 0 #006078;
    }

    .icon-builder::after {
      content: "";
      position: absolute;
      left: 15px;
      bottom: 7px;
      width: 22px;
      height: 8px;
      background: #804000;
      border: 2px solid var(--ink);
    }

    .icon-missions {
      border: 3px solid var(--ink);
      background: #e8e8e8;
      box-shadow: inset -4px -4px 0 #a0a0a0;
    }

    .icon-missions::before {
      content: "";
      position: absolute;
      left: 13px;
      top: 8px;
      width: 5px;
      height: 34px;
      background: var(--ink);
    }

    .icon-missions::after {
      content: "";
      position: absolute;
      left: 18px;
      top: 9px;
      width: 22px;
      height: 17px;
      background: var(--red);
      border: 2px solid var(--ink);
      box-shadow: 0 19px 0 -6px var(--green);
    }

    .icon-battler {
      border: 3px solid var(--ink);
      background:
        linear-gradient(45deg, transparent 0 40%, var(--ink) 40% 48%, #d8d8d8 48% 59%, var(--ink) 59% 67%, transparent 67%) center / 48px 48px no-repeat,
        linear-gradient(-45deg, transparent 0 40%, var(--ink) 40% 48%, #d8d8d8 48% 59%, var(--ink) 59% 67%, transparent 67%) center / 48px 48px no-repeat,
        #800080;
      box-shadow: inset -4px -4px 0 #400040;
    }

    .label {
      width: 100%;
      overflow-wrap: anywhere;
      font-size: 20px;
      font-weight: 700;
      line-height: 1.2;
    }

    .status-bar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 6px;
      padding: 0 8px 8px;
      font-size: 14px;
    }

    .status-cell {
      min-height: 24px;
      min-width: 0;
      display: flex;
      align-items: center;
      padding: 2px 6px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      border-style: solid;
      border-width: 2px;
      border-color: var(--shadow) var(--light) var(--light) var(--shadow);
      background: #d7d7d7;
    }

    .taskbar {
      min-height: 42px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px;
      background: var(--window);
      border-style: solid;
      border-width: 2px 0 0;
      border-color: var(--light);
      box-shadow: 0 -1px 0 var(--shadow);
    }

    .start-button {
      min-height: 32px;
      padding: 4px 12px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--window);
      border-style: solid;
      border-width: 2px;
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      font-weight: 700;
    }

    .start-mark {
      width: 18px;
      height: 18px;
      background:
        linear-gradient(90deg, var(--red) 0 50%, var(--green) 50% 100%) 0 0 / 18px 9px no-repeat,
        linear-gradient(90deg, var(--cyan) 0 50%, #ffff00 50% 100%) 0 9px / 18px 9px no-repeat;
      border: 1px solid var(--ink);
    }

    .task-status {
      flex: 1 1 auto;
      min-width: 0;
      min-height: 30px;
      display: flex;
      align-items: center;
      padding: 4px 8px;
      border-style: solid;
      border-width: 2px;
      border-color: var(--shadow) var(--light) var(--light) var(--shadow);
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }

    @media (max-width: 760px) {
      body {
        font-size: 15px;
      }

      .desktop {
        padding: 8px;
      }

      .panel {
        margin: 6px;
        padding: 16px;
        gap: 14px;
      }

      h1 {
        font-size: 32px;
      }

      .launch-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 460px) {
      .title-control:nth-child(1),
      .title-control:nth-child(2),
      .menu-bar {
        display: none;
      }

      .masthead {
        grid-template-columns: 1fr;
      }

      .badge {
        width: 60px;
        height: 60px;
        font-size: 30px;
      }

      h1 {
        font-size: 28px;
      }

      .launch-grid {
        grid-template-columns: 1fr;
      }

      .launcher {
        min-height: 96px;
        grid-template-columns: auto minmax(0, 1fr);
        align-content: center;
        justify-items: start;
        text-align: left;
        padding: 12px;
      }

      .launch-grid {
        gap: 8px;
      }

      .status-bar {
        grid-template-columns: 1fr;
      }
    }

    @media (prefers-reduced-motion: no-preference) {
      .launcher {
        transition: background-color .12s ease, transform .08s ease;
      }
    }
  </style>
</head>
<body>
  <main class="desktop">
    <section class="shell" aria-labelledby="homeTitle">
      <div class="title-bar">
        <div class="title">HereticTools.exe</div>
        <div class="title-controls" aria-hidden="true">
          <span class="title-control">_</span>
          <span class="title-control">[]</span>
          <span class="title-control">x</span>
        </div>
      </div>

      <nav class="menu-bar" aria-label="Application menu">
        <span class="menu-item">File</span>
        <span class="menu-item">View</span>
        <span class="menu-item">Tools</span>
        <span class="menu-item">Help</span>
      </nav>

      <div class="panel">
        <header class="masthead">
          <div class="badge" aria-hidden="true">HT</div>
          <div>
            <h1 id="homeTitle">HereticTools</h1>
            <p class="subhead">Command center for Codex, Builder, Missions, and Battler.</p>
          </div>
        </header>

        <div class="launch-grid" aria-label="Primary sections">
          <button class="launcher" type="button" data-app="Codex" data-route="codex" aria-pressed="false">
            <span class="icon icon-codex" aria-hidden="true"></span>
            <span class="label">Codex</span>
          </button>
          <button class="launcher" type="button" data-app="Builder" data-route="builder" aria-pressed="false">
            <span class="icon icon-builder" aria-hidden="true"></span>
            <span class="label">Builder</span>
          </button>
          <button class="launcher" type="button" data-app="Missions" data-route="missions" aria-pressed="false">
            <span class="icon icon-missions" aria-hidden="true"></span>
            <span class="label">Missions</span>
          </button>
          <button class="launcher" type="button" data-app="Battler" data-route="battler" aria-pressed="false">
            <span class="icon icon-battler" aria-hidden="true"></span>
            <span class="label">Battler</span>
          </button>
        </div>
      </div>

      <div class="status-bar" aria-live="polite">
        <div class="status-cell" id="statusText">Ready</div>
        <div class="status-cell">Local</div>
      </div>
    </section>

    <footer class="taskbar" aria-label="Desktop taskbar">
      <div class="start-button" aria-hidden="true"><span class="start-mark"></span>Start</div>
      <div class="task-status">HereticTools</div>
    </footer>
  </main>

  <script>
    const launchers = Array.from(document.querySelectorAll(".launcher"));
    const statusText = document.getElementById("statusText");

    function selectLauncher(button) {
      launchers.forEach((item) => item.setAttribute("aria-pressed", "false"));
      button.setAttribute("aria-pressed", "true");
      statusText.textContent = `${button.dataset.app} selected`;
      history.replaceState(null, "", `#${button.dataset.route}`);
    }

    launchers.forEach((button) => {
      button.addEventListener("click", () => selectLauncher(button));
    });

    const activeRoute = window.location.hash.replace("#", "");
    const activeButton = launchers.find((button) => button.dataset.route === activeRoute);
    if (activeButton) {
      selectLauncher(activeButton);
    }
  </script>
</body>
</html>
"""


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
                self.send_html(HOME_HTML)
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
