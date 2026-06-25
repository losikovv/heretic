import re

from roster_builder_assets import FACTION_IMAGES_BY_ID, FACTION_IMAGES_BY_NAME, UNIT_IMAGES_BY_ID, UNIT_IMAGES_BY_NAME
from roster_builder_codex_rich_text import (
    core_rule_href,
    escape_attr,
    escape_html,
    normalize_rule_reference_code,
    normalize_rule_text,
    render_rich_text,
    render_rule_component,
)
from roster_builder_templates import render_template
from roster_builder_utils import dict_row


def faction_image_url(image):
    return f"/assets/faction-images/{escape_attr(image['filename'])}"


def unit_image_url(image):
    return f"/assets/unit-images/{escape_attr(image['filename'])}"


def find_faction_image(name, faction_id=None):
    if faction_id and faction_id in FACTION_IMAGES_BY_ID:
        return FACTION_IMAGES_BY_ID[faction_id]
    return FACTION_IMAGES_BY_NAME.get(str(name).lower())


def find_unit_image(name, datasheet_id=None):
    if datasheet_id and datasheet_id in UNIT_IMAGES_BY_ID:
        return UNIT_IMAGES_BY_ID[datasheet_id]
    return UNIT_IMAGES_BY_NAME.get(str(name).lower())


def faction_href(faction_id):
    return f"/codex/faction/{escape_attr(faction_id)}"


def datasheet_href(faction_id, datasheet_id):
    return f"/codex/faction/{faction_id}/datasheet/{datasheet_id}"


def detachment_href(faction_id, detachment_id):
    return f"/codex/faction/{faction_id}/detachment/{detachment_id}"


CORE_RULES_PUBLICATION_ID = "4cdf7a87-0914-49e8-b5df-b9f8be4d13c6"
FAQ_RELATION_COLUMNS = {
    "datasheetId",
    "armyRuleId",
    "detachmentId",
    "enhancementId",
    "stratagemId",
    "ruleContainerId",
}
CORE_RULES_INFERRED_FAQ_REFERENCES = {
    "5928ab6e-7113-42c8-9085-4291faddae09": ("06.03", "24.15"),
    "c2df3e97-f21e-4fc9-943e-37072c08c10e": ("18.02", "18.03", "18.04"),
    "4978f15f-2b4a-4805-aacd-db9b5cad71bd": ("06.03", "09.07"),
}


def normalize_rule_section_code(value):
    match = re.fullmatch(r"\s*(\d{1,2})(?:\..*)?\s*", str(value or ""))
    if not match:
        return ""
    return f"{int(match.group(1)):02d}"


def core_rule_section_href(section):
    code = normalize_rule_section_code(section.get("name", ""))
    return f"/codex/core-rules/section/{code}" if code else "/codex/core-rules/rules"


def title_bar_context(hero_image=None, hero_image_url=None):
    if not hero_image_url and hero_image:
        hero_image_url = faction_image_url(hero_image)
    if not hero_image_url:
        return {"title_bar_class": "", "title_bar_style_attr": ""}
    return {
        "title_bar_class": "faction-hero-title",
        "title_bar_style_attr": f' style="--faction-hero-image: url(\'{hero_image_url}\');"',
    }


def render_window_title(value):
    return "<br>".join(escape_html(line) for line in str(value).splitlines())


def render_launcher(button):
    href_attr = f' data-href="{escape_attr(button["href"])}"' if button.get("href") else ""
    classes = ["launcher"]
    tag_html = ""
    image_html = ""

    if button.get("tag"):
        tag_html = render_template("codex_launcher_tag.html", tag=escape_html(button["tag"]))

    image = button.get("image")
    if image:
        classes.append("has-faction-image")
        image_html = render_template(
            "codex_launcher_image.html",
            src=faction_image_url(image),
        )

    return render_template(
        "codex_launcher.html",
        class_attr=escape_attr(" ".join(classes)),
        label_attr=escape_attr(button["label"]),
        route_attr=escape_attr(button["route"]),
        href_attr=href_attr,
        image_html=image_html,
        label=escape_html(button["label"]),
        tag_html=tag_html,
    )


def render_codex_page(
    title,
    window_title,
    task_title,
    page_class,
    grid_label,
    buttons,
    back_href,
    back_label,
    hero_image=None,
    hero_image_url=None,
):
    if len(buttons) > 5:
        page_class = f"{page_class} many-buttons-page"

    return render_template(
        "codex.html",
        **title_bar_context(hero_image, hero_image_url),
        document_title=escape_html(f"{title} - HereticTools"),
        page_class=escape_attr(page_class),
        title=escape_attr(title),
        window_title=render_window_title(window_title),
        grid_label=escape_attr(grid_label),
        buttons_html="\n".join(render_launcher(button) for button in buttons),
        back_href=escape_attr(back_href),
        back_label=escape_attr(back_label),
        task_title=escape_html(task_title),
    )


def render_codex_content_page(
    title,
    window_title,
    task_title,
    page_class,
    content_html,
    back_href,
    back_label,
    hero_image=None,
    hero_image_url=None,
):
    return render_template(
        "codex_content.html",
        **title_bar_context(hero_image, hero_image_url),
        document_title=escape_html(f"{title} - HereticTools"),
        page_class=escape_attr(page_class),
        title=escape_attr(title),
        window_title=render_window_title(window_title),
        content_html=content_html,
        back_href=escape_attr(back_href),
        back_label=escape_attr(back_label),
        task_title=escape_html(task_title),
    )


def render_codex_root_page():
    return render_codex_page(
        title="Codex",
        window_title="Codex",
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


def render_core_rules_page():
    return render_codex_page(
        title="Core Rules",
        window_title="CoreRules",
        task_title="Core Rules",
        page_class="core-rules-page",
        grid_label="Core Rules sections",
        back_href="/codex",
        back_label="Back to Codex",
        buttons=[
            {"label": "Rules", "tag": "Reference", "route": "rules", "href": "/codex/core-rules/rules"},
            {"label": "Stratagems", "tag": "Tactics", "route": "stratagems", "href": "/codex/core-rules/stratagems"},
            {"label": "FAQ", "tag": "Updates", "route": "faq", "href": "/codex/core-rules/faq"},
        ],
    )


def core_rule_sections(heretic_builder):
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select rs.id, rs.name, rs.displayOrder,
                   count(rc.id) as containerCount
            from rule_section rs
            left join rule_container rc on rc.ruleSectionId = rs.id
            where rs.publicationId = ?
            group by rs.id
            order by rs.displayOrder, rs.name
            """,
            [CORE_RULES_PUBLICATION_ID],
        ).fetchall()
    return [dict_row(row) for row in rows]


def core_rule_section_by_code(heretic_builder, code):
    normalized = normalize_rule_section_code(code)
    if not normalized:
        raise ValueError("Rule section not found")
    with heretic_builder.connect(readonly=True) as conn:
        row = conn.execute(
            """
            select id, name, displayOrder
            from rule_section
            where publicationId = ?
              and name like ?
            order by displayOrder
            limit 1
            """,
            [CORE_RULES_PUBLICATION_ID, f"{normalized}.%"],
        ).fetchone()
    if not row:
        raise ValueError("Rule section not found")
    return dict_row(row)


def core_rule_containers_for_section(heretic_builder, section_id):
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select rc.id, rc.title, rc.subtitle, rc.containerType, rc.displayOrder,
                   s.cpCost, s.category,
                   count(fc.faqId) as faqCount
            from rule_container rc
            left join stratagem s on s.id = rc.stratagemId
            left join faq_config fc on fc.ruleContainerId = rc.id
            where rc.ruleSectionId = ?
            group by rc.id
            order by rc.displayOrder, rc.subtitle, rc.title
            """,
            [section_id],
        ).fetchall()
    return [dict_row(row) for row in rows]


def core_stratagem_containers(heretic_builder):
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select rc.id, rc.title, rc.subtitle, rc.containerType, rc.displayOrder,
                   s.cpCost, s.category,
                   count(fc.faqId) as faqCount
            from rule_container rc
            join rule_section rs on rs.id = rc.ruleSectionId
            left join stratagem s on s.id = rc.stratagemId
            left join faq_config fc on fc.ruleContainerId = rc.id
            where rs.publicationId = ?
              and rc.containerType = 'stratagem'
            group by rc.id
            order by rc.displayOrder, rc.subtitle, rc.title
            """,
            [CORE_RULES_PUBLICATION_ID],
        ).fetchall()
    return [dict_row(row) for row in rows]


def core_rule_faqs(heretic_builder):
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select id, errataHeader, errataText, question, answer, displayOrder
            from faq
            where publicationId = ?
            order by displayOrder, id
            """,
            [CORE_RULES_PUBLICATION_ID],
        ).fetchall()
    return [dict_row(row) for row in rows]


def render_rule_container_item(container):
    meta = [container["subtitle"], container["containerType"].replace("behaviourType", "movement")]
    if container.get("cpCost"):
        meta.append(f'{container["cpCost"]} CP')
    if container.get("category"):
        meta.append(container["category"])
    if container.get("faqCount"):
        meta.append(f'{container["faqCount"]} FAQ')
    return render_list_item(
        container["title"],
        " / ".join(item for item in meta if item),
        href=core_rule_href(container["subtitle"]),
    )


def render_core_rules_rules_page(heretic_builder):
    sections = core_rule_sections(heretic_builder)
    items_html = "".join(
        render_list_item(
            section["name"],
            f'{section["containerCount"]} rules',
            href=core_rule_section_href(section),
        )
        for section in sections
    )
    content_html = f'<div class="list-grid core-rules-list-grid">{items_html}</div>'
    return render_codex_content_page(
        title="Core Rules",
        window_title="Core Rules",
        task_title="Core Rules / Rules",
        page_class="faction-detail-page core-rules-list-page",
        content_html=content_html,
        back_href="/codex/core-rules",
        back_label="Back to Core Rules",
    )


def render_core_rules_section_page(heretic_builder, section_code):
    section = core_rule_section_by_code(heretic_builder, section_code)
    containers = core_rule_containers_for_section(heretic_builder, section["id"])
    items_html = "".join(render_rule_container_item(container) for container in containers)
    content_html = f'<div class="list-grid core-rules-list-grid">{items_html}</div>'
    return render_codex_content_page(
        title=section["name"],
        window_title=section["name"],
        task_title=f'Core Rules / {section["name"]}',
        page_class="faction-detail-page core-rules-list-page",
        content_html=content_html,
        back_href="/codex/core-rules/rules",
        back_label="Back to Core Rules",
    )


def render_core_stratagems_page(heretic_builder):
    stratagems = core_stratagem_containers(heretic_builder)
    items_html = "".join(render_rule_container_item(stratagem) for stratagem in stratagems)
    content_html = f'<div class="list-grid core-rules-list-grid">{items_html}</div>'
    return render_codex_content_page(
        title="Core Stratagems",
        window_title="Core Stratagems",
        task_title="Core Rules / Stratagems",
        page_class="faction-detail-page core-rules-list-page",
        content_html=content_html,
        back_href="/codex/core-rules",
        back_label="Back to Core Rules",
    )


def has_errata(faq):
    return bool(normalize_rule_text(faq.get("errataHeader")) or normalize_rule_text(faq.get("errataText")))


def has_faq(faq):
    return bool(normalize_rule_text(faq.get("question")) or normalize_rule_text(faq.get("answer")))


def render_errata_card(faq, current_rule_reference=None):
    pieces = []
    if normalize_rule_text(faq.get("errataHeader")):
        pieces.append(f'<h3>{escape_html(normalize_rule_text(faq["errataHeader"]))}</h3>')
    if normalize_rule_text(faq.get("errataText")):
        pieces.append(render_rich_text(faq["errataText"], current_rule_reference))
    if not pieces:
        return ""
    return f'<section class="rule-card faq-card errata-card"><div class="faq-card-kicker">Errata</div>{"".join(pieces)}</section>'


def render_faq_card(faq, current_rule_reference=None):
    pieces = []
    if normalize_rule_text(faq.get("question")):
        pieces.append(f'<div class="faq-question">{render_rich_text(faq["question"], current_rule_reference)}</div>')
    if normalize_rule_text(faq.get("answer")):
        pieces.append(f'<div class="faq-answer">{render_rich_text(faq["answer"], current_rule_reference)}</div>')
    if not pieces:
        return ""
    return f'<section class="rule-card faq-card question-card"><div class="faq-card-kicker">FAQ</div>{"".join(pieces)}</section>'


def render_faq_section(title, faqs, current_rule_reference=None):
    cards = "".join(render_faq_card(faq, current_rule_reference) for faq in faqs if has_faq(faq))
    if not cards:
        return ""
    title_html = f'<h2 class="detachment-section-title">{escape_html(title)}</h2>' if title else ""
    return (
        f'<section class="codex-content faq-section">'
        f'{title_html}'
        f'{cards}'
        f'</section>'
    )


def render_errata_section(title, faqs, current_rule_reference=None):
    cards = "".join(render_errata_card(faq, current_rule_reference) for faq in faqs if has_errata(faq))
    if not cards:
        return ""
    title_html = f'<h2 class="detachment-section-title">{escape_html(title)}</h2>' if title else ""
    return (
        f'<section class="codex-content faq-section errata-section">'
        f'{title_html}'
        f'{cards}'
        f'</section>'
    )


def render_faq_update_sections(faqs, errata_title="Errata", faq_title="FAQ", current_rule_reference=None):
    return (
        render_errata_section(errata_title, faqs, current_rule_reference)
        + render_faq_section(faq_title, faqs, current_rule_reference)
    )


def faqs_for_entity(heretic_builder, relation_column, relation_id):
    if relation_column not in FAQ_RELATION_COLUMNS:
        raise ValueError("Unsupported FAQ relation")
    if not relation_id:
        return []
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            f"""
            select distinct f.id, f.errataHeader, f.errataText, f.question, f.answer, f.displayOrder
            from faq_config fc
            join faq f on f.id = fc.faqId
            where fc.{relation_column} = ?
            order by f.displayOrder, f.id
            """,
            [relation_id],
        ).fetchall()
    return [dict_row(row) for row in rows]


def attach_faqs(heretic_builder, items, relation_column):
    for item in items:
        item["faqs"] = faqs_for_entity(heretic_builder, relation_column, item["id"])
    return items


def rule_reference_codes_from_faq(faq):
    text = " ".join(
        str(faq.get(key) or "")
        for key in ("errataHeader", "errataText", "question", "answer")
    )
    return {
        normalize_rule_reference_code(match.group(1))
        for match in re.finditer(r"\((\d{1,2}(?:\.\d{1,2})?)\)", text)
        if normalize_rule_reference_code(match.group(1))
    }


def related_faqs_for_core_rule(conn, rule_container_id, reference):
    normalized = normalize_rule_reference_code(reference)
    faq_by_id = {}
    explicit_rows = conn.execute(
        """
        select f.id, f.errataHeader, f.errataText, f.question, f.answer, f.displayOrder
        from faq_config fc
        join faq f on f.id = fc.faqId
        where fc.ruleContainerId = ?
        """,
        [rule_container_id],
    ).fetchall()
    for row in explicit_rows:
        faq = dict_row(row)
        faq_by_id[faq["id"]] = faq

    core_rows = conn.execute(
        """
        select id, errataHeader, errataText, question, answer, displayOrder
        from faq
        where publicationId = ?
        """,
        [CORE_RULES_PUBLICATION_ID],
    ).fetchall()
    for row in core_rows:
        faq = dict_row(row)
        inferred_codes = set(CORE_RULES_INFERRED_FAQ_REFERENCES.get(faq["id"], ()))
        inferred_codes.update(rule_reference_codes_from_faq(faq))
        if normalized in inferred_codes:
            faq_by_id[faq["id"]] = faq

    return sorted(faq_by_id.values(), key=lambda faq: (faq["displayOrder"], faq["id"]))


def render_core_faq_page(heretic_builder):
    faqs = core_rule_faqs(heretic_builder)
    content_html = render_faq_update_sections(faqs) or '<div class="empty-state">No FAQ or errata found.</div>'
    return render_codex_content_page(
        title="Core Rules FAQ",
        window_title="Core Rules\nFAQ",
        task_title="Core Rules / FAQ",
        page_class="faction-detail-page core-rules-faq-page",
        content_html=content_html,
        back_href="/codex/core-rules",
        back_label="Back to Core Rules",
    )


def core_rule_by_reference(heretic_builder, reference):
    normalized = normalize_rule_reference_code(reference)
    if not normalized:
        raise ValueError("Rule reference not found")
    with heretic_builder.connect(readonly=True) as conn:
        rule = conn.execute(
            """
            select rc.id, rc.title, rc.subtitle, rc.containerType, rc.behaviourTypeId, rc.stratagemId
            from rule_container rc
            join rule_section rs on rs.id = rc.ruleSectionId
            where rc.subtitle = ?
              and rs.publicationId = ?
            """,
            [normalized, CORE_RULES_PUBLICATION_ID],
        ).fetchone()
        if not rule:
            raise ValueError("Rule reference not found")
        result = dict_row(rule)
        result["components"] = [
            dict_row(row)
            for row in conn.execute(
                """
                select type, title, textContent, trigger, effect, imageUrl, altText, displayOrder
                from rule_container_component
                where ruleContainerId = ?
                order by displayOrder
                """,
                [result["id"]],
            )
        ]
        result["behaviourType"] = None
        result["stratagem"] = None
        result["faqs"] = related_faqs_for_core_rule(conn, result["id"], normalized)
        if result.get("stratagemId"):
            stratagem = conn.execute(
                """
                select id, name, lore, whenRules, targetRules, effectRules, restrictionRules,
                       cpCost, category, secondaryEffectAdditionalCPCost,
                       secondaryEffectIsMutuallyExclusive, secondaryEffect
                from stratagem
                where id = ?
                """,
                [result["stratagemId"]],
            ).fetchone()
            if stratagem:
                result["stratagem"] = dict_row(stratagem)
        if result.get("behaviourTypeId"):
            behaviour = conn.execute(
                """
                select *
                from behaviour_type
                where id = ?
                """,
                [result["behaviourTypeId"]],
            ).fetchone()
            if behaviour:
                result["behaviourType"] = dict_row(behaviour)
    return result


def render_behaviour_type(behaviour, current_rule_reference=None):
    fields = (
        ("eligibleIf", "Eligible If"),
        ("effect", "Effect"),
        ("maximumDistance", "Maximum Distance"),
        ("setupDistance", "Set-up Distance"),
        ("beforeMoving", "Before Moving"),
        ("whileMoving", "While Moving"),
        ("afterMoving", "After Moving"),
        ("beforeFighting", "Before Fighting"),
        ("whileFighting", "While Fighting"),
        ("afterFighting", "After Fighting"),
        ("beforeShooting", "Before Shooting"),
        ("whileShooting", "While Shooting"),
        ("afterShooting", "After Shooting"),
    )
    cards = []
    for key, label in fields:
        value = behaviour.get(key)
        if not normalize_rule_text(value):
            continue
        cards.append(
            f'<section class="rule-card core-rule-field-card">'
            f'<h3>{escape_html(label)}</h3>'
            f'{render_rich_text(value, current_rule_reference)}'
            f'</section>'
        )
    return "".join(cards)


def render_core_rule_page(heretic_builder, reference):
    rule = core_rule_by_reference(heretic_builder, reference)
    current_rule_reference = rule["subtitle"]
    heading = f'{rule["subtitle"]} {rule["title"]}' if rule.get("subtitle") else rule["title"]
    sections = [
        f'<section class="rule-card core-rule-heading-card">'
        f'<div class="core-rule-number">{escape_html(rule["subtitle"])}</div>'
        f'<h2>{escape_html(rule["title"])}</h2>'
        f'</section>'
    ]
    sections.extend(render_rule_component(component, current_rule_reference) for component in rule["components"])
    if rule.get("stratagem"):
        sections.append(render_stratagem_card(rule["stratagem"], current_rule_reference))
    if rule.get("behaviourType"):
        sections.append(render_behaviour_type(rule["behaviourType"], current_rule_reference))
    faq_html = render_faq_update_sections(
        rule.get("faqs") or [],
        errata_title="",
        faq_title="",
        current_rule_reference=current_rule_reference,
    )
    if faq_html:
        sections.append(faq_html)
    if len([section for section in sections if section]) == 1:
        sections.append('<section class="rule-card"><p>No rule text found.</p></section>')
    content_html = '<article class="codex-content core-rule-content">' + "".join(section for section in sections if section) + "</article>"
    return render_codex_content_page(
        title=heading,
        window_title=heading,
        task_title=f"Core Rules / {heading}",
        page_class="core-rule-page",
        content_html=content_html,
        back_href="/codex/core-rules",
        back_label="Back to Core Rules",
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

ADEPTUS_ASTARTES_FACTION_ID = "01623188-9470-4441-96b0-e06eb2572bb5"


FACTION_GROUPS = {
    "imperium": {
        "title": "Imperium",
        "window_title": "Imperium",
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
        "window_title": "Chaos",
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
        "window_title": "Xenos",
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
            "href": faction_href(faction["id"]),
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
        window_title="AdeptusAstartes",
        task_title="Adeptus Astartes",
        page_class="faction-list-page",
        grid_label="Adeptus Astartes factions",
        back_href="/codex/imperium",
        back_label="Back to Imperium",
        buttons=[
            {
                "label": faction["name"],
                "route": faction["id"],
                "href": faction_href(faction["id"]),
                "image": find_faction_image(faction["name"], faction["id"]),
            }
            for faction in group_factions
        ],
    )


def faction_back_href(faction_id):
    if faction_id in ADEPTUS_ASTARTES_FACTION_IDS:
        return "/codex/imperium/adeptus-astartes"
    for group_key, group in FACTION_GROUPS.items():
        if faction_id in group["ids"]:
            return f"/codex/{group_key}"
    return "/codex"


def faction_by_id(heretic_builder, faction_id):
    with heretic_builder.connect(readonly=True) as conn:
        row = conn.execute(
            """
            select id, name, lore
            from faction_keyword
            where id = ?
              and excludedFromArmyBuilder = 0
            """,
            [faction_id],
        ).fetchone()
    if not row:
        raise ValueError("Faction not found")
    return dict_row(row)


def faction_hero_image(faction):
    return find_faction_image(faction["name"], faction["id"])


def render_faction_page(heretic_builder, faction_id):
    faction = faction_by_id(heretic_builder, faction_id)
    base_href = faction_href(faction["id"])
    return render_codex_page(
        title=faction["name"],
        window_title=f"{faction['name']}",
        task_title=faction["name"],
        page_class="faction-home-page",
        grid_label=f"{faction['name']} sections",
        back_href=faction_back_href(faction["id"]),
        back_label="Back to Factions",
        hero_image=faction_hero_image(faction),
        buttons=[
            {"label": "Army Rule", "tag": "Reference", "route": "army-rule", "href": f"{base_href}/army-rule"},
            {"label": "Detachments", "tag": "Forces", "route": "detachments", "href": f"{base_href}/detachments"},
            {"label": "Data Sheets", "tag": "Units", "route": "datasheets", "href": f"{base_href}/datasheets"},
        ],
    )


def rule_components_for(conn, relation_column, relation_id):
    if relation_column not in {"armyRuleId", "detachmentRuleId"}:
        raise ValueError("Unsupported rule component relation")
    return [
        dict_row(row)
        for row in conn.execute(
            f"""
                select type, title, textContent, trigger, effect, imageUrl, altText, displayOrder
                from rule_container_component
                where {relation_column} = ?
                order by displayOrder
            """,
            [relation_id],
        )
    ]


def army_rules_for_faction(heretic_builder, faction_id):
    with heretic_builder.connect(readonly=True) as conn:
        rules = [
            dict_row(row)
            for row in conn.execute(
                """
                select ar.id, ar.name
                from army_rule ar
                join army_rule_faction_keyword arfk on arfk.armyRuleId = ar.id
                where arfk.factionKeywordId = ?
                  and ar.hiddenFromCommandBunker = 0
                order by ar.displayOrder, lower(ar.name)
                """,
                [faction_id],
            )
        ]
        for rule in rules:
            rule["components"] = rule_components_for(conn, "armyRuleId", rule["id"])
            rule["faqs"] = [
                dict_row(row)
                for row in conn.execute(
                    """
                    select distinct f.id, f.errataHeader, f.errataText, f.question, f.answer, f.displayOrder
                    from faq_config fc
                    join faq f on f.id = fc.faqId
                    where fc.armyRuleId = ?
                    order by f.displayOrder, f.id
                    """,
                    [rule["id"]],
                )
            ]
    return rules


def render_faction_army_rule_page(heretic_builder, faction_id):
    faction = faction_by_id(heretic_builder, faction_id)
    rules = army_rules_for_faction(heretic_builder, faction["id"])
    if not rules:
        content_html = '<div class="empty-state">No army rule found.</div>'
    else:
        rule_html = []
        for rule in rules:
            components = "".join(render_rule_component(component) for component in rule["components"])
            rule_html.append(
                f'<article class="codex-content">'
                f'<section class="rule-card"><h2>{escape_html(rule["name"])}</h2></section>'
                f'{components}'
                f'{render_faq_update_sections(rule.get("faqs") or [], errata_title="", faq_title="")}'
                f'</article>'
            )
        content_html = '<div class="codex-content">' + "".join(rule_html) + "</div>"
    return render_codex_content_page(
        title=f"{faction['name']} Army Rule",
        window_title=f"{faction['name']}\nRule",
        task_title=f"{faction['name']} / Army Rule",
        page_class="faction-detail-page",
        content_html=content_html,
        back_href=faction_href(faction["id"]),
        back_label=f"Back to {faction['name']}",
        hero_image=faction_hero_image(faction),
    )


def render_list_item(title, meta, href=None, extra_class=""):
    meta_html = f'<div class="list-item-meta">{escape_html(meta)}</div>' if meta else ""
    classes = " ".join(item for item in ("list-item", extra_class) if item)
    if href:
        return (
            f'<a class="{escape_attr(classes)}" href="{escape_attr(href)}">'
            f'<div class="list-item-title">{escape_html(title)}</div>'
            f'{meta_html}'
            '</a>'
        )
    return (
        f'<div class="{escape_attr(classes)}">'
        f'<div class="list-item-title">{escape_html(title)}</div>'
        f'{meta_html}'
        '</div>'
    )


def detachment_meta(detachment):
    meta = []
    if detachment.get("detachmentPointsCost") is not None:
        meta.append(f'{detachment["detachmentPointsCost"]} RP')
    if detachment.get("isCombatPatrol"):
        meta.append("Combat Patrol")
    return " / ".join(meta)


def render_datasheet_item(datasheet, faction_id):
    image = find_unit_image(datasheet["name"], datasheet.get("id"))
    meta = f'{datasheet["points"]} pts' if datasheet.get("points") is not None else ""
    href = datasheet_href(faction_id, datasheet["id"])
    if not image:
        return render_list_item(datasheet["name"], meta, href=href)
    return (
        f'<a class="list-item datasheet-tile has-unit-image" href="{escape_attr(href)}">'
        f'<span class="unit-art-frame" aria-hidden="true"><img class="unit-art" src="{unit_image_url(image)}" alt=""></span>'
        '<span class="datasheet-tile-text">'
        f'<span class="list-item-title">{escape_html(datasheet["name"])}</span>'
        f'<span class="list-item-meta">{escape_html(meta)}</span>'
        '</span>'
        '</a>'
    )


DATASHEET_GROUPS = (
    ("Epic Heroes", {"Epic Hero"}),
    ("Leaders", {"Character"}),
    ("Supports", {"Character"}),
    ("Characters", {"Character"}),
    ("Battleline", {"Battleline"}),
    ("Infantry", {"Infantry"}),
    ("Transports", {"Dedicated Transport", "Transport"}),
    ("Vehicles", {"Vehicle"}),
    ("Monsters", {"Monster"}),
    ("Mounted", {"Mounted"}),
    ("Beasts", {"Beast"}),
    ("Swarms", {"Swarm", "Endless Multitude"}),
    ("Aircraft", {"Aircraft"}),
    ("Fortifications", {"Fortification", "Fortifications"}),
    ("Titanic", {"Titanic"}),
    ("Allied Units", set()),
    ("Other Datasheets", set()),
)

DATASHEET_GROUP_ORDER = [name for name, _ in DATASHEET_GROUPS]
SPECIAL_DATASHEET_KEYWORDS = {
    "Aircraft",
    "Dedicated Transport",
    "Endless Multitude",
    "Fortification",
    "Fortifications",
    "Swarm",
    "Titanic",
    "Transport",
}


def datasheet_keywords(heretic_builder, datasheet_ids):
    if not datasheet_ids:
        return {}
    placeholders = ",".join("?" for _ in datasheet_ids)
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            f"""
            select m.datasheetId, k.name
            from miniature m
            join miniature_keyword mk on mk.miniatureId = m.id
            join keyword k on k.id = mk.keywordId
            where m.datasheetId in ({placeholders})
            """,
            datasheet_ids,
        )
        result = {datasheet_id: set() for datasheet_id in datasheet_ids}
        for row in rows:
            result.setdefault(row["datasheetId"], set()).add(row["name"])
    return result


def datasheet_attachment_types(heretic_builder, datasheet_ids):
    if not datasheet_ids:
        return {}
    placeholders = ",".join("?" for _ in datasheet_ids)
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            f"""
            select datasheetId, bodyguardType
            from datasheet_bodyguard_group
            where datasheetId in ({placeholders})
            """,
            datasheet_ids,
        )
        result = {datasheet_id: set() for datasheet_id in datasheet_ids}
        for row in rows:
            result.setdefault(row["datasheetId"], set()).add(row["bodyguardType"])
    return result


def allied_datasheets_for_faction(heretic_builder, faction_id):
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select distinct d.id, d.name,
                   coalesce((
                     select uc.points
                     from unit_composition uc
                     where uc.datasheetId = d.id
                     order by uc.isDefault desc, uc.displayOrder
                     limit 1
                   ), 0) as points
            from faction_keyword_allied_faction fkaf
            join allied_faction_datasheet afd on afd.alliedFactionId = fkaf.alliedFactionId
            join datasheet d on d.id = afd.datasheetId
            where fkaf.factionKeywordId = ?
            order by lower(d.name)
            limit 250
            """,
            [faction_id],
        ).fetchall()
    return [dict_row(row) for row in rows]


def astartes_codex_datasheets(heretic_builder, faction_id):
    params = [faction_id]
    chapter_filter = ""
    if faction_id == ADEPTUS_ASTARTES_FACTION_ID:
        chapter_ids = sorted(ADEPTUS_ASTARTES_FACTION_IDS - {ADEPTUS_ASTARTES_FACTION_ID})
        placeholders = ",".join("?" for _ in chapter_ids)
        chapter_filter = f"""
          and not exists (
            select 1
            from datasheet_faction_keyword chapter_dfk
            where chapter_dfk.datasheetId = d.id
              and chapter_dfk.factionKeywordId in ({placeholders})
          )
        """
        params.extend(chapter_ids)

    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            f"""
            select distinct d.id, d.name,
                   coalesce((
                     select uc.points
                     from unit_composition uc
                     where uc.datasheetId = d.id
                     order by uc.isDefault desc, uc.displayOrder
                     limit 1
                   ), 0) as points
            from datasheet d
            join datasheet_faction_keyword dfk
              on dfk.datasheetId = d.id
             and dfk.factionKeywordId = ?
            where not exists (
                select 1
                from faction_keyword_excluded_datasheet fked
                where fked.datasheetId = d.id
                  and fked.factionKeywordId = ?
              )
              {chapter_filter}
            order by lower(d.name)
            limit 250
            """,
            [faction_id, *params],
        ).fetchall()
    return [dict_row(row) for row in rows]


def codex_datasheets_for_faction(heretic_builder, faction_id):
    if faction_id in ADEPTUS_ASTARTES_FACTION_IDS:
        return astartes_codex_datasheets(heretic_builder, faction_id)
    return heretic_builder.datasheets(faction_id).get("datasheets", [])


def datasheet_group_name(datasheet, keywords, attachment_types):
    if datasheet.get("allyType") == "allied":
        return "Allied Units"
    if "Epic Hero" in keywords:
        return "Epic Heroes"
    if "Character" in keywords:
        if "leader" in attachment_types:
            return "Leaders"
        if "support" in attachment_types:
            return "Supports"
        return "Characters"
    if "Battleline" in keywords:
        return "Battleline"
    if keywords.intersection({"Swarm", "Endless Multitude"}):
        return "Swarms"
    if "Aircraft" in keywords:
        return "Aircraft"
    if keywords.intersection({"Fortification", "Fortifications"}):
        return "Fortifications"
    if "Titanic" in keywords:
        return "Titanic"
    if keywords.intersection({"Dedicated Transport", "Transport"}):
        return "Transports"
    if "Infantry" in keywords:
        return "Infantry"
    if "Vehicle" in keywords and not keywords.intersection(SPECIAL_DATASHEET_KEYWORDS):
        return "Vehicles"
    if "Monster" in keywords and not keywords.intersection(SPECIAL_DATASHEET_KEYWORDS):
        return "Monsters"
    if "Mounted" in keywords:
        return "Mounted"
    if "Beast" in keywords:
        return "Beasts"
    if "Vehicle" in keywords:
        return "Vehicles"
    if "Monster" in keywords:
        return "Monsters"
    return "Other Datasheets"


def render_datasheet_groups(heretic_builder, native_datasheets, allied_datasheets, faction_id):
    datasheets = [
        {**datasheet, "allyType": "native"}
        for datasheet in native_datasheets
    ] + [
        {**datasheet, "allyType": "allied"}
        for datasheet in allied_datasheets
    ]
    keyword_map = datasheet_keywords(heretic_builder, [datasheet["id"] for datasheet in datasheets])
    attachment_type_map = datasheet_attachment_types(heretic_builder, [datasheet["id"] for datasheet in datasheets])
    grouped = {name: [] for name in DATASHEET_GROUP_ORDER}
    for datasheet in datasheets:
        keywords = keyword_map.get(datasheet["id"], set())
        attachment_types = attachment_type_map.get(datasheet["id"], set())
        grouped[datasheet_group_name(datasheet, keywords, attachment_types)].append(datasheet)

    sections = []
    for group_name in DATASHEET_GROUP_ORDER:
        group_datasheets = grouped[group_name]
        if not group_datasheets:
            continue
        items_html = "".join(
            render_datasheet_item(datasheet, faction_id)
            for datasheet in sorted(group_datasheets, key=lambda item: item["name"].lower())
        )
        sections.append(
            f'<section class="datasheet-group">'
            f'<h2 class="datasheet-group-title">{escape_html(group_name)}</h2>'
            f'<div class="list-grid">{items_html}</div>'
            f'</section>'
        )
    return '<div class="codex-content">' + "".join(sections) + "</div>"


def detachment_by_id_for_faction(heretic_builder, faction_id, detachment_id):
    with heretic_builder.connect(readonly=True) as conn:
        row = conn.execute(
            """
            select d.id, d.name, d.bannerImage, d.rowImage, d.isCombatPatrol,
                   coalesce(dfdpc.detachmentPointsCost, d.detachmentPointsCost) as detachmentPointsCost
            from detachment d
            join detachment_faction_keyword dfk
              on dfk.detachmentId = d.id
             and dfk.factionKeywordId = ?
            left join detachment_faction_detachment_points_cost dfdpc
              on dfdpc.detachmentId = d.id
             and dfdpc.factionKeywordId = ?
            where d.id = ?
            """,
            [faction_id, faction_id, detachment_id],
        ).fetchone()
    if not row:
        raise ValueError("Detachment not found")
    return dict_row(row)


def detachment_rules_for(heretic_builder, detachment_id):
    with heretic_builder.connect(readonly=True) as conn:
        rules = [
            dict_row(row)
            for row in conn.execute(
                """
                select id, name
                from detachment_rule
                where detachmentId = ?
                  and hiddenFromCommandBunker = 0
                order by displayOrder, lower(name)
                """,
                [detachment_id],
            )
        ]
        for rule in rules:
            rule["components"] = rule_components_for(conn, "detachmentRuleId", rule["id"])
    return rules


def detachment_details_for(heretic_builder, detachment_id):
    with heretic_builder.connect(readonly=True) as conn:
        details = [
            dict_row(row)
            for row in conn.execute(
                """
                select id, title
                from detachment_detail
                where detachmentId = ?
                order by displayOrder, lower(title)
                """,
                [detachment_id],
            )
        ]
        for detail in details:
            detail["bulletPoints"] = [
                dict_row(row)
                for row in conn.execute(
                    """
                    select text
                    from detachment_detail_bullet_point
                    where detachmentDetailId = ?
                    order by displayOrder
                    """,
                    [detail["id"]],
                )
            ]
    return details


def detachment_enhancements_for(heretic_builder, detachment_id):
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select id, name, rules, lore, basePointsCost, enhancementType
            from enhancement
            where detachmentId = ?
            order by displayOrder, lower(name)
            """,
            [detachment_id],
        ).fetchall()
    return [dict_row(row) for row in rows]


def detachment_stratagems_for(heretic_builder, detachment_id):
    with heretic_builder.connect(readonly=True) as conn:
        rows = conn.execute(
            """
            select id, name, lore, whenRules, targetRules, effectRules, restrictionRules,
                   cpCost, category, secondaryEffectAdditionalCPCost,
                   secondaryEffectIsMutuallyExclusive, secondaryEffect
            from stratagem
            where detachmentId = ?
            order by displayOrder, lower(name)
            """,
            [detachment_id],
        ).fetchall()
    return [dict_row(row) for row in rows]


def render_section_title(title):
    return f'<h2 class="detachment-section-title">{escape_html(title)}</h2>'


def render_rule_article(title, components):
    components_html = "".join(render_rule_component(component) for component in components)
    return (
        '<article class="codex-content">'
        f'<section class="rule-card"><h2>{escape_html(title)}</h2></section>'
        f'{components_html}'
        '</article>'
    )


def render_detachment_details(details):
    if not details:
        return ""
    cards = []
    for detail in details:
        bullet_html = "".join(
            f'<li>{render_rich_text(point["text"])}</li>'
            for point in detail["bulletPoints"]
        )
        if not bullet_html:
            continue
        cards.append(
            '<section class="rule-card detachment-detail-card">'
            f'<h3>{escape_html(detail["title"])}</h3>'
            f'<ul class="detachment-bullet-list">{bullet_html}</ul>'
            '</section>'
        )
    if not cards:
        return ""
    return render_section_title("Details") + '<div class="detachment-card-grid">' + "".join(cards) + "</div>"


def render_enhancement_card(enhancement):
    tags = []
    if enhancement.get("basePointsCost") is not None:
        tags.append(f'{enhancement["basePointsCost"]} pts')
    if enhancement.get("enhancementType"):
        tags.append(enhancement["enhancementType"].title())
    tag_html = "".join(f'<span class="unit-card-tag">{escape_html(tag)}</span>' for tag in tags)
    lore_html = render_lore_block(enhancement["lore"]) if enhancement.get("lore") else ""
    lore_class = " has-lore" if lore_html else ""
    return (
        f'<section class="rule-card detachment-feature-card{lore_class}">'
        '<div class="unit-card-heading">'
        f'<h3>{escape_html(enhancement["name"])}</h3>'
        f'<div class="detachment-tag-row">{tag_html}</div>'
        '</div>'
        f'{render_rich_text(enhancement["rules"])}'
        f'{lore_html}'
        '</section>'
    )


def render_detachment_enhancements(enhancements):
    if not enhancements:
        return ""
    cards = "".join(render_enhancement_card(enhancement) for enhancement in enhancements)
    return render_section_title("Enhancements") + '<div class="detachment-card-grid">' + cards + "</div>"


def render_lore_block(text, current_rule_reference=None):
    if not text or not normalize_rule_text(text):
        return ""
    return f'<div class="detachment-lore">{render_rich_text(text, current_rule_reference)}</div>'


def render_stratagem_rule(label, text, current_rule_reference=None):
    if not text or not normalize_rule_text(text):
        return ""
    return (
        '<div class="stratagem-rule-block">'
        f'<div class="stratagem-rule-label">{escape_html(label)}</div>'
        f'{render_rich_text(text, current_rule_reference)}'
        '</div>'
    )


def render_stratagem_card(stratagem, current_rule_reference=None):
    tags = []
    if stratagem.get("cpCost"):
        tags.append(f'{stratagem["cpCost"]} CP')
    if stratagem.get("category"):
        tags.append(stratagem["category"])
    tag_html = "".join(f'<span class="unit-card-tag">{escape_html(tag)}</span>' for tag in tags)
    secondary_label = "Secondary Effect"
    if stratagem.get("secondaryEffectAdditionalCPCost") is not None:
        secondary_label = f'Secondary Effect (+{stratagem["secondaryEffectAdditionalCPCost"]} CP)'
    pieces = [
        render_stratagem_rule("When", stratagem.get("whenRules"), current_rule_reference),
        render_stratagem_rule("Target", stratagem.get("targetRules"), current_rule_reference),
        render_stratagem_rule("Effect", stratagem.get("effectRules"), current_rule_reference),
        render_stratagem_rule("Restrictions", stratagem.get("restrictionRules"), current_rule_reference),
        render_stratagem_rule(secondary_label, stratagem.get("secondaryEffect"), current_rule_reference),
    ]
    lore_html = render_lore_block(stratagem["lore"], current_rule_reference) if stratagem.get("lore") else ""
    return (
        '<section class="rule-card detachment-feature-card stratagem-card">'
        '<div class="unit-card-heading">'
        f'<h3>{escape_html(stratagem["name"])}</h3>'
        f'<div class="detachment-tag-row">{tag_html}</div>'
        '</div>'
        f'{lore_html}'
        f'{"".join(piece for piece in pieces if piece)}'
        '</section>'
    )


def render_detachment_stratagems(stratagems):
    if not stratagems:
        return ""
    cards = "".join(render_stratagem_card(stratagem) for stratagem in stratagems)
    return render_section_title("Stratagems") + '<div class="detachment-card-grid stratagem-grid">' + cards + "</div>"


def render_faction_detachment_page(heretic_builder, faction_id, detachment_id):
    faction = faction_by_id(heretic_builder, faction_id)
    detachment = detachment_by_id_for_faction(heretic_builder, faction["id"], detachment_id)
    rules = detachment_rules_for(heretic_builder, detachment["id"])
    details = detachment_details_for(heretic_builder, detachment["id"])
    enhancements = detachment_enhancements_for(heretic_builder, detachment["id"])
    stratagems = detachment_stratagems_for(heretic_builder, detachment["id"])
    attach_faqs(heretic_builder, enhancements, "enhancementId")
    attach_faqs(heretic_builder, stratagems, "stratagemId")

    sections = []
    sections.extend(render_rule_article(rule["name"], rule["components"]) for rule in rules)
    sections.append(render_detachment_details(details))
    sections.append(render_detachment_enhancements(enhancements))
    sections.append(render_detachment_stratagems(stratagems))
    sections.append(render_faq_update_sections(
        faqs_for_entity(heretic_builder, "detachmentId", detachment["id"]),
        errata_title="Detachment Errata",
        faq_title="Detachment FAQ",
    ))
    sections.extend(
        render_faq_update_sections(
            enhancement.get("faqs") or [],
            errata_title=f'{enhancement["name"]} Errata',
            faq_title=f'{enhancement["name"]} FAQ',
        )
        for enhancement in enhancements
    )
    sections.extend(
        render_faq_update_sections(
            stratagem.get("faqs") or [],
            errata_title=f'{stratagem["name"]} Errata',
            faq_title=f'{stratagem["name"]} FAQ',
        )
        for stratagem in stratagems
    )
    content_html = '<div class="codex-content detachment-detail-content">' + "".join(section for section in sections if section) + "</div>"
    return render_codex_content_page(
        title=f"{detachment['name']} Detachment",
        window_title=f"{detachment['name']}\nDetachment",
        task_title=f"{faction['name']} / {detachment['name']}",
        page_class="faction-detail-page detachment-detail-page",
        content_html=content_html,
        back_href=f"{faction_href(faction['id'])}/detachments",
        back_label=f"Back to {faction['name']} Detachments",
        hero_image=faction_hero_image(faction),
    )


def render_faction_detachments_page(heretic_builder, faction_id):
    faction = faction_by_id(heretic_builder, faction_id)
    detachments = heretic_builder.detachments(faction["id"]).get("detachments", [])
    if detachments:
        items_html = "".join(
            render_list_item(
                detachment["name"],
                detachment_meta(detachment),
                href=detachment_href(faction["id"], detachment["id"]),
            )
            for detachment in detachments
        )
        content_html = f'<div class="list-grid">{items_html}</div>'
    else:
        content_html = '<div class="empty-state">No detachments found.</div>'
    return render_codex_content_page(
        title=f"{faction['name']} Detachments",
        window_title=f"{faction['name']}\nDetachments",
        task_title=f"{faction['name']} / Detachments",
        page_class="faction-detail-page many-buttons-page",
        content_html=content_html,
        back_href=faction_href(faction["id"]),
        back_label=f"Back to {faction['name']}",
        hero_image=faction_hero_image(faction),
    )


def render_faction_datasheets_page(heretic_builder, faction_id):
    faction = faction_by_id(heretic_builder, faction_id)
    datasheets = [
        datasheet
        for datasheet in codex_datasheets_for_faction(heretic_builder, faction["id"])
        if datasheet.get("points", 0) > 0
    ]
    allied_datasheets = [
        datasheet
        for datasheet in allied_datasheets_for_faction(heretic_builder, faction["id"])
        if datasheet.get("points", 0) > 0
    ]
    if datasheets or allied_datasheets:
        content_html = render_datasheet_groups(heretic_builder, datasheets, allied_datasheets, faction["id"])
    else:
        content_html = '<div class="empty-state">No datasheets found.</div>'
    return render_codex_content_page(
        title=f"{faction['name']} Data Sheets",
        window_title=f"{faction['name']}\nData Sheets",
        task_title=f"{faction['name']} / Data Sheets",
        page_class="faction-detail-page many-buttons-page",
        content_html=content_html,
        back_href=faction_href(faction["id"]),
        back_label=f"Back to {faction['name']}",
        hero_image=faction_hero_image(faction),
    )
