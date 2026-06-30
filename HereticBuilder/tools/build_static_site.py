#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parent
HERETIC_BUILDER_ROOT = TOOLS_ROOT.parent
PROJECT_ROOT = HERETIC_BUILDER_ROOT.parent

if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from roster_builder_assets import (  # noqa: E402
    DEFAULT_DB,
    STATIC_ROOT,
)
from roster_builder_codex import (  # noqa: E402
    CORE_RULES_PUBLICATION_ID,
    core_rule_section_href,
    core_rule_sections,
    datasheet_href,
    detachment_slug_map_for_faction,
    detachment_href,
    faction_href,
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
    visible_codex_datasheets_for_faction,
)
from roster_builder_codex_datasheet import render_datasheet_page  # noqa: E402
from roster_builder_codex_rich_text import core_rule_href  # noqa: E402
from roster_builder_core import HereticBuilder  # noqa: E402
from roster_builder_routes import scoped_slug_map  # noqa: E402
from roster_builder_search import compact_text  # noqa: E402
from roster_builder_templates import render_template  # noqa: E402


STATIC_SEARCH_METHODS = (
    "search_static_items",
    "search_faction_items",
    "search_core_rule_items",
    "search_army_rule_items",
    "search_datasheet_items",
    "search_detachment_items",
    "search_detachment_rule_items",
    "search_enhancement_items",
    "search_detachment_stratagem_items",
)


def normalize_base_path(value):
    path = str(value or "").strip().rstrip("/")
    if not path or path == "/":
        return ""
    return "/" + path.lstrip("/")


def site_url(path, base_path):
    if not path or not path.startswith("/") or path.startswith("//"):
        return path
    return f"{base_path}{path}"


def codex_root_site_url(path, base_path):
    if path == "/codex":
        return site_url("/", base_path)
    if path.startswith("/codex/"):
        return site_url(path.removeprefix("/codex"), base_path)
    return site_url(path, base_path)


def inject_static_config(html, base_path, mount_codex_at_root=False):
    runtime_base_path = "" if mount_codex_at_root else base_path
    config = (
        f'  <meta name="heretic-base-path" content="{escape(runtime_base_path, quote=True)}">\n'
        f'  <meta name="heretic-search-index" content="{escape(site_url("/search-index.json", base_path), quote=True)}">'
    )
    if "</head>" in html:
        html = html.replace("</head>", f"{config}\n</head>", 1)

    def replace_attr(match):
        prefix, url, suffix = match.groups()
        if mount_codex_at_root:
            url = codex_root_site_url(url, base_path)
        else:
            url = site_url(url, base_path)
        return f"{prefix}{escape(url, quote=True)}{suffix}"

    html = re.sub(
        r'((?:href|src|data-href|data-up-href)=["\'])(/[^"\']*)(["\'])',
        replace_attr,
        html,
    )
    if base_path:
        html = html.replace("url('/", f"url('{base_path}/")
        html = html.replace('url("/', f'url("{base_path}/')
    return html


def codex_root_route(route):
    if route == "/codex":
        return "/"
    if route.startswith("/codex/"):
        return route.removeprefix("/codex")
    return route


def route_to_file(out_dir, route, mount_codex_at_root=False):
    if mount_codex_at_root:
        route = codex_root_route(route)
    path = route.split("?", 1)[0].split("#", 1)[0].strip("/")
    if not path:
        return out_dir / "index.html"
    return out_dir / path / "index.html"


def write_route(out_dir, route, html, base_path, mount_codex_at_root=False):
    target = route_to_file(out_dir, route, mount_codex_at_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(inject_static_config(html, base_path, mount_codex_at_root), encoding="utf-8")


def copy_dir(src, dest):
    if not src.exists():
        return
    shutil.copytree(src, dest, dirs_exist_ok=True)


def prepare_out_dir(out_dir):
    resolved = out_dir.resolve()
    protected = {
        PROJECT_ROOT.resolve(),
        HERETIC_BUILDER_ROOT.resolve(),
        TOOLS_ROOT.resolve(),
        Path.home().resolve(),
        Path("/").resolve(),
    }
    if resolved in protected:
        raise SystemExit(f"Refusing to clear protected output directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    return resolved


def copy_assets(out_dir):
    copy_dir(STATIC_ROOT, out_dir / "static")
    copy_dir(HERETIC_BUILDER_ROOT / "assets", out_dir / "assets")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")


def search_index_items(builder):
    with builder.connect(readonly=True) as conn:
        items = []
        for method_name in STATIC_SEARCH_METHODS:
            items.extend(getattr(builder, method_name)(conn))

    normalized = []
    for item in items:
        title = compact_text(item.get("title"))
        href = item.get("href") or ""
        if not title or not href:
            continue
        normalized.append({
            "type": compact_text(item.get("type")) or "Result",
            "title": title,
            "meta": compact_text(item.get("meta")),
            "text": compact_text(item.get("text")),
            "href": href,
        })
    return normalized


def write_search_index(builder, out_dir):
    payload = {
        "version": 1,
        "items": search_index_items(builder),
    }
    (out_dir / "search-index.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def core_rule_reference_routes(builder):
    with builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select distinct rc.subtitle
            from rule_container rc
            join rule_section rs on rs.id = rc.ruleSectionId
            where rs.publicationId = ?
              and rc.subtitle is not null
            order by rc.subtitle
            """,
            [CORE_RULES_PUBLICATION_ID],
        ).fetchall()
    routes = []
    for row in rows:
        route = core_rule_href(row["subtitle"])
        if route and "/rule/" in route:
            routes.append((route, row["subtitle"]))
    return routes


def detachment_routes(builder):
    routes = []
    for faction in builder.bootstrap()["factions"]:
        detachments = builder.detachments(faction["id"]).get("detachments", [])
        slug_by_id = detachment_slug_map_for_faction(builder, faction["id"])
        routes.extend(
            (detachment_href(faction, detachment, slug_by_id[detachment["id"]]), faction["id"], detachment["id"])
            for detachment in detachments
        )
    return routes


def datasheet_routes(builder):
    routes = []
    for faction in builder.bootstrap()["factions"]:
        native_datasheets, allied_datasheets = visible_codex_datasheets_for_faction(builder, faction["id"])
        datasheets = [
            {**datasheet, "allyType": "native"}
            for datasheet in native_datasheets
        ] + [
            {**datasheet, "allyType": "allied"}
            for datasheet in allied_datasheets
        ]
        slug_by_id = scoped_slug_map(datasheets)
        routes.extend(
            (datasheet_href(faction, datasheet, slug_by_id[datasheet["id"]]), faction["id"], datasheet["id"])
            for datasheet in datasheets
        )
    return routes


def write_static_pages(builder, out_dir, base_path, mount_codex_at_root=False):
    count = 0

    def write(route, html):
        nonlocal count
        write_route(out_dir, route, html, base_path, mount_codex_at_root)
        count += 1

    if not mount_codex_at_root:
        write("/", render_template("home.html"))
    write("/codex", render_codex_root_page())
    write("/codex/core-rules", render_core_rules_page())
    write("/codex/core-rules/rules", render_core_rules_rules_page(builder))
    write("/codex/core-rules/stratagems", render_core_stratagems_page(builder))
    write("/codex/core-rules/faq", render_core_faq_page(builder))

    for section in core_rule_sections(builder):
        route = core_rule_section_href(section)
        write(route, render_core_rules_section_page(builder, route.rsplit("/", 1)[-1]))

    for route, reference in core_rule_reference_routes(builder):
        write(route, render_core_rule_page(builder, reference))

    for group_key in ("imperium", "chaos", "xenos"):
        write(f"/codex/{group_key}", render_faction_group_page(builder, group_key))
    write("/codex/imperium/adeptus-astartes", render_adeptus_astartes_page(builder))

    for faction in builder.bootstrap()["factions"]:
        route = faction_href(faction)
        write(route, render_faction_page(builder, faction["id"]))
        write(f"{route}/army-rule", render_faction_army_rule_page(builder, faction["id"]))
        write(f"{route}/detachments", render_faction_detachments_page(builder, faction["id"]))
        write(f"{route}/datasheets", render_faction_datasheets_page(builder, faction["id"]))

    for route, faction_id, detachment_id in detachment_routes(builder):
        write(route, render_faction_detachment_page(builder, faction_id, detachment_id))

    for route, faction_id, datasheet_id in datasheet_routes(builder):
        write(route, render_datasheet_page(builder, faction_id, datasheet_id))

    return count


def parse_args():
    parser = argparse.ArgumentParser(description="Build a static HereticBuilder site for GitHub Pages.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "dist"), help="Output directory")
    parser.add_argument("--base-path", default="", help="Site base path, e.g. /HereticSheets for project Pages")
    parser.add_argument(
        "--mount-codex-at-root",
        action="store_true",
        help="Publish the Codex section at the static site root.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")

    out_dir = prepare_out_dir(Path(args.out))
    builder = HereticBuilder(db_path)
    base_path = normalize_base_path(args.base_path)

    copy_assets(out_dir)
    page_count = write_static_pages(builder, out_dir, base_path, args.mount_codex_at_root)
    write_search_index(builder, out_dir)

    print(f"Static site: {out_dir}")
    print(f"Pages: {page_count}")
    print(f"Base path: {base_path or '/'}")


if __name__ == "__main__":
    main()
