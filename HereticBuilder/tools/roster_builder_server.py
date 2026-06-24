import argparse
import csv
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from roster_builder_core import HereticBuilder


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "heretic_db.sqlite"
HERETIC_BUILDER_ROOT = Path(__file__).resolve().parents[1]
FACTION_IMAGE_ROOT = PROJECT_ROOT / "generated" / "faction_images_90s" / "images"
FACTION_IMAGE_MANIFEST = PROJECT_ROOT / "generated" / "faction_images_90s" / "manifest.csv"
ICON_ASSETS = {
    "/assets/icons/codex.png": HERETIC_BUILDER_ROOT / "assets" / "icons" / "codex.png",
    "/assets/icons/builder.png": HERETIC_BUILDER_ROOT / "assets" / "icons" / "builder.png",
    "/assets/icons/missions.png": HERETIC_BUILDER_ROOT / "assets" / "icons" / "missions.png",
    "/assets/icons/battler.png": HERETIC_BUILDER_ROOT / "assets" / "icons" / "battler.png",
    "/assets/icons/start.png": HERETIC_BUILDER_ROOT / "assets" / "icons" / "start.png",
}


def load_faction_image_manifest():
    if not FACTION_IMAGE_MANIFEST.exists():
        return {}, {}

    images_by_id = {}
    images_by_name = {}
    with FACTION_IMAGE_MANIFEST.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("status") != "ok":
                continue
            output_file = Path(row.get("output_file") or "")
            if not output_file.name:
                continue
            image = {
                "id": row.get("id") or "",
                "name": row.get("name") or "",
                "filename": output_file.name,
            }
            if image["id"]:
                images_by_id[image["id"]] = image
            if image["name"]:
                images_by_name[image["name"].lower()] = image
    return images_by_id, images_by_name


FACTION_IMAGES_BY_ID, FACTION_IMAGES_BY_NAME = load_faction_image_manifest()


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
      height: 100%;
      background: var(--desktop);
      overflow: hidden;
    }

    body {
      margin: 0;
      min-width: 320px;
      height: 100vh;
      height: 100svh;
      color: var(--ink);
      background:
        linear-gradient(45deg, rgba(255, 255, 255, .06) 25%, transparent 25%) 0 0 / 16px 16px,
        linear-gradient(45deg, transparent 75%, rgba(0, 0, 0, .08) 75%) 0 0 / 16px 16px,
        var(--desktop);
      font-family: var(--font);
      font-size: 16px;
      letter-spacing: 0;
      overflow: hidden;
    }

    button {
      font: inherit;
      letter-spacing: 0;
    }

    .desktop {
      height: 100vh;
      height: 100svh;
      min-height: 0;
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto;
      gap: 12px;
      padding: max(12px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right)) max(12px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
      overflow: hidden;
    }

    .shell {
      width: min(980px, 100%);
      max-height: 100%;
      min-height: 0;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      align-self: center;
      margin: auto;
      overflow: hidden;
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
      position: relative;
      min-height: 0;
      display: grid;
      grid-template-rows: minmax(0, 1fr);
      overflow: hidden;
      border-style: solid;
      border-width: 2px;
      border-color: var(--shadow) var(--light) var(--light) var(--shadow);
      margin: 8px;
      background: #d4d4d4;
    }

    .panel-content {
      min-height: 0;
      display: grid;
      gap: 18px;
      padding: 22px;
      overflow: auto;
      scrollbar-width: none;
    }

    .panel-content::-webkit-scrollbar {
      width: 0;
      height: 0;
    }

    .panel.is-scrollable .panel-content {
      padding-right: 40px;
    }

    .win-scrollbar {
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      width: 24px;
      display: grid;
      grid-template-rows: 24px minmax(0, 1fr) 24px;
      background: var(--window);
      z-index: 2;
    }

    .win-scrollbar[hidden] {
      display: none;
    }

    .scroll-button {
      width: 24px;
      min-width: 24px;
      height: 24px;
      display: grid;
      place-items: center;
      padding: 0;
      color: var(--ink);
      background: var(--window);
      border-style: solid;
      border-width: 2px;
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      font-size: 11px;
      line-height: 1;
      cursor: pointer;
    }

    .scroll-button:active {
      border-color: var(--shadow) var(--light) var(--light) var(--shadow);
      padding: 1px 0 0 1px;
    }

    .scroll-button::before {
      content: "";
      width: 0;
      height: 0;
      border-left: 3px solid transparent;
      border-right: 3px solid transparent;
    }

    .scroll-button-up::before {
      border-bottom: 5px solid var(--ink);
    }

    .scroll-button-down::before {
      border-top: 5px solid var(--ink);
    }

    .scroll-track {
      position: relative;
      min-height: 0;
      background: #d7d7d7;
      cursor: pointer;
    }

    .scroll-thumb {
      position: absolute;
      left: 2px;
      top: 0;
      width: 20px;
      min-height: 22px;
      background: var(--window);
      border-style: solid;
      border-width: 2px;
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      box-shadow: inset 1px 1px 0 #dfdfdf;
      cursor: grab;
      touch-action: none;
    }

    .scroll-thumb:active {
      cursor: grabbing;
      border-color: var(--shadow) var(--light) var(--light) var(--shadow);
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
      min-height: 176px;
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
      width: 112px;
      height: 112px;
      display: grid;
      place-items: center;
    }

    .icon-art {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      image-rendering: auto;
    }

    .label {
      width: 100%;
      overflow-wrap: anywhere;
      font-size: 20px;
      font-weight: 700;
      line-height: 1.2;
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
      width: 22px;
      height: 22px;
      display: inline-block;
      image-rendering: pixelated;
    }

    .start-art {
      display: block;
      width: 22px;
      height: 22px;
      object-fit: contain;
      filter: drop-shadow(1px 1px 0 var(--shadow));
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
      }

      .panel-content {
        padding: 16px;
        gap: 14px;
      }

      h1 {
        font-size: 32px;
      }

      .launch-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .icon {
        width: 92px;
        height: 92px;
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

      .icon {
        width: 72px;
        height: 72px;
      }

      .launch-grid {
        gap: 8px;
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
    <section class="shell" aria-label="HereticTools">
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
        <div class="panel-content">
          <div class="launch-grid" aria-label="Primary sections">
            <button class="launcher" type="button" data-app="Codex" data-route="codex" aria-pressed="false">
              <span class="icon" aria-hidden="true">
                <img class="icon-art" src="/assets/icons/codex.png" alt="">
              </span>
              <span class="label">Codex</span>
            </button>
            <button class="launcher" type="button" data-app="Builder" data-route="builder" aria-pressed="false">
              <span class="icon" aria-hidden="true">
                <img class="icon-art" src="/assets/icons/builder.png" alt="">
              </span>
              <span class="label">Builder</span>
            </button>
            <button class="launcher" type="button" data-app="Missions" data-route="missions" aria-pressed="false">
              <span class="icon" aria-hidden="true">
                <img class="icon-art" src="/assets/icons/missions.png" alt="">
              </span>
              <span class="label">Missions</span>
            </button>
            <button class="launcher" type="button" data-app="Battler" data-route="battler" aria-pressed="false">
              <span class="icon" aria-hidden="true">
                <img class="icon-art" src="/assets/icons/battler.png" alt="">
              </span>
              <span class="label">Battler</span>
            </button>
          </div>
        </div>
      </div>
    </section>

    <footer class="taskbar" aria-label="Desktop taskbar">
      <div class="start-button" aria-hidden="true">
        <span class="start-mark">
          <img class="start-art" src="/assets/icons/start.png" alt="">
        </span>
        Start
      </div>
      <div class="task-status">HereticTools</div>
    </footer>
  </main>

  <script>
    const launchers = Array.from(document.querySelectorAll(".launcher"));

    function setupWinScrollbars() {
      document.querySelectorAll(".panel").forEach((panel) => {
        const content = panel.querySelector(".panel-content");
        if (!content || panel.dataset.scrollbarReady === "true") {
          return;
        }

        panel.dataset.scrollbarReady = "true";
        const scrollbar = document.createElement("div");
        scrollbar.className = "win-scrollbar";
        scrollbar.hidden = true;
        scrollbar.innerHTML = `
          <button class="scroll-button scroll-button-up" type="button" aria-label="Scroll up"></button>
          <div class="scroll-track"><div class="scroll-thumb"></div></div>
          <button class="scroll-button scroll-button-down" type="button" aria-label="Scroll down"></button>
        `;
        panel.appendChild(scrollbar);

        const upButton = scrollbar.querySelector(".scroll-button-up");
        const downButton = scrollbar.querySelector(".scroll-button-down");
        const track = scrollbar.querySelector(".scroll-track");
        const thumb = scrollbar.querySelector(".scroll-thumb");

        function scrollStep() {
          return Math.max(64, Math.floor(content.clientHeight * 0.35));
        }

        function updateScrollbar() {
          const maxScroll = content.scrollHeight - content.clientHeight;
          const isScrollable = maxScroll > 1;
          panel.classList.toggle("is-scrollable", isScrollable);
          scrollbar.hidden = !isScrollable;
          if (!isScrollable) {
            return;
          }

          const trackHeight = track.clientHeight;
          const thumbHeight = Math.max(24, Math.floor(content.clientHeight / content.scrollHeight * trackHeight));
          const travel = Math.max(0, trackHeight - thumbHeight);
          const thumbTop = maxScroll ? Math.round(content.scrollTop / maxScroll * travel) : 0;
          thumb.style.height = `${thumbHeight}px`;
          thumb.style.transform = `translateY(${thumbTop}px)`;
        }

        upButton.addEventListener("click", () => content.scrollBy({ top: -scrollStep(), behavior: "auto" }));
        downButton.addEventListener("click", () => content.scrollBy({ top: scrollStep(), behavior: "auto" }));
        track.addEventListener("click", (event) => {
          if (event.target !== track) {
            return;
          }
          const thumbRect = thumb.getBoundingClientRect();
          content.scrollBy({ top: event.clientY < thumbRect.top ? -content.clientHeight : content.clientHeight, behavior: "auto" });
        });

        let dragStart = null;
        thumb.addEventListener("pointerdown", (event) => {
          dragStart = { y: event.clientY, scrollTop: content.scrollTop };
          thumb.setPointerCapture(event.pointerId);
          event.preventDefault();
        });
        thumb.addEventListener("pointermove", (event) => {
          if (!dragStart) {
            return;
          }
          const maxScroll = content.scrollHeight - content.clientHeight;
          const travel = Math.max(1, track.clientHeight - thumb.offsetHeight);
          content.scrollTop = dragStart.scrollTop + (event.clientY - dragStart.y) * maxScroll / travel;
        });
        thumb.addEventListener("pointerup", () => {
          dragStart = null;
        });
        thumb.addEventListener("pointercancel", () => {
          dragStart = null;
        });

        content.addEventListener("scroll", updateScrollbar, { passive: true });
        window.addEventListener("resize", updateScrollbar);
        if ("ResizeObserver" in window) {
          const observer = new ResizeObserver(updateScrollbar);
          observer.observe(panel);
          observer.observe(content);
        }
        requestAnimationFrame(updateScrollbar);
      });
    }

    function selectLauncher(button) {
      launchers.forEach((item) => item.setAttribute("aria-pressed", "false"));
      button.setAttribute("aria-pressed", "true");
      history.replaceState(null, "", `#${button.dataset.route}`);
    }

    launchers.forEach((button) => {
      button.addEventListener("click", () => {
        selectLauncher(button);
        if (button.dataset.route === "codex") {
          window.location.href = "/codex";
        }
      });
    });

    const activeRoute = window.location.hash.replace("#", "");
    const activeButton = launchers.find((button) => button.dataset.route === activeRoute);
    if (activeButton) {
      selectLauncher(activeButton);
    }

    setupWinScrollbars();
    window.addEventListener("load", setupWinScrollbars);
  </script>
</body>
</html>
"""


def _extract_embedded_style(html_text):
    start = html_text.index("<style>") + len("<style>")
    end = html_text.index("</style>", start)
    return html_text[start:end]


DESKTOP_STYLE = _extract_embedded_style(HOME_HTML)


CODEX_PAGE_STYLE = DESKTOP_STYLE + r"""
    .codex-page a {
      color: inherit;
      text-decoration: none;
    }

    .codex-page .shell {
      width: min(980px, 100%);
    }

    .codex-page .title-bar {
      cursor: pointer;
    }

    .codex-page .title-bar:focus-visible {
      outline: 2px dotted var(--light);
      outline-offset: -4px;
    }

    .codex-page .menu-item:focus-visible {
      border-color: var(--light) var(--shadow) var(--shadow) var(--light);
      background: #d7d7d7;
      outline: none;
    }

    .codex-root-page .launch-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .core-rules-page .launch-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .faction-list-page .launch-grid {
      grid-template-columns: repeat(auto-fit, minmax(min(384px, 100%), 384px));
      justify-content: center;
    }

    .codex-page .launcher {
      min-height: 176px;
      justify-items: start;
      padding: 20px;
      text-align: left;
    }

    .codex-page .section-tag {
      min-height: 26px;
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      background: var(--title);
      color: var(--light);
      font-size: 14px;
      font-weight: 700;
      line-height: 1;
    }

    .codex-page .label {
      font-size: 28px;
      line-height: 1.05;
    }

    .faction-list-page .launcher {
      min-height: 96px;
      padding: 14px;
    }

    .faction-list-page .label {
      font-size: 20px;
      line-height: 1.12;
    }

    .faction-list-page .launcher.has-faction-image {
      position: relative;
      width: min(384px, 100%);
      min-height: 0;
      height: auto;
      aspect-ratio: 384 / 100;
      isolation: isolate;
      overflow: hidden;
      color: var(--light);
      text-align: left;
      text-shadow: 1px 1px 0 var(--ink);
    }

    .faction-list-page .launcher.has-faction-image::after {
      content: "";
      position: absolute;
      inset: 0;
      z-index: 1;
      background: linear-gradient(180deg, transparent 0%, transparent 40%, rgba(0, 0, 0, .32) 65%, rgba(0, 0, 0, .64) 100%);
      pointer-events: none;
    }

    .faction-list-page .launcher.has-faction-image .faction-art-frame {
      position: absolute;
      top: -3px;
      left: -3px;
      z-index: 0;
      display: block;
      width: calc(100% + 6px);
      overflow: hidden;
      border: 0;
      pointer-events: none;
    }

    .faction-list-page .launcher.has-faction-image .faction-art {
      display: block;
      width: 100%;
      height: auto;
      max-width: none;
      image-rendering: auto;
    }

    .faction-list-page .launcher.has-faction-image .label {
      position: absolute;
      right: 10px;
      bottom: 6px;
      left: 10px;
      z-index: 2;
      width: auto;
      color: var(--light);
      line-height: 1.08;
      overflow-wrap: normal;
      word-break: normal;
    }

    @media (max-width: 760px) {
      .codex-root-page .launch-grid,
      .core-rules-page .launch-grid,
      .faction-list-page .launch-grid {
        grid-template-columns: repeat(auto-fit, minmax(min(384px, 100%), 384px));
      }

      .codex-page .launcher {
        min-height: 132px;
        padding: 16px;
      }

      .codex-page .label {
        font-size: 24px;
      }

      .faction-list-page .launcher {
        min-height: 88px;
        padding: 12px;
      }

      .faction-list-page .label {
        font-size: 18px;
      }

      .faction-list-page .launcher.has-faction-image {
        min-height: 0;
        padding: 12px;
      }

    }

    @media (max-width: 460px) {
      .codex-page .menu-bar {
        display: none;
      }

      .codex-root-page .launch-grid,
      .core-rules-page .launch-grid,
      .faction-list-page .launch-grid {
        grid-template-columns: 1fr;
      }

      .codex-page .launcher {
        grid-template-columns: 1fr;
        min-height: 96px;
      }

      .many-buttons-page .launcher {
        width: min(286px, 100%);
        min-height: 68px;
        justify-self: center;
        padding: 10px 12px;
      }

      .many-buttons-page .launcher.has-faction-image {
        width: min(384px, 100%);
        min-height: 0;
        padding: 10px 12px;
      }

      .many-buttons-page .label {
        font-size: 17px;
        line-height: 1.12;
      }

      .many-buttons-page .launcher.has-faction-image .label {
        right: 8px;
        bottom: 5px;
        left: 8px;
        font-size: 16px;
        line-height: 1.02;
      }
    }
"""


MOCKUP_PAGE_STYLE = CODEX_PAGE_STYLE + r"""
    .mockup-page .panel-content {
      gap: 18px;
    }

    .mockup-set {
      display: grid;
      gap: 8px;
      min-width: 0;
    }

    .mockup-set > .section-tag {
      justify-self: start;
    }

    .mockup-page .launch-grid {
      grid-template-columns: repeat(auto-fit, minmax(min(384px, 100%), 384px));
      justify-content: center;
    }

    .mockup-page .faction-mockup {
      position: relative;
      width: min(384px, 100%);
      min-height: 0;
      height: auto;
      aspect-ratio: 384 / 100;
      min-width: 0;
      overflow: hidden;
      isolation: isolate;
      color: var(--light);
      text-shadow: 1px 1px 0 var(--ink);
    }

    .faction-art-frame {
      position: absolute;
      z-index: 0;
      display: block;
      overflow: hidden;
      border: 0;
      pointer-events: none;
    }

    .faction-art {
      display: block;
      max-width: none;
      image-rendering: auto;
    }

    .mockup-page .faction-mockup::after {
      content: "";
      position: absolute;
      inset: 0;
      z-index: 1;
      pointer-events: none;
    }

    .mockup-page .faction-mockup .label {
      position: relative;
      z-index: 2;
      color: var(--light);
      overflow-wrap: normal;
      word-break: normal;
    }

    .faction-mockup--right {
      grid-template-columns: minmax(0, 1fr);
      align-items: center;
      justify-items: start;
      text-align: left;
    }

    .faction-mockup--right::after {
      background: linear-gradient(90deg, rgba(0, 0, 0, .46) 0%, rgba(0, 0, 0, .26) 44%, transparent 72%);
    }

    .faction-mockup--right .faction-art-frame {
      top: 0;
      left: 50%;
      height: 100%;
      transform: translateX(-50%);
    }

    .faction-mockup--right .faction-art {
      width: auto;
      height: 100%;
    }

    .faction-mockup--right .label {
      max-width: 118px;
      line-height: 1.08;
    }

    .faction-mockup--top {
      align-content: end;
      justify-items: start;
      text-align: left;
    }

    .faction-mockup--top::after {
      background: linear-gradient(180deg, transparent 0%, transparent 40%, rgba(0, 0, 0, .32) 65%, rgba(0, 0, 0, .64) 100%);
    }

    .faction-mockup--top .faction-art-frame {
      top: -3px;
      left: -3px;
      width: calc(100% + 6px);
    }

    .faction-mockup--top .faction-art {
      width: 100%;
      height: auto;
    }

    .mockup-page .faction-mockup--top .label {
      position: absolute;
      right: 10px;
      bottom: 6px;
      left: 10px;
      width: auto;
      line-height: 1.08;
    }

    @media (max-width: 760px) {
      .mockup-page .faction-mockup {
        height: auto;
      }
    }

    @media (max-width: 460px) {
      .mockup-page .launch-grid {
        grid-template-columns: minmax(0, 1fr);
      }

      .mockup-page .faction-mockup {
        width: 100%;
        height: auto;
      }

      .mockup-page .faction-mockup--right {
        grid-template-columns: minmax(0, 1fr);
      }

      .faction-mockup--right .label {
        max-width: 142px;
      }

      .faction-mockup--right::after {
        background: linear-gradient(90deg, rgba(0, 0, 0, .5) 0%, rgba(0, 0, 0, .28) 58%, transparent 84%);
      }

      .mockup-page .faction-mockup--top .label {
        right: 8px;
        bottom: 5px;
        left: 8px;
        font-size: 16px;
        line-height: 1.02;
      }
    }
"""


def escape_html(value):
    return html.escape(str(value), quote=False)


def escape_attr(value):
    return html.escape(str(value), quote=True)


def faction_image_url(image):
    return f"/assets/faction-images/{escape_attr(image['filename'])}"


def find_faction_image(name, faction_id=None):
    if faction_id and faction_id in FACTION_IMAGES_BY_ID:
        return FACTION_IMAGES_BY_ID[faction_id]
    return FACTION_IMAGES_BY_NAME.get(str(name).lower())


def render_mockup_button(image, variant):
    label = escape_html(image["name"])
    label_attr = escape_attr(image["name"])
    src = faction_image_url(image)
    image_html = (
        f'<span class="faction-art-frame" aria-hidden="true">'
        f'<img class="faction-art" src="{src}" alt=""></span>'
    )
    return (
        f'            <button class="launcher faction-mockup faction-mockup--{variant}" '
        f'type="button" data-app="{label_attr}" data-route="{escape_attr(image["id"])}" '
        f'aria-pressed="false">\n'
        f'              {image_html}\n'
        f'              <span class="label">{label}</span>\n'
        f'            </button>'
    )


def render_mockup_grid(variant, label, images):
    buttons = "\n".join(render_mockup_button(image, variant) for image in images)
    return f"""          <section class="mockup-set" aria-label="{escape_attr(label)}">
            <div class="section-tag">{escape_html(label)}</div>
            <div class="launch-grid mockup-grid mockup-grid--{variant}">
{buttons}
            </div>
          </section>"""


def render_launcher(button):
    href = f' data-href="{escape_attr(button["href"])}"' if button.get("href") else ""
    classes = ["launcher"]
    tag = ""
    if button.get("tag"):
        tag = f'\n            <span class="section-tag">{escape_html(button["tag"])}</span>'
    image = button.get("image")
    image_html = ""
    if image:
        classes.append("has-faction-image")
        src = faction_image_url(image)
        image_html = (
            f'            <span class="faction-art-frame" aria-hidden="true">'
            f'<img class="faction-art" src="{src}" alt=""></span>\n'
        )
    class_attr = escape_attr(" ".join(classes))
    return (
        f'          <button class="{class_attr}" type="button" data-app="{escape_attr(button["label"])}" '
        f'data-route="{escape_attr(button["route"])}"{href} aria-pressed="false">\n'
        f'{image_html}'
        f'            <span class="label">{escape_html(button["label"])}</span>{tag}\n'
        f'          </button>'
    )


def render_codex_page(title, window_title, task_title, page_class, grid_label, buttons, back_href, back_label):
    button_html = "\n".join(render_launcher(button) for button in buttons)
    if len(buttons) > 5:
        page_class = f"{page_class} many-buttons-page"
    title_text = escape_html(title)
    window_text = escape_html(window_title)
    document_title = escape_html(f"{title} - HereticTools")
    task_text = escape_html(task_title)
    page_class_attr = escape_attr(page_class)
    grid_label_attr = escape_attr(grid_label)
    back_href_attr = escape_attr(back_href)
    back_label_attr = escape_attr(back_label)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{document_title}</title>
  <style>{CODEX_PAGE_STYLE}
  </style>
</head>
<body>
  <main class="desktop codex-page {page_class_attr}">
    <section class="shell" aria-label="{title_text}">
      <div class="title-bar" role="button" tabindex="0" aria-label="{back_label_attr}" title="{back_label_attr}" data-up-href="{back_href_attr}">
        <div class="title">{window_text}</div>
        <div class="title-controls" aria-hidden="true">
          <span class="title-control">_</span>
          <span class="title-control">[]</span>
          <span class="title-control">x</span>
        </div>
      </div>

      <nav class="menu-bar" aria-label="Application menu">
        <a class="menu-item" href="{back_href_attr}">File</a>
        <span class="menu-item">View</span>
        <span class="menu-item">Tools</span>
        <span class="menu-item">Help</span>
      </nav>

      <div class="panel">
        <div class="panel-content">
          <div class="launch-grid" aria-label="{grid_label_attr}">
{button_html}
          </div>
        </div>
      </div>
    </section>

    <footer class="taskbar" aria-label="Desktop taskbar">
      <a class="start-button" href="/">
        <span class="start-mark" aria-hidden="true">
          <img class="start-art" src="/assets/icons/start.png" alt="">
        </span>
        Start
      </a>
      <div class="task-status">{task_text}</div>
    </footer>
  </main>

  <script>
    const launchers = Array.from(document.querySelectorAll(".launcher"));
    const titleBar = document.querySelector(".title-bar");

    function setupWinScrollbars() {{
      document.querySelectorAll(".panel").forEach((panel) => {{
        const content = panel.querySelector(".panel-content");
        if (!content || panel.dataset.scrollbarReady === "true") {{
          return;
        }}

        panel.dataset.scrollbarReady = "true";
        const scrollbar = document.createElement("div");
        scrollbar.className = "win-scrollbar";
        scrollbar.hidden = true;
        scrollbar.innerHTML = `
          <button class="scroll-button scroll-button-up" type="button" aria-label="Scroll up"></button>
          <div class="scroll-track"><div class="scroll-thumb"></div></div>
          <button class="scroll-button scroll-button-down" type="button" aria-label="Scroll down"></button>
        `;
        panel.appendChild(scrollbar);

        const upButton = scrollbar.querySelector(".scroll-button-up");
        const downButton = scrollbar.querySelector(".scroll-button-down");
        const track = scrollbar.querySelector(".scroll-track");
        const thumb = scrollbar.querySelector(".scroll-thumb");

        function scrollStep() {{
          return Math.max(64, Math.floor(content.clientHeight * 0.35));
        }}

        function updateScrollbar() {{
          const maxScroll = content.scrollHeight - content.clientHeight;
          const isScrollable = maxScroll > 1;
          panel.classList.toggle("is-scrollable", isScrollable);
          scrollbar.hidden = !isScrollable;
          if (!isScrollable) {{
            return;
          }}

          const trackHeight = track.clientHeight;
          const thumbHeight = Math.max(24, Math.floor(content.clientHeight / content.scrollHeight * trackHeight));
          const travel = Math.max(0, trackHeight - thumbHeight);
          const thumbTop = maxScroll ? Math.round(content.scrollTop / maxScroll * travel) : 0;
          thumb.style.height = `${{thumbHeight}}px`;
          thumb.style.transform = `translateY(${{thumbTop}}px)`;
        }}

        upButton.addEventListener("click", () => content.scrollBy({{ top: -scrollStep(), behavior: "auto" }}));
        downButton.addEventListener("click", () => content.scrollBy({{ top: scrollStep(), behavior: "auto" }}));
        track.addEventListener("click", (event) => {{
          if (event.target !== track) {{
            return;
          }}
          const thumbRect = thumb.getBoundingClientRect();
          content.scrollBy({{ top: event.clientY < thumbRect.top ? -content.clientHeight : content.clientHeight, behavior: "auto" }});
        }});

        let dragStart = null;
        thumb.addEventListener("pointerdown", (event) => {{
          dragStart = {{ y: event.clientY, scrollTop: content.scrollTop }};
          thumb.setPointerCapture(event.pointerId);
          event.preventDefault();
        }});
        thumb.addEventListener("pointermove", (event) => {{
          if (!dragStart) {{
            return;
          }}
          const maxScroll = content.scrollHeight - content.clientHeight;
          const travel = Math.max(1, track.clientHeight - thumb.offsetHeight);
          content.scrollTop = dragStart.scrollTop + (event.clientY - dragStart.y) * maxScroll / travel;
        }});
        thumb.addEventListener("pointerup", () => {{
          dragStart = null;
        }});
        thumb.addEventListener("pointercancel", () => {{
          dragStart = null;
        }});

        content.addEventListener("scroll", updateScrollbar, {{ passive: true }});
        window.addEventListener("resize", updateScrollbar);
        if ("ResizeObserver" in window) {{
          const observer = new ResizeObserver(updateScrollbar);
          observer.observe(panel);
          observer.observe(content);
        }}
        requestAnimationFrame(updateScrollbar);
      }});
    }}

    function goUp() {{
      window.location.href = titleBar.dataset.upHref;
    }}

    function selectLauncher(button) {{
      launchers.forEach((item) => item.setAttribute("aria-pressed", "false"));
      button.setAttribute("aria-pressed", "true");
      if (button.dataset.href) {{
        window.location.href = button.dataset.href;
        return;
      }}
      history.replaceState(null, "", "#" + button.dataset.route);
    }}

    launchers.forEach((button) => {{
      button.addEventListener("click", () => selectLauncher(button));
    }});

    titleBar.addEventListener("click", goUp);
    titleBar.addEventListener("keydown", (event) => {{
      if (event.key === "Enter" || event.key === " ") {{
        event.preventDefault();
        goUp();
      }}
    }});

    const activeRoute = window.location.hash.replace("#", "");
    const activeButton = launchers.find((button) => button.dataset.route === activeRoute);
    if (activeButton) {{
      activeButton.setAttribute("aria-pressed", "true");
    }}

    setupWinScrollbars();
    window.addEventListener("load", setupWinScrollbars);
  </script>
</body>
</html>
"""


MOCKUP_FACTION_IDS = (
    "01623188-9470-4441-96b0-e06eb2572bb5",
    "aee1b46d-3461-4d5d-a612-0efd05dd843d",
    "2e79f9cd-94dc-48ca-bddf-6d5e877609c5",
    "47670bc3-64b8-4c2d-9154-7391f132688b",
    "0b30f1e3-1e5c-4823-afa1-07951433a270",
    "1a241f8e-2d79-47c4-82b1-f6faea353970",
)


MOCKUP_WINDOW_SCRIPT = r"""
  <script>
    const titleBar = document.querySelector(".title-bar");
    const launchers = Array.from(document.querySelectorAll(".launcher"));

    function setupWinScrollbars() {
      document.querySelectorAll(".panel").forEach((panel) => {
        const content = panel.querySelector(".panel-content");
        if (!content || panel.dataset.scrollbarReady === "true") {
          return;
        }

        panel.dataset.scrollbarReady = "true";
        const scrollbar = document.createElement("div");
        scrollbar.className = "win-scrollbar";
        scrollbar.hidden = true;
        scrollbar.innerHTML = `
          <button class="scroll-button scroll-button-up" type="button" aria-label="Scroll up"></button>
          <div class="scroll-track"><div class="scroll-thumb"></div></div>
          <button class="scroll-button scroll-button-down" type="button" aria-label="Scroll down"></button>
        `;
        panel.appendChild(scrollbar);

        const upButton = scrollbar.querySelector(".scroll-button-up");
        const downButton = scrollbar.querySelector(".scroll-button-down");
        const track = scrollbar.querySelector(".scroll-track");
        const thumb = scrollbar.querySelector(".scroll-thumb");

        function scrollStep() {
          return Math.max(64, Math.floor(content.clientHeight * 0.35));
        }

        function updateScrollbar() {
          const maxScroll = content.scrollHeight - content.clientHeight;
          const isScrollable = maxScroll > 1;
          panel.classList.toggle("is-scrollable", isScrollable);
          scrollbar.hidden = !isScrollable;
          if (!isScrollable) {
            return;
          }

          const trackHeight = track.clientHeight;
          const thumbHeight = Math.max(24, Math.floor(content.clientHeight / content.scrollHeight * trackHeight));
          const travel = Math.max(0, trackHeight - thumbHeight);
          const thumbTop = maxScroll ? Math.round(content.scrollTop / maxScroll * travel) : 0;
          thumb.style.height = `${thumbHeight}px`;
          thumb.style.transform = `translateY(${thumbTop}px)`;
        }

        upButton.addEventListener("click", () => content.scrollBy({ top: -scrollStep(), behavior: "auto" }));
        downButton.addEventListener("click", () => content.scrollBy({ top: scrollStep(), behavior: "auto" }));
        track.addEventListener("click", (event) => {
          if (event.target !== track) {
            return;
          }
          const thumbRect = thumb.getBoundingClientRect();
          content.scrollBy({ top: event.clientY < thumbRect.top ? -content.clientHeight : content.clientHeight, behavior: "auto" });
        });

        let dragStart = null;
        thumb.addEventListener("pointerdown", (event) => {
          dragStart = { y: event.clientY, scrollTop: content.scrollTop };
          thumb.setPointerCapture(event.pointerId);
          event.preventDefault();
        });
        thumb.addEventListener("pointermove", (event) => {
          if (!dragStart) {
            return;
          }
          const maxScroll = content.scrollHeight - content.clientHeight;
          const travel = Math.max(1, track.clientHeight - thumb.offsetHeight);
          content.scrollTop = dragStart.scrollTop + (event.clientY - dragStart.y) * maxScroll / travel;
        });
        thumb.addEventListener("pointerup", () => {
          dragStart = null;
        });
        thumb.addEventListener("pointercancel", () => {
          dragStart = null;
        });

        content.addEventListener("scroll", updateScrollbar, { passive: true });
        window.addEventListener("resize", updateScrollbar);
        if ("ResizeObserver" in window) {
          const observer = new ResizeObserver(updateScrollbar);
          observer.observe(panel);
          observer.observe(content);
        }
        requestAnimationFrame(updateScrollbar);
      });
    }

    function goUp() {
      window.location.href = titleBar.dataset.upHref;
    }

    launchers.forEach((button) => {
      button.addEventListener("click", () => {
        launchers.forEach((item) => item.setAttribute("aria-pressed", "false"));
        button.setAttribute("aria-pressed", "true");
      });
    });

    titleBar.addEventListener("click", goUp);
    titleBar.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        goUp();
      }
    });

    setupWinScrollbars();
    window.addEventListener("load", setupWinScrollbars);
  </script>
"""


def render_faction_image_mockups():
    images = [
        FACTION_IMAGES_BY_ID[faction_id]
        for faction_id in MOCKUP_FACTION_IDS
        if faction_id in FACTION_IMAGES_BY_ID
    ]
    mockup_html = "\n".join([
        render_mockup_grid("right", "A. Image Right", images),
        render_mockup_grid("top", "B. Image Top", images),
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Faction Image Mockups - HereticTools</title>
  <style>{MOCKUP_PAGE_STYLE}
  </style>
</head>
<body>
  <main class="desktop codex-page faction-list-page many-buttons-page mockup-page">
    <section class="shell" aria-label="Faction Image Mockups">
      <div class="title-bar" role="button" tabindex="0" aria-label="Back to Codex" title="Back to Codex" data-up-href="/codex">
        <div class="title">FactionMockups.exe</div>
        <div class="title-controls" aria-hidden="true">
          <span class="title-control">_</span>
          <span class="title-control">[]</span>
          <span class="title-control">x</span>
        </div>
      </div>

      <nav class="menu-bar" aria-label="Application menu">
        <a class="menu-item" href="/codex">File</a>
        <span class="menu-item">View</span>
        <span class="menu-item">Tools</span>
        <span class="menu-item">Help</span>
      </nav>

      <div class="panel">
        <div class="panel-content">
{mockup_html}
        </div>
      </div>
    </section>

    <footer class="taskbar" aria-label="Desktop taskbar">
      <a class="start-button" href="/">
        <span class="start-mark" aria-hidden="true">
          <img class="start-art" src="/assets/icons/start.png" alt="">
        </span>
        Start
      </a>
      <div class="task-status">Faction Mockups</div>
    </footer>
  </main>

{MOCKUP_WINDOW_SCRIPT}
</body>
</html>
"""


CODEX_HTML = render_codex_page(
    title="Codex",
    window_title="Codex.exe",
    task_title="Codex",
    page_class="codex-root-page",
    grid_label="Codex sections",
    back_href="/",
    back_label="Back to HereticTools",
    buttons=[
        {"label": "Core Rules", "tag": "Reference", "route": "core-rules", "href": "/codex/core-rules"},
        {"label": "Imperium", "route": "imperium", "href": "/codex/imperium"},
        {"label": "Chaos", "route": "chaos", "href": "/codex/chaos"},
        {"label": "Xenos", "route": "xenos", "href": "/codex/xenos"},
    ],
)


CORE_RULES_HTML = render_codex_page(
    title="Core Rules",
    window_title="CoreRules.exe",
    task_title="Core Rules",
    page_class="core-rules-page",
    grid_label="Core Rules sections",
    back_href="/codex",
    back_label="Back to Codex",
    buttons=[
        {"label": "Rules", "tag": "Reference", "route": "rules"},
        {"label": "Stratagems", "tag": "Tactics", "route": "stratagems"},
        {"label": "FAQ", "tag": "Updates", "route": "faq"},
    ],
)


ADEPTUS_ASTARTES_FACTION_IDS = {
    "01623188-9470-4441-96b0-e06eb2572bb5",
    "28162de0-fd36-450b-87ee-39e973ead32d",
    "864734c9-d6c7-4486-92de-9b8271a6a1e5",
    "fa0e86ef-b5da-4510-9a9f-8cd86267bb6a",
    "51ac31b0-93ff-4c94-a9a5-5c1a97fbbb75",
    "93423323-3abb-4a72-a51e-b8ac54f2f98d",
    "cd8dd346-3b5a-489d-8e47-22711922098d",
    "780aa838-ed0f-44b7-bca3-ff54d357a07b",
    "8d74ba46-ac06-4c05-a90c-5d25282b2c94",
    "4db683fe-87a0-4138-9b53-4b326c8e8521",
    "bc367514-36b7-47c6-bd3f-ffbf85f5cfd9",
    "b7d67027-cf56-4cd1-8127-9e7658de4ef5",
    "a65e110c-2b80-4887-8b2f-1f335b4dd450",
}


FACTION_GROUPS = {
    "imperium": {
        "title": "Imperium",
        "window_title": "Imperium.exe",
        "ids": {
            "aee1b46d-3461-4d5d-a612-0efd05dd843d",
            "6cc4ee5e-3bc6-4142-8147-2e1a9fb6e82c",
            "60ecf26b-0c2b-4ea3-8a29-5f06bd02f6d8",
            "fec6e6a5-f491-4d83-99c0-e46e510f29e8",
            "2f81671f-3164-4ab0-93c0-4a99746b5996",
            "9b847488-9663-48dc-b819-08ab93ac4382",
            "5737b3b6-1c33-4cb3-828c-08b6909197aa",
        },
    },
    "chaos": {
        "title": "Chaos",
        "window_title": "Chaos.exe",
        "ids": {
            "2e79f9cd-94dc-48ca-bddf-6d5e877609c5",
            "19176137-2faa-4d6e-adb4-2572510032b7",
            "b63a417d-63ea-4d20-b7f0-85c66c56979e",
            "d4162ab7-8356-4e4e-adb3-5e3b631d47e6",
            "40a70c91-675a-4ac5-aa97-daedb9cb6f11",
            "25d2c58f-59b5-4a4f-b597-495ba322ce07",
            "46cec02c-a75a-4e1e-b53a-afab701e94c6",
            "8bd4c67d-4aba-4502-8561-7c6c6faae51d",
        },
    },
    "xenos": {
        "title": "Xenos",
        "window_title": "Xenos.exe",
        "ids": {
            "2cb72f92-bfc7-4d2c-a183-b2bff6b26bfc",
            "43bbfe97-4c14-47be-be2b-90de3e6756b1",
            "800c0387-5033-47da-bad0-f42e53b37453",
            "a42808ab-f00b-4664-aed5-8d9341b96e36",
            "47670bc3-64b8-4c2d-9154-7391f132688b",
            "0b30f1e3-1e5c-4823-afa1-07951433a270",
            "b30b3258-9140-46b8-9c9e-113be9008ea9",
            "1a241f8e-2d79-47c4-82b1-f6faea353970",
        },
    },
}


def render_faction_group_page(heretic_builder, group_key):
    group = FACTION_GROUPS[group_key]
    factions = heretic_builder.bootstrap()["factions"]
    group_ids = group["ids"]
    group_factions = [faction for faction in factions if faction["id"] in group_ids]
    buttons = [
        {
            "label": faction["name"],
            "route": faction["id"],
            "image": find_faction_image(faction["name"], faction["id"]),
        }
        for faction in group_factions
    ]
    if group_key == "imperium":
        buttons.append({
            "label": "Adeptus Astartes",
            "route": "adeptus-astartes",
            "href": "/codex/imperium/adeptus-astartes",
            "image": find_faction_image("Adeptus Astartes"),
        })
        buttons.sort(key=lambda button: button["label"].lower())
    return render_codex_page(
        title=group["title"],
        window_title=group["window_title"],
        task_title=group["title"],
        page_class="faction-list-page",
        grid_label="Faction sections",
        back_href="/codex",
        back_label="Back to Codex",
        buttons=buttons,
    )


def render_adeptus_astartes_page(heretic_builder):
    factions = heretic_builder.bootstrap()["factions"]
    group_factions = [
        faction
        for faction in factions
        if faction["id"] in ADEPTUS_ASTARTES_FACTION_IDS
    ]
    return render_codex_page(
        title="Adeptus Astartes",
        window_title="AdeptusAstartes.exe",
        task_title="Adeptus Astartes",
        page_class="faction-list-page",
        grid_label="Adeptus Astartes factions",
        back_href="/codex/imperium",
        back_label="Back to Imperium",
        buttons=[
            {
                "label": faction["name"],
                "route": faction["id"],
                "image": find_faction_image(faction["name"], faction["id"]),
            }
            for faction in group_factions
        ],
    )


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

    def send_png(self, path, status=200):
        if not path.exists():
            self.send_json({"error": "Not found"}, status=404)
            return
        body = path.read_bytes()
        self.send_response(status)
        self.send_header("Content-Type", "image/png")
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
            elif parsed.path == "/codex":
                self.send_html(CODEX_HTML)
            elif parsed.path == "/codex/core-rules":
                self.send_html(CORE_RULES_HTML)
            elif parsed.path == "/codex/faction-image-mockups":
                self.send_html(render_faction_image_mockups())
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
