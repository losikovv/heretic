import re

from roster_builder_codex_rich_text import (
    core_rule_href,
    normalize_rule_text,
)


CORE_RULES_PUBLICATION_ID = "4cdf7a87-0914-49e8-b5df-b9f8be4d13c6"
MAX_SEARCH_LIMIT = 50


def compact_text(*values):
    chunks = []
    for value in values:
        text = normalize_rule_text(value)
        if text:
            text = re.sub(r"\*+", "", text).replace("■", " ")
            chunks.append(text)
    return " ".join(" ".join(chunks).split())


def search_tokens(value):
    return re.findall(r"[\w']+", compact_text(value).casefold())


def normalize_rule_section_code(value):
    match = re.fullmatch(r"\s*(\d{1,2})(?:\..*)?\s*", str(value or ""))
    if not match:
        return ""
    return f"{int(match.group(1)):02d}"


def faction_href(faction_id):
    return f"/codex/faction/{faction_id}"


def datasheet_href(faction_id, datasheet_id):
    return f"/codex/faction/{faction_id}/datasheet/{datasheet_id}"


def detachment_href(faction_id, detachment_id):
    return f"/codex/faction/{faction_id}/detachment/{detachment_id}"


def clipped_excerpt(text, query, tokens, length=180):
    source = compact_text(text)
    if not source:
        return ""
    source_folded = source.casefold()
    query_index = source_folded.find(query)
    indexes = [query_index] if query_index >= 0 else [
        source_folded.find(token)
        for token in tokens
        if source_folded.find(token) >= 0
    ]
    start = min(indexes) if indexes else 0
    start = max(0, start - 48)
    end = min(len(source), start + length)
    excerpt = source[start:end].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(source):
        excerpt = f"{excerpt}..."
    return excerpt


def result_score(item, query, tokens):
    title = compact_text(item["title"]).casefold()
    meta = compact_text(item.get("meta")).casefold()
    text = compact_text(item.get("text")).casefold()
    haystack = f"{title} {meta} {text}"
    if not all(token in haystack for token in tokens):
        return None

    score = 0
    if title == query:
        score += 300
    elif title.startswith(query):
        score += 220
    elif query in title:
        score += 160
    elif query in meta:
        score += 80
    elif query in text:
        score += 40

    for token in tokens:
        if title.startswith(token):
            score += 60
        elif token in title:
            score += 45
        elif token in meta:
            score += 25
        elif token in text:
            score += 10
    return score


def match_results(items, query, limit):
    query_text = compact_text(query).casefold()
    tokens = search_tokens(query)
    if not query_text or not tokens:
        return []

    matched = []
    seen = set()
    for item in items:
        if not item.get("title") or not item.get("href"):
            continue
        key = (item.get("type"), item["title"].casefold(), item["href"])
        if key in seen:
            continue
        seen.add(key)
        score = result_score(item, query_text, tokens)
        if score is None:
            continue
        matched.append({
            "score": score,
            "type": item.get("type") or "Result",
            "title": compact_text(item["title"]),
            "meta": compact_text(item.get("meta")),
            "excerpt": clipped_excerpt(item.get("text"), query_text, tokens),
            "href": item["href"],
        })

    matched.sort(key=lambda item: (-item["score"], item["type"], item["title"].casefold()))
    return [
        {key: value for key, value in item.items() if key != "score"}
        for item in matched[:limit]
    ]


class RosterSearchMixin:
    def search(self, query, limit=30):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 30
        limit = max(1, min(limit, MAX_SEARCH_LIMIT))
        query_text = compact_text(query)
        if not query_text:
            return {"query": "", "results": []}

        with self.connect(readonly=True) as conn:
            items = []
            items.extend(self.search_static_items(conn))
            items.extend(self.search_faction_items(conn))
            items.extend(self.search_core_rule_items(conn))
            items.extend(self.search_army_rule_items(conn))
            items.extend(self.search_datasheet_items(conn))
            items.extend(self.search_detachment_items(conn))
            items.extend(self.search_detachment_rule_items(conn))
            items.extend(self.search_enhancement_items(conn))
            items.extend(self.search_detachment_stratagem_items(conn))

        return {
            "query": query_text,
            "results": match_results(items, query_text, limit),
        }

    def search_static_items(self, conn):
        core_faq = conn.execute(
            """
            select group_concat(
              coalesce(errataHeader, '') || ' ' ||
              coalesce(errataText, '') || ' ' ||
              coalesce(question, '') || ' ' ||
              coalesce(answer, ''),
              ' '
            ) as faqText
            from faq
            where publicationId = ?
            """,
            [CORE_RULES_PUBLICATION_ID],
        ).fetchone()
        return [
            {
                "type": "App",
                "title": "Codex",
                "meta": "Reference",
                "text": "Core Rules Imperium Chaos Xenos factions datasheets detachments stratagems FAQ",
                "href": "/codex",
            },
            {
                "type": "Section",
                "title": "Core Rules",
                "meta": "Codex",
                "text": "Rules Stratagems FAQ Warhammer 40,000 reference",
                "href": "/codex/core-rules",
            },
            {
                "type": "Section",
                "title": "Core Rules FAQ",
                "meta": "Codex / Core Rules",
                "text": core_faq["faqText"] if core_faq else "",
                "href": "/codex/core-rules/faq",
            },
            {
                "type": "Section",
                "title": "Imperium",
                "meta": "Codex",
                "text": "Imperial factions Adeptus Astartes Space Marines",
                "href": "/codex/imperium",
            },
            {
                "type": "Section",
                "title": "Adeptus Astartes",
                "meta": "Codex / Imperium",
                "text": "Space Marines chapters",
                "href": "/codex/imperium/adeptus-astartes",
            },
            {
                "type": "Section",
                "title": "Chaos",
                "meta": "Codex",
                "text": "Chaos factions Heretic Astartes Daemons",
                "href": "/codex/chaos",
            },
            {
                "type": "Section",
                "title": "Xenos",
                "meta": "Codex",
                "text": "Xenos factions",
                "href": "/codex/xenos",
            },
        ]

    def search_faction_items(self, conn):
        rows = conn.execute(
            """
            select id, name, commonName, lore
            from faction_keyword
            where excludedFromArmyBuilder = 0
            order by lower(name)
            """
        ).fetchall()
        return [
            {
                "type": "Faction",
                "title": row["name"],
                "meta": "Codex",
                "text": compact_text(row["commonName"], row["lore"]),
                "href": faction_href(row["id"]),
            }
            for row in rows
        ]

    def search_core_rule_items(self, conn):
        sections = [
            {
                "type": "Section",
                "title": row["name"],
                "meta": "Core Rules",
                "text": "Rules section",
                "href": f"/codex/core-rules/section/{normalize_rule_section_code(row['name'])}",
            }
            for row in conn.execute(
                """
                select id, name
                from rule_section
                where publicationId = ?
                order by displayOrder, name
                """,
                [CORE_RULES_PUBLICATION_ID],
            )
        ]
        rules = [
            {
                "type": "Stratagem" if row["containerType"] == "stratagem" else "Core Rule",
                "title": row["title"],
                "meta": compact_text("Core Rules", row["sectionName"], row["subtitle"]),
                "text": compact_text(
                    row["containerType"],
                    row["stratagemName"],
                    row["lore"],
                    row["whenRules"],
                    row["targetRules"],
                    row["effectRules"],
                    row["restrictionRules"],
                    row["secondaryEffect"],
                    row["componentText"],
                    row["faqText"],
                ),
                "href": core_rule_href(row["subtitle"]),
            }
            for row in conn.execute(
                """
                select rc.id, rc.title, rc.subtitle, rc.containerType,
                       rs.name as sectionName,
                       s.name as stratagemName, s.lore, s.whenRules, s.targetRules,
                       s.effectRules, s.restrictionRules, s.secondaryEffect,
                       (
                         select group_concat(
                           coalesce(rcc.title, '') || ' ' ||
                           coalesce(rcc.subtitle, '') || ' ' ||
                           coalesce(rcc.textContent, '') || ' ' ||
                           coalesce(rcc.trigger, '') || ' ' ||
                           coalesce(rcc.effect, '') || ' ' ||
                           coalesce(rcc.altText, ''),
                           ' '
                         )
                         from rule_container_component rcc
                         where rcc.ruleContainerId = rc.id
                       ) as componentText,
                       (
                         select group_concat(
                           coalesce(f.errataHeader, '') || ' ' ||
                           coalesce(f.errataText, '') || ' ' ||
                           coalesce(f.question, '') || ' ' ||
                           coalesce(f.answer, ''),
                           ' '
                         )
                         from faq_config fc
                         join faq f on f.id = fc.faqId
                         where fc.ruleContainerId = rc.id
                       ) as faqText
                from rule_container rc
                join rule_section rs on rs.id = rc.ruleSectionId
                left join stratagem s on s.id = rc.stratagemId
                where rs.publicationId = ?
                order by rs.displayOrder, rc.displayOrder, rc.title
                """,
                [CORE_RULES_PUBLICATION_ID],
            )
        ]
        return sections + rules

    def search_army_rule_items(self, conn):
        rows = conn.execute(
            """
            select ar.id, ar.name, fk.id as factionId, fk.name as factionName,
                   (
                     select group_concat(
                       coalesce(rcc.title, '') || ' ' ||
                       coalesce(rcc.subtitle, '') || ' ' ||
                       coalesce(rcc.textContent, '') || ' ' ||
                       coalesce(rcc.trigger, '') || ' ' ||
                       coalesce(rcc.effect, '') || ' ' ||
                       coalesce(rcc.altText, ''),
                       ' '
                     )
                     from rule_container_component rcc
                     where rcc.armyRuleId = ar.id
                   ) as componentText,
                   (
                     select group_concat(
                       coalesce(f.errataHeader, '') || ' ' ||
                       coalesce(f.errataText, '') || ' ' ||
                       coalesce(f.question, '') || ' ' ||
                       coalesce(f.answer, ''),
                       ' '
                     )
                     from faq_config fc
                     join faq f on f.id = fc.faqId
                     where fc.armyRuleId = ar.id
                   ) as faqText
            from army_rule ar
            join army_rule_faction_keyword arfk on arfk.armyRuleId = ar.id
            join faction_keyword fk on fk.id = arfk.factionKeywordId
            where ar.hiddenFromCommandBunker = 0
              and fk.excludedFromArmyBuilder = 0
            order by lower(fk.name), ar.displayOrder, lower(ar.name)
            """
        ).fetchall()
        return [
            {
                "type": "Army Rule",
                "title": row["name"],
                "meta": compact_text(row["factionName"]),
                "text": compact_text(row["componentText"], row["faqText"]),
                "href": f"{faction_href(row['factionId'])}/army-rule",
            }
            for row in rows
        ]

    def search_datasheet_items(self, conn):
        rows = conn.execute(
            """
            select d.id, d.name, d.unitComposition, d.lore, d.baseSize,
                   fk.id as factionId, fk.name as factionName,
                   (
                     select group_concat(
                       coalesce(m.name, '') || ' ' ||
                       coalesce(m.movement, '') || ' ' ||
                       coalesce(m.toughness, '') || ' ' ||
                       coalesce(m.save, '') || ' ' ||
                       coalesce(m.wounds, '') || ' ' ||
                       coalesce(m.leadership, '') || ' ' ||
                       coalesce(m.objectiveControl, ''),
                       ' '
                     )
                     from miniature m
                     where m.datasheetId = d.id
                   ) as miniatureText,
                   (
                     select group_concat(dr.name || ' ' || dr.rules, ' ')
                     from datasheet_rule dr
                     where dr.datasheetId = d.id
                   ) as ruleText,
                   (
                     select group_concat(
                       da.name || ' ' ||
                       da.abilityType || ' ' ||
                       da.rules || ' ' ||
                       coalesce(da.lore, '') || ' ' ||
                       coalesce(da.subAbilityHeader, '') || ' ' ||
                       coalesce(dsa.name, '') || ' ' ||
                       coalesce(dsa.rules, ''),
                       ' '
                     )
                     from datasheet_datasheet_ability dda
                     join datasheet_ability da on da.id = dda.datasheetAbilityId
                     left join datasheet_sub_ability dsa on dsa.datasheetAbilityId = da.id
                     where dda.datasheetId = d.id
                   ) as abilityText,
                   (
                     select group_concat(
                       coalesce(inv.rules, '') || ' ' ||
                       coalesce(inv.save, '') || ' ' ||
                       coalesce(inv.meleeSave, '') || ' ' ||
                       coalesce(inv.rangedSave, ''),
                       ' '
                     )
                     from invulnerable_save inv
                     where inv.datasheetId = d.id
                   ) as invulnerableText,
                   (
                     select group_concat(name || ' ' || rules, ' ')
                     from datasheet_damage dd
                     where dd.datasheetId = d.id
                   ) as damageText,
                   (
                     select group_concat(rulesText, ' ')
                     from wargear_rule wr
                     where wr.datasheetId = d.id
                   ) as wargearRuleText,
                   (
                     select group_concat(
                       coalesce(wog.instructionText, '') || ' ' ||
                       coalesce(m.name, '') || ' ' ||
                       coalesce(wi.name, '') || ' ' ||
                       coalesce(wi.wargearType, '') || ' ' ||
                       coalesce(wi.ruleText, '') || ' ' ||
                       coalesce(wip.name, '') || ' ' ||
                       coalesce(wip.type, '') || ' ' ||
                       coalesce(wip.range, '') || ' ' ||
                       coalesce(wip.attacks, '') || ' ' ||
                       coalesce(wip.ballisticSkill, '') || ' ' ||
                       coalesce(wip.weaponSkill, '') || ' ' ||
                       coalesce(wip.strength, '') || ' ' ||
                       coalesce(wip.armourPenetration, '') || ' ' ||
                       coalesce(wip.damage, '') || ' ' ||
                       coalesce(wa.name, ''),
                       ' '
                     )
                     from wargear_option_group wog
                     left join miniature m on m.id = wog.miniatureId
                     left join wargear_option wo on wo.wargearOptionGroupId = wog.id
                     left join wargear_item wi on wi.id = wo.wargearItemId
                     left join wargear_item_profile wip on wip.wargearItemId = wi.id
                     left join wargear_item_profile_wargear_ability wipwa on wipwa.wargearItemProfileId = wip.id
                     left join wargear_ability wa on wa.id = wipwa.wargearAbilityId
                     where wog.datasheetId = d.id
                   ) as wargearText,
                   (
                     select group_concat(
                       coalesce(f.errataHeader, '') || ' ' ||
                       coalesce(f.errataText, '') || ' ' ||
                       coalesce(f.question, '') || ' ' ||
                       coalesce(f.answer, ''),
                       ' '
                     )
                     from faq_config fc
                     join faq f on f.id = fc.faqId
                     where fc.datasheetId = d.id
                   ) as faqText
            from datasheet d
            join datasheet_faction_keyword dfk on dfk.datasheetId = d.id
            join faction_keyword fk on fk.id = dfk.factionKeywordId
            where fk.excludedFromArmyBuilder = 0
            order by lower(fk.name), lower(d.name)
            """
        ).fetchall()
        return [
            {
                "type": "Datasheet",
                "title": row["name"],
                "meta": row["factionName"],
                "text": compact_text(
                    row["unitComposition"],
                    row["lore"],
                    row["baseSize"],
                    row["miniatureText"],
                    row["ruleText"],
                    row["abilityText"],
                    row["invulnerableText"],
                    row["damageText"],
                    row["wargearRuleText"],
                    row["wargearText"],
                    row["faqText"],
                ),
                "href": datasheet_href(row["factionId"], row["id"]),
            }
            for row in rows
        ]

    def search_detachment_items(self, conn):
        rows = conn.execute(
            """
            select d.id, d.name, fk.id as factionId, fk.name as factionName,
                   (
                     select group_concat(
                       dd.title || ' ' || coalesce(ddbp.text, ''),
                       ' '
                     )
                     from detachment_detail dd
                     left join detachment_detail_bullet_point ddbp on ddbp.detachmentDetailId = dd.id
                     where dd.detachmentId = d.id
                   ) as detailText,
                   (
                     select group_concat(
                       coalesce(f.errataHeader, '') || ' ' ||
                       coalesce(f.errataText, '') || ' ' ||
                       coalesce(f.question, '') || ' ' ||
                       coalesce(f.answer, ''),
                       ' '
                     )
                     from faq_config fc
                     join faq f on f.id = fc.faqId
                     where fc.detachmentId = d.id
                   ) as faqText
            from detachment d
            join detachment_faction_keyword dfk on dfk.detachmentId = d.id
            join faction_keyword fk on fk.id = dfk.factionKeywordId
            where fk.excludedFromArmyBuilder = 0
            order by lower(fk.name), lower(d.name)
            """
        ).fetchall()
        return [
            {
                "type": "Detachment",
                "title": row["name"],
                "meta": row["factionName"],
                "text": compact_text(row["detailText"], row["faqText"]),
                "href": detachment_href(row["factionId"], row["id"]),
            }
            for row in rows
        ]

    def search_detachment_rule_items(self, conn):
        rows = conn.execute(
            """
            select dr.id, dr.name, d.id as detachmentId, d.name as detachmentName,
                   fk.id as factionId, fk.name as factionName,
                   (
                     select group_concat(
                       coalesce(rcc.title, '') || ' ' ||
                       coalesce(rcc.subtitle, '') || ' ' ||
                       coalesce(rcc.textContent, '') || ' ' ||
                       coalesce(rcc.trigger, '') || ' ' ||
                       coalesce(rcc.effect, '') || ' ' ||
                       coalesce(rcc.altText, ''),
                       ' '
                     )
                     from rule_container_component rcc
                     where rcc.detachmentRuleId = dr.id
                   ) as componentText
            from detachment_rule dr
            join detachment d on d.id = dr.detachmentId
            join detachment_faction_keyword dfk on dfk.detachmentId = d.id
            join faction_keyword fk on fk.id = dfk.factionKeywordId
            where dr.hiddenFromCommandBunker = 0
              and fk.excludedFromArmyBuilder = 0
            order by lower(fk.name), lower(d.name), dr.displayOrder, lower(dr.name)
            """
        ).fetchall()
        return [
            {
                "type": "Detachment Rule",
                "title": row["name"],
                "meta": compact_text(row["factionName"], row["detachmentName"]),
                "text": row["componentText"],
                "href": detachment_href(row["factionId"], row["detachmentId"]),
            }
            for row in rows
        ]

    def search_enhancement_items(self, conn):
        rows = conn.execute(
            """
            select e.id, e.name, e.rules, e.lore, e.basePointsCost, e.enhancementType,
                   d.id as detachmentId, d.name as detachmentName,
                   fk.id as factionId, fk.name as factionName,
                   (
                     select group_concat(
                       coalesce(f.errataHeader, '') || ' ' ||
                       coalesce(f.errataText, '') || ' ' ||
                       coalesce(f.question, '') || ' ' ||
                       coalesce(f.answer, ''),
                       ' '
                     )
                     from faq_config fc
                     join faq f on f.id = fc.faqId
                     where fc.enhancementId = e.id
                   ) as faqText
            from enhancement e
            join detachment d on d.id = e.detachmentId
            join detachment_faction_keyword dfk on dfk.detachmentId = d.id
            join faction_keyword fk on fk.id = dfk.factionKeywordId
            where fk.excludedFromArmyBuilder = 0
            order by lower(fk.name), lower(d.name), e.displayOrder, lower(e.name)
            """
        ).fetchall()
        return [
            {
                "type": "Enhancement",
                "title": row["name"],
                "meta": compact_text(row["factionName"], row["detachmentName"]),
                "text": compact_text(
                    row["rules"],
                    row["lore"],
                    row["basePointsCost"],
                    row["enhancementType"],
                    row["faqText"],
                ),
                "href": detachment_href(row["factionId"], row["detachmentId"]),
            }
            for row in rows
        ]

    def search_detachment_stratagem_items(self, conn):
        rows = conn.execute(
            """
            select s.id, s.name, s.lore, s.whenRules, s.targetRules, s.effectRules,
                   s.restrictionRules, s.cpCost, s.category, s.secondaryEffect,
                   d.id as detachmentId, d.name as detachmentName,
                   fk.id as factionId, fk.name as factionName,
                   (
                     select group_concat(
                       coalesce(f.errataHeader, '') || ' ' ||
                       coalesce(f.errataText, '') || ' ' ||
                       coalesce(f.question, '') || ' ' ||
                       coalesce(f.answer, ''),
                       ' '
                     )
                     from faq_config fc
                     join faq f on f.id = fc.faqId
                     where fc.stratagemId = s.id
                   ) as faqText
            from stratagem s
            join detachment d on d.id = s.detachmentId
            join detachment_faction_keyword dfk on dfk.detachmentId = d.id
            join faction_keyword fk on fk.id = dfk.factionKeywordId
            where fk.excludedFromArmyBuilder = 0
            order by lower(fk.name), lower(d.name), s.displayOrder, lower(s.name)
            """
        ).fetchall()
        return [
            {
                "type": "Stratagem",
                "title": row["name"],
                "meta": compact_text(row["factionName"], row["detachmentName"], row["cpCost"], row["category"]),
                "text": compact_text(
                    row["lore"],
                    row["whenRules"],
                    row["targetRules"],
                    row["effectRules"],
                    row["restrictionRules"],
                    row["secondaryEffect"],
                    row["faqText"],
                ),
                "href": detachment_href(row["factionId"], row["detachmentId"]),
            }
            for row in rows
        ]
