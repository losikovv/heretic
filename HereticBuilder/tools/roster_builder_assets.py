from pathlib import Path
import csv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "heretic_db.sqlite"
HERETIC_BUILDER_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = HERETIC_BUILDER_ROOT / "static"
ASSET_ROOT = HERETIC_BUILDER_ROOT / "assets"
FACTION_IMAGE_ROOT = ASSET_ROOT / "faction-images"
FACTION_IMAGE_MANIFEST = FACTION_IMAGE_ROOT / "manifest.csv"
UNIT_IMAGE_ROOT = ASSET_ROOT / "unit-images"
UNIT_IMAGE_MANIFEST = UNIT_IMAGE_ROOT / "manifest.csv"

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


def load_unit_image_manifest():
    if not UNIT_IMAGE_MANIFEST.exists():
        return {}, {}

    images_by_id = {}
    images_by_name = {}
    with UNIT_IMAGE_MANIFEST.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("status") not in {"ok", "exists"}:
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


UNIT_IMAGES_BY_ID, UNIT_IMAGES_BY_NAME = load_unit_image_manifest()
