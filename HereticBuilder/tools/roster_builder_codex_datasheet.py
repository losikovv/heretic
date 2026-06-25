import re

from roster_builder_codex import (
    escape_attr,
    escape_html,
    faction_by_id,
    faction_href,
    faqs_for_entity,
    find_unit_image,
    normalize_rule_text,
    render_codex_content_page,
    render_faq_update_sections,
    render_rich_text,
    unit_image_url,
)
from roster_builder_templates import render_template
from roster_builder_utils import dict_row


def option_group_title(group):
    text = normalize_rule_text(group.get("instructionText"))
    first_line = next((line.strip(" ■") for line in text.splitlines() if line.strip()), "")
    return first_line or "Wargear"


def profile_display_name(profile):
    item_name = profile["itemName"]
    profile_name = profile["profileName"]
    if profile_name.lower() == item_name.lower():
        return item_name
    return f"{item_name} - {profile_name}"


def format_points(value, signed=False):
    value = int(value or 0)
    if signed and value > 0:
        return f"+{value} pts"
    return f"{value} pts"


def ordinal(value):
    value = int(value)
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def base_size_entries(value):
    text = str(value or "").strip()
    if not text or text == "-":
        return []
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            label, base_size = line.split(":", 1)
            entries.append((label.strip(), base_size.strip()))
            continue
        for base_size in re.split(r"\s*[,;]\s*", line):
            base_size = base_size.strip()
            if base_size:
                entries.append(("Base", base_size))
    return entries


def weapon_ability_tags(abilities):
    text = normalize_rule_text(abilities)
    if text in {"", "-"}:
        return ""
    tags = [tag.strip() for tag in re.split(r",|\n", text) if tag.strip()]
    return "".join(
        render_template(
            "codex_unit_weapon_ability_tag.html",
            label=escape_html(tag),
        )
        for tag in tags
    )


def weapon_bucket(profile):
    return "melee" if str(profile.get("type") or "").lower() == "melee" else "ranged"


def weapon_profile_skill(profile):
    if weapon_bucket(profile) == "melee":
        return profile.get("weaponSkill") or "-"
    return profile.get("ballisticSkill") or "-"


def weapon_profile_key(profile):
    return (
        profile_display_name(profile).lower(),
        str(profile.get("type") or "").lower(),
        str(profile.get("range") or ""),
        str(profile.get("attacks") or ""),
        str(weapon_profile_skill(profile)),
        str(profile.get("strength") or ""),
        str(profile.get("armourPenetration") or ""),
        str(profile.get("damage") or ""),
        str(profile.get("abilities") or "-").lower(),
    )


def plain_wargear_group_rule(group):
    text = normalize_rule_text(group.get("instructionText"))
    if option_group_title(group).lower() == "default wargear":
        default_items = [
            item
            for item in group["items"]
            if item.get("defaultValue")
        ]
        if default_items:
            item_lines = []
            for item in default_items:
                count = item.get("defaultValue") or 1
                prefix = f"{count} " if count > 1 else ""
                item_lines.append(f"◦ {prefix}{item['itemName']}")
            text = "\n".join([text or "Default Wargear", *item_lines])
    return text.strip()


def datasheet_wargear_rules(conn, datasheet_id, wargear_groups):
    default_rules = [
        plain_wargear_group_rule(group)
        for group in wargear_groups
        if option_group_title(group).lower() == "default wargear"
    ]
    rows = [
        row["rulesText"]
        for row in conn.execute(
            """
            select rulesText
            from wargear_rule
            where datasheetId = ?
            order by displayOrder
            """,
            [datasheet_id],
        )
    ]
    if rows:
        return [rule for rule in [*default_rules, *rows] if rule.strip()]
    return [
        plain_wargear_group_rule(group)
        for group in wargear_groups
        if plain_wargear_group_rule(group)
    ]


def datasheet_wargear_groups(conn, datasheet_id):
    rows = conn.execute(
        """
        select wog.id as groupId, wog.instructionText, wog.displayOrder as groupOrder,
               wog.isStaticWargear, m.name as miniatureName,
               wo.id as optionId, wo.defaultValue, wo.points, wo.displayOrder as optionOrder,
               wi.id as wargearItemId, wi.name as itemName, wi.wargearType, wi.ruleText
        from wargear_option_group wog
        join wargear_option wo on wo.wargearOptionGroupId = wog.id
        join wargear_item wi on wi.id = wo.wargearItemId
        left join miniature m on m.id = wog.miniatureId
        where wog.datasheetId = ?
        order by wog.displayOrder, lower(coalesce(m.name, '')), wo.displayOrder, lower(wi.name)
        """,
        [datasheet_id],
    ).fetchall()
    groups = []
    by_id = {}
    seen_options = set()
    for row in rows:
        group = by_id.get(row["groupId"])
        if not group:
            group = {
                "id": row["groupId"],
                "instructionText": row["instructionText"],
                "displayOrder": row["groupOrder"],
                "isStaticWargear": row["isStaticWargear"],
                "miniatureName": row["miniatureName"],
                "items": [],
                "profiles": [],
            }
            by_id[row["groupId"]] = group
            groups.append(group)
        if row["optionId"] in seen_options:
            continue
        seen_options.add(row["optionId"])
        group["items"].append({
            "id": row["optionId"],
            "itemId": row["wargearItemId"],
            "itemName": row["itemName"],
            "wargearType": row["wargearType"],
            "ruleText": row["ruleText"],
            "defaultValue": row["defaultValue"],
            "points": row["points"],
        })

    if not groups:
        return []

    profile_rows = conn.execute(
        """
        select wog.id as groupId, wo.id as optionId, wo.defaultValue, wo.points,
               wi.id as wargearItemId,
               wi.name as itemName, wip.id as profileId, wip.name as profileName,
               wip.type, wip.range, wip.attacks, wip.ballisticSkill, wip.weaponSkill,
               wip.strength, wip.armourPenetration, wip.damage, wip.displayOrder,
               group_concat(wa.name, ', ') as abilities
        from wargear_option_group wog
        join wargear_option wo on wo.wargearOptionGroupId = wog.id
        join wargear_item wi on wi.id = wo.wargearItemId
        join wargear_item_profile wip on wip.wargearItemId = wi.id
        left join wargear_item_profile_wargear_ability wipwa on wipwa.wargearItemProfileId = wip.id
        left join wargear_ability wa on wa.id = wipwa.wargearAbilityId
        where wog.datasheetId = ?
        group by wog.id, wo.id, wip.id
        order by wog.displayOrder,
                 case lower(wip.type) when 'ranged' then 0 when 'melee' then 1 else 2 end,
                 lower(wi.name), wip.displayOrder
        """,
        [datasheet_id],
    ).fetchall()
    for row in profile_rows:
        group = by_id.get(row["groupId"])
        if not group:
            continue
        group["profiles"].append(dict_row(row))
    return groups


def paid_wargear_options(wargear_groups):
    seen = set()
    result = []
    for group in wargear_groups:
        for item in group["items"]:
            if not item.get("points"):
                continue
            key = (item["itemName"].lower(), item["points"])
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return sorted(result, key=lambda item: (abs(item["points"]), item["itemName"].lower()))


def datasheet_detail(heretic_builder, faction_id, datasheet_id):
    with heretic_builder.connect(readonly=True) as conn:
        row = conn.execute(
            """
            select d.id, d.name, d.baseSize, d.unitComposition, d.lore,
                   coalesce((
                     select uc.points
                     from unit_composition uc
                     where uc.datasheetId = d.id
                     order by uc.isDefault desc, uc.displayOrder
                     limit 1
                   ), 0) as points
            from datasheet d
            where d.id = ?
            """,
            [datasheet_id],
        ).fetchone()
        if not row:
            raise ValueError("Datasheet not found")

        datasheet = dict_row(row)
        composition_faction_ids = heretic_builder.composition_faction_keyword_ids(conn, faction_id)
        composition = heretic_builder.default_composition(conn, datasheet_id, composition_faction_ids, [])
        if composition:
            datasheet["points"] = composition["points"]
        point_options = [
            comp
            for comp in heretic_builder.compositions(conn, datasheet_id, {"factionKeywordId": composition_faction_ids}, [])
            if comp.get("available")
        ]

        miniatures = [
            dict_row(miniature)
            for miniature in conn.execute(
                """
                select id, name, movement, toughness, save, wounds, leadership,
                       objectiveControl, statlineHidden, displayOrder
                from miniature
                where datasheetId = ?
                order by displayOrder, lower(name)
                """,
                [datasheet_id],
            )
        ]
        rules = [
            dict_row(rule)
            for rule in conn.execute(
                """
                select name, rules, displayOrder
                from datasheet_rule
                where datasheetId = ?
                order by displayOrder, lower(name)
                """,
                [datasheet_id],
            )
        ]
        abilities = [
            {**dict_row(ability), "subAbilities": []}
            for ability in conn.execute(
                """
                select da.id, da.name, da.abilityType, da.rules, da.lore,
                       da.subAbilityHeader, da.isPsychic, da.isAura, da.isBondsman,
                       dda.restriction, dda.displayOrder
                from datasheet_datasheet_ability dda
                join datasheet_ability da on da.id = dda.datasheetAbilityId
                where dda.datasheetId = ?
                order by dda.displayOrder, lower(da.name)
                """,
                [datasheet_id],
            )
        ]
        ability_by_id = {ability["id"]: ability for ability in abilities}
        if ability_by_id:
            placeholders = ",".join("?" for _ in ability_by_id)
            for sub_ability in conn.execute(
                f"""
                select datasheetAbilityId, name, rules, displayOrder
                from datasheet_sub_ability
                where datasheetAbilityId in ({placeholders})
                order by displayOrder, lower(name)
                """,
                list(ability_by_id),
            ):
                ability_by_id[sub_ability["datasheetAbilityId"]]["subAbilities"].append(dict_row(sub_ability))

        keywords = [
            row["name"]
            for row in conn.execute(
                """
                select distinct k.name
                from miniature m
                join miniature_keyword mk on mk.miniatureId = m.id
                join keyword k on k.id = mk.keywordId
                where m.datasheetId = ?
                order by lower(k.name)
                """,
                [datasheet_id],
            )
        ]
        invulnerable_saves = [
            dict_row(save)
            for save in conn.execute(
                """
                select inv.miniatureId, inv.save, inv.meleeSave, inv.rangedSave, inv.rules,
                       m.name as miniatureName
                from invulnerable_save inv
                left join miniature m on m.id = inv.miniatureId
                where inv.datasheetId = ?
                order by lower(coalesce(m.name, ''))
                """,
                [datasheet_id],
            )
        ]
        points_steps = [
            dict_row(step)
            for step in conn.execute(
                """
                select stepAt, stepPoints
                from datasheet_points_step
                where datasheetId = ?
                order by stepAt
                """,
                [datasheet_id],
            )
        ]
        wargear_groups = datasheet_wargear_groups(conn, datasheet_id)
        wargear_rules = datasheet_wargear_rules(conn, datasheet_id, wargear_groups)
        damage_rows = [
            dict_row(damage)
            for damage in conn.execute(
                """
                select name, damagedAt, rules, displayOrder
                from datasheet_damage
                where datasheetId = ?
                order by displayOrder, lower(name)
                """,
                [datasheet_id],
            )
        ]

    return {
        "datasheet": datasheet,
        "pointOptions": point_options,
        "pointsSteps": points_steps,
        "miniatures": miniatures,
        "rules": rules,
        "abilities": abilities,
        "keywords": keywords,
        "invulnerableSaves": invulnerable_saves,
        "wargearGroups": wargear_groups,
        "wargearRules": wargear_rules,
        "paidWargear": paid_wargear_options(wargear_groups),
        "damageRows": damage_rows,
    }


def is_empty_rule(value):
    return normalize_rule_text(value) in {"", "-"}


def render_unit_meta_item(label, value):
    if value in (None, ""):
        return ""
    return render_template(
        "codex_unit_meta_item.html",
        label=escape_html(label),
        value=escape_html(value),
    )


def format_invulnerable_save_value(value):
    text = normalize_rule_text(value)
    if text in {"", "-"}:
        return ""
    if text.endswith("++"):
        return text
    if text.endswith("+"):
        return f"{text}+"
    return text


def compact_invulnerable_save(save):
    base_save = format_invulnerable_save_value(save.get("save"))
    rules_text = normalize_rule_text(save.get("rules")).lower()
    if base_save and "ranged attacks only" in rules_text:
        return f"R{base_save}"
    if base_save and "melee attacks only" in rules_text:
        return f"M{base_save}"
    if base_save:
        return base_save

    parts = []
    melee_save = format_invulnerable_save_value(save.get("meleeSave"))
    ranged_save = format_invulnerable_save_value(save.get("rangedSave"))
    if melee_save:
        parts.append(f"M{melee_save}")
    if ranged_save:
        parts.append(f"R{ranged_save}")
    return "/".join(parts)


def invulnerable_save_title(save):
    details = []
    if save.get("miniatureName"):
        details.append(save["miniatureName"])
    rules = normalize_rule_text(save.get("rules"))
    if rules not in {"", "-"}:
        details.append(rules)
    return ": ".join(details)


def render_invulnerable_save_cell(save):
    value = compact_invulnerable_save(save) if save else "-"
    title = invulnerable_save_title(save) if save else ""
    title_attr = ""
    if title:
        label = f"Invulnerable save {value}: {title}"
        title_attr = f' title="{escape_attr(title)}" aria-label="{escape_attr(label)}"'
    return f'          <td class="unit-invulnerable-save-cell" data-label="INV"{title_attr}>{escape_html(value)}</td>\n'


def render_statline_table(miniatures, invulnerable_saves=None):
    visible = [miniature for miniature in miniatures if not miniature.get("statlineHidden")]
    if not visible:
        return ""
    invulnerable_saves = invulnerable_saves or []
    global_invulnerable_save = next((save for save in invulnerable_saves if not save.get("miniatureId")), None)
    invulnerable_saves_by_miniature = {
        save["miniatureId"]: save
        for save in invulnerable_saves
        if save.get("miniatureId")
    }
    has_invulnerable_column = bool(invulnerable_saves)
    has_model_column = len(visible) > 1
    model_header_html = render_template("codex_unit_statline_model_header.html") if has_model_column else ""
    invulnerable_header_html = ""
    if has_invulnerable_column:
        invulnerable_header_html = '          <th class="unit-invulnerable-save-cell" scope="col">INV</th>\n'
    rows = []
    for miniature in visible:
        model_cell_html = ""
        if has_model_column:
            model_cell_html = render_template(
                "codex_unit_statline_model_cell.html",
                model_name=escape_html(miniature["name"]),
            )
        invulnerable_cell_html = ""
        if has_invulnerable_column:
            invulnerable_save = invulnerable_saves_by_miniature.get(miniature["id"], global_invulnerable_save)
            invulnerable_cell_html = render_invulnerable_save_cell(invulnerable_save)
        rows.append(render_template(
            "codex_unit_statline_row.html",
            model_cell_html=model_cell_html,
            movement=escape_html(miniature["movement"]),
            toughness=escape_html(miniature["toughness"]),
            save=escape_html(miniature["save"]),
            invulnerable_cell_html=invulnerable_cell_html,
            wounds=escape_html(miniature["wounds"]),
            leadership=escape_html(miniature["leadership"]),
            objective_control=escape_html(miniature["objectiveControl"]),
        ))
    return render_template(
        "codex_unit_statline.html",
        table_class="unit-stat-table-no-model" if not has_model_column else "",
        model_header_html=model_header_html,
        invulnerable_header_html=invulnerable_header_html,
        rows_html="".join(rows),
    )


def render_base_sizes(base_size):
    entries = base_size_entries(base_size)
    if not entries:
        return ""
    items_html = "".join(
        render_template(
            "codex_unit_base_size.html",
            label=escape_html(label),
            value=escape_html(value),
        )
        for label, value in entries
    )
    return render_template(
        "codex_unit_base_sizes.html",
        items_html=items_html,
    )


def render_points_section(point_options, points_steps, paid_wargear):
    if not point_options and not points_steps and not paid_wargear:
        return ""
    rows = []
    for option in point_options:
        rows.append(render_template(
            "codex_unit_points_row.html",
            label=escape_html(option["label"]),
            value=escape_html(format_points(option["points"])),
            tag_html=render_template("codex_unit_points_tag.html", label="models"),
        ))
    for step in points_steps:
        rows.append(render_template(
            "codex_unit_points_row.html",
            label=escape_html(f'{ordinal(step["stepAt"])} copy and later'),
            value=escape_html(format_points(step["stepPoints"], signed=True)),
            tag_html=render_template("codex_unit_points_tag.html", label="repeat"),
        ))
    for item in paid_wargear:
        rows.append(render_template(
            "codex_unit_points_row.html",
            label=escape_html(item["itemName"]),
            value=escape_html(format_points(item["points"], signed=True)),
            tag_html=render_template("codex_unit_points_tag.html", label="wargear"),
        ))
    return render_template(
        "codex_unit_points.html",
        rows_html="".join(rows),
    )


def render_reference_stack(*sections):
    sections_html = "".join(section for section in sections if section)
    if not sections_html:
        return ""
    return render_template(
        "codex_unit_reference_stack.html",
        sections_html=sections_html,
    )


def render_weapon_profiles_table(groups):
    weapon_groups = [group for group in groups if group.get("profiles")]
    if not weapon_groups:
        return ""
    profile_names_by_item = {}
    for group in weapon_groups:
        for profile in group["profiles"]:
            profile_names_by_item.setdefault(profile["itemName"].lower(), set()).add(profile["profileName"].lower())
    multi_profile_items = {
        item_name
        for item_name, profile_names in profile_names_by_item.items()
        if len(profile_names) > 1
    }

    profiles = {"ranged": [], "melee": []}
    seen = set()
    for group in weapon_groups:
        for profile in group["profiles"]:
            profile_key = weapon_profile_key(profile)
            if profile_key in seen:
                continue
            seen.add(profile_key)
            profiles[weapon_bucket(profile)].append({
                "profile": profile,
                "skill": weapon_profile_skill(profile),
                "abilities": profile.get("abilities") or "-",
                "hasModes": profile["itemName"].lower() in multi_profile_items,
            })

    group_html = []
    for bucket, title, skill_label in (("ranged", "Ranged Weapons", "BS"), ("melee", "Melee Weapons", "WS")):
        rows = []
        for item in profiles[bucket]:
            profile = item["profile"]
            rows.append(render_template(
                "codex_unit_weapon_row.html",
                row_class="unit-weapon-row",
                profile_name=escape_html(profile_display_name(profile)),
                mode_marker_html=render_template("codex_unit_weapon_mode_marker.html") if item["hasModes"] else "",
                ability_tags_html=weapon_ability_tags(item["abilities"]),
                range=escape_html(profile["range"]),
                attacks=escape_html(profile["attacks"]),
                skill=escape_html(item["skill"]),
                strength=escape_html(profile["strength"]),
                armour_penetration=escape_html(profile["armourPenetration"]),
                damage=escape_html(profile["damage"]),
                skill_label=skill_label,
            ))
        if rows:
            group_html.append(render_template(
                "codex_unit_weapon_group.html",
                title=escape_html(title),
                skill_label=skill_label,
                rows_html="".join(rows),
            ))
    return render_template(
        "codex_unit_weapons.html",
        groups_html="".join(group_html),
    )


def render_wargear_rules_section(rules):
    if not rules:
        return ""
    rule_html = "".join(
        render_template(
            "codex_unit_wargear_rule.html",
            rules_text=escape_html(rule),
        )
        for rule in rules
    )
    return render_template(
        "codex_unit_wargear_rules.html",
        rules_html=rule_html,
    )


def class_names(*groups):
    result = []
    seen = set()
    for group in groups:
        if not group:
            continue
        items = group if isinstance(group, (list, tuple)) else str(group).split()
        for item in items:
            if item and item not in seen:
                result.append(item)
                seen.add(item)
    return result


def info_card_key(title):
    return normalize_rule_text(title).lower()


def merge_info_cards(cards):
    merged = []
    by_key = {}
    for card in cards:
        if not card:
            continue
        key = info_card_key(card["title"])
        existing = by_key.get(key)
        if existing is None:
            existing = {
                "title": card["title"],
                "classes": list(card["classes"]),
                "tags": list(card.get("tags") or []),
                "bodyParts": list(card.get("bodyParts") or []),
            }
            by_key[key] = existing
            merged.append(existing)
            continue
        existing["classes"] = class_names(existing["classes"], card["classes"])
        for tag in card.get("tags") or []:
            if tag not in existing["tags"]:
                existing["tags"].append(tag)
        existing["bodyParts"].extend(card.get("bodyParts") or [])
    return merged


def render_info_card(card):
    tag_html = "".join(
        render_template("codex_unit_ability_tag.html", label=escape_html(tag))
        for tag in card.get("tags") or []
    )
    if tag_html:
        heading_html = (
            '<div class="unit-card-heading">'
            f'<h3>{escape_html(card["title"])}</h3>{tag_html}'
            '</div>'
        )
    else:
        heading_html = f'<h3>{escape_html(card["title"])}</h3>'
    return (
        f'<section class="{escape_attr(" ".join(card["classes"]))}">'
        f'{heading_html}'
        f'{"".join(card.get("bodyParts") or [])}'
        '</section>'
    )


def text_info_card(title, text, class_name=""):
    if is_empty_rule(text):
        return None
    return {
        "title": title,
        "classes": class_names("rule-card", class_name),
        "tags": [],
        "bodyParts": [render_rich_text(text)],
    }


def render_datasheet_lore(text):
    if is_empty_rule(text):
        return ""
    return render_template(
        "codex_unit_lore.html",
        body_html=render_rich_text(text),
    )


def ability_info_card(ability):
    tags = []
    if ability.get("abilityType"):
        tags.append(ability["abilityType"].title())
    if ability.get("isPsychic"):
        tags.append("Psychic")
    if ability.get("isAura"):
        tags.append("Aura")
    if ability.get("isBondsman"):
        tags.append("Bondsman")
    tag_labels = [" / ".join(tags)] if tags else []

    restriction_html = ""
    if ability.get("restriction"):
        restriction_html = render_template("codex_unit_restriction.html", text=escape_html(ability["restriction"]))

    body_parts = []
    if not is_empty_rule(ability.get("rules")):
        body_parts.append(render_rich_text(ability["rules"]))
    if not is_empty_rule(ability.get("lore")):
        body_parts.append(render_rich_text(ability["lore"]))

    sub_abilities = []
    if ability.get("subAbilities"):
        if ability.get("subAbilityHeader"):
            sub_abilities.append(render_template(
                "codex_unit_sub_ability_header.html",
                title=escape_html(ability["subAbilityHeader"]),
            ))
        for sub_ability in ability["subAbilities"]:
            sub_abilities.append(render_template(
                "codex_unit_sub_ability.html",
                sub_ability_name=escape_html(sub_ability["name"]),
                rules_html=render_rich_text(sub_ability["rules"]),
            ))
    return {
        "title": ability["name"],
        "classes": class_names("rule-card unit-info-card unit-ability-card"),
        "tags": tag_labels,
        "bodyParts": [restriction_html, *body_parts, "".join(sub_abilities)],
    }


def render_invulnerable_saves(saves):
    if not saves:
        return ""
    rows = []
    for save in saves:
        values = []
        if save.get("save"):
            values.append(save["save"])
        if save.get("meleeSave"):
            values.append(f'Melee {save["meleeSave"]}')
        if save.get("rangedSave"):
            values.append(f'Ranged {save["rangedSave"]}')
        label = ", ".join(values) if values else "Invulnerable Save"
        if save.get("miniatureName"):
            label = f'{save["miniatureName"]}: {label}'
        rows.append(render_template(
            "codex_unit_invulnerable_save.html",
            label=escape_html(label),
            rules_html=render_rich_text(save["rules"]) if not is_empty_rule(save.get("rules")) else "",
        ))
    return render_template(
        "codex_unit_invulnerable_saves.html",
        saves_html="".join(rows),
    )


def render_unit_keywords(keywords):
    if not keywords:
        return ""
    return render_template(
        "codex_unit_keywords.html",
        keywords=escape_html(", ".join(keywords)),
    )


def is_faction_ability(ability):
    return str(ability.get("abilityType") or "").lower() == "faction"


def render_unit_keyword_tags(keywords, faction_abilities=None):
    faction_abilities = faction_abilities or []
    if not keywords and not faction_abilities:
        return ""
    keyword_tags_html = "".join(
        render_template(
            "codex_unit_keyword_tag.html",
            label=escape_html(keyword),
        )
        for keyword in keywords
    )
    faction_tags_html = "".join(
        f'<span class="unit-keyword-tag unit-faction-ability-tag">{escape_html(ability["name"])}</span>'
        for ability in faction_abilities
    )
    return render_template(
        "codex_unit_keyword_tags.html",
        tags_html=f"{keyword_tags_html}{faction_tags_html}",
    )


def render_datasheet_page(heretic_builder, faction_id, datasheet_id):
    faction = faction_by_id(heretic_builder, faction_id)
    detail = datasheet_detail(heretic_builder, faction["id"], datasheet_id)
    datasheet = detail["datasheet"]
    image = find_unit_image(datasheet["name"], datasheet["id"])
    points_html = render_points_section(
        detail["pointOptions"],
        detail["pointsSteps"],
        detail["paidWargear"],
    )
    base_sizes_html = render_base_sizes(datasheet.get("baseSize"))
    statline_html = render_statline_table(detail["miniatures"], detail["invulnerableSaves"])
    weapons_html = render_weapon_profiles_table(detail["wargearGroups"])

    faction_abilities = [ability for ability in detail["abilities"] if is_faction_ability(ability)]
    datasheet_abilities = [ability for ability in detail["abilities"] if not is_faction_ability(ability)]

    info_cards = []
    info_cards.extend(ability_info_card(ability) for ability in datasheet_abilities)
    info_cards.extend(
        text_info_card(rule["name"], rule["rules"], "unit-info-card unit-rule-card")
        for rule in detail["rules"]
    )
    info_cards.extend(
        text_info_card(
            damage["name"] if not damage.get("damagedAt") else f'{damage["name"]}: {damage["damagedAt"]} wounds',
            damage["rules"],
            "unit-info-card unit-damage-card",
        )
        for damage in detail["damageRows"]
    )
    info_sections = [render_info_card(card) for card in merge_info_cards(info_cards)]
    content_html = render_template(
        "codex_unit_detail.html",
        keyword_tags_html=render_unit_keyword_tags(detail["keywords"], faction_abilities),
        statline_html=statline_html,
        points_html=render_reference_stack(points_html, base_sizes_html),
        weapons_html=weapons_html,
        info_html="".join(section for section in info_sections if section),
        wargear_rules_html=render_wargear_rules_section(detail["wargearRules"]),
    )
    content_html += render_faq_update_sections(
        faqs_for_entity(heretic_builder, "datasheetId", datasheet_id),
        errata_title="",
        faq_title="",
    )
    content_html += render_datasheet_lore(datasheet.get("lore"))

    return render_codex_content_page(
        title=datasheet["name"],
        window_title=f"{datasheet['name']}",
        task_title=f"{faction['name']} / {datasheet['name']}",
        page_class="faction-detail-page unit-detail-page",
        content_html=content_html,
        back_href=f"{faction_href(faction['id'])}/datasheets",
        back_label=f"Back to {faction['name']} Data Sheets",
        hero_image_url=unit_image_url(image) if image else None,
    )
