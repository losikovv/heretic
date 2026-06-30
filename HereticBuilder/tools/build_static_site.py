#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
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
CONFIG_FILENAME = "heretic.toml"


@dataclass(frozen=True)
class StaticBuildConfig:
    db: Path
    out: Path
    base_path: str
    mount_codex_at_root: bool
    source: Path
    config: Path | None = None
    profile: str | None = None


@dataclass(frozen=True)
class StaticBuildResult:
    out_dir: Path
    page_count: int
    base_path: str
    mount_codex_at_root: bool


def normalize_base_path(value):
    path = str(value or "").strip().rstrip("/")
    if not path or path == "/":
        return ""
    return "/" + path.lstrip("/")


def resolve_config_path(source_dir, config_path=None):
    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = source_dir / path
        return path.resolve()

    path = source_dir / CONFIG_FILENAME
    if path.exists():
        return path.resolve()
    return None


def load_toml_config(path):
    if not path:
        return {}
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def merge_profile_config(config, profile):
    build_config = dict(config.get("build", {}))
    if not profile:
        return build_config

    profiles = config.get("profiles", {})
    if profile not in profiles:
        known = ", ".join(sorted(profiles)) or "none"
        raise SystemExit(f"Unknown build profile '{profile}'. Available profiles: {known}")
    build_config.update(profiles[profile])
    return build_config


def resolve_source_path(path):
    return Path(path or PROJECT_ROOT).expanduser().resolve()


def resolve_project_path(value, source_dir):
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = source_dir / path
    return path.resolve()


def static_build_config_from_args(args):
    source_dir = resolve_source_path(args.source)
    config_path = resolve_config_path(source_dir, args.config)
    raw_config = merge_profile_config(load_toml_config(config_path), args.profile)

    db = args.db if args.db is not None else raw_config.get("db", str(DEFAULT_DB))
    out = args.out if args.out is not None else raw_config.get("out", "dist")
    base_path = args.base_path if args.base_path is not None else raw_config.get("base_path", "")
    mount_codex_at_root = (
        args.mount_codex_at_root
        if args.mount_codex_at_root is not None
        else bool(raw_config.get("mount_codex_at_root", False))
    )

    return StaticBuildConfig(
        db=resolve_project_path(db, source_dir),
        out=resolve_project_path(out, source_dir),
        base_path=normalize_base_path(base_path),
        mount_codex_at_root=mount_codex_at_root,
        source=source_dir,
        config=config_path,
        profile=args.profile,
    )


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


def codex_root_href(path):
    if path == "/codex":
        return "/"
    if path.startswith("/codex/"):
        return path.removeprefix("/codex")
    return path


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
    return codex_root_href(route)


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


def prepare_out_dir(out_dir, protected_dirs=()):
    resolved = out_dir.resolve()
    protected = {
        PROJECT_ROOT.resolve(),
        HERETIC_BUILDER_ROOT.resolve(),
        TOOLS_ROOT.resolve(),
        Path.home().resolve(),
        Path("/").resolve(),
    }
    protected.update(Path(path).resolve() for path in protected_dirs)
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


def search_index_items(builder, mount_codex_at_root=False):
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
        if mount_codex_at_root:
            href = codex_root_href(href)
        normalized.append({
            "type": compact_text(item.get("type")) or "Result",
            "title": title,
            "meta": compact_text(item.get("meta")),
            "text": compact_text(item.get("text")),
            "href": href,
        })
    return normalized


def write_search_index(builder, out_dir, mount_codex_at_root=False):
    payload = {
        "version": 1,
        "items": search_index_items(builder, mount_codex_at_root),
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


def add_static_build_arguments(parser):
    parser.add_argument("--source", default=str(PROJECT_ROOT), help="Project source directory")
    parser.add_argument("--config", help=f"Build config path, defaults to {CONFIG_FILENAME} under --source")
    parser.add_argument("--profile", help="Build profile from the config file")
    parser.add_argument("--db", help="SQLite database path")
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--base-path", help="Site base path, e.g. /codex for project Pages")
    parser.add_argument(
        "--mount-codex-at-root",
        action="store_true",
        default=None,
        help="Publish the Codex section at the static site root.",
    )
    parser.add_argument(
        "--no-mount-codex-at-root",
        action="store_false",
        dest="mount_codex_at_root",
        help="Publish the home page at the static site root and Codex under /codex.",
    )
    return parser


def parse_args():
    parser = argparse.ArgumentParser(description="Build a static HereticBuilder site for GitHub Pages.")
    add_static_build_arguments(parser)
    return parser.parse_args()


def build_static_site(config):
    if not config.db.exists():
        raise SystemExit(f"Database does not exist: {config.db}")

    out_dir = prepare_out_dir(config.out, protected_dirs=(config.source,))
    builder = HereticBuilder(config.db)

    copy_assets(out_dir)
    page_count = write_static_pages(builder, out_dir, config.base_path, config.mount_codex_at_root)
    write_search_index(builder, out_dir, config.mount_codex_at_root)

    return StaticBuildResult(
        out_dir=out_dir,
        page_count=page_count,
        base_path=config.base_path,
        mount_codex_at_root=config.mount_codex_at_root,
    )


def build_from_args(args):
    return build_static_site(static_build_config_from_args(args))


def print_build_result(result):
    print(f"Static site: {result.out_dir}")
    print(f"Pages: {result.page_count}")
    print(f"Base path: {result.base_path or '/'}")
    print(f"Codex mount: {'root' if result.mount_codex_at_root else '/codex'}")


def main():
    result = build_from_args(parse_args())
    print_build_result(result)


if __name__ == "__main__":
    main()
