from roster_builder_utils import dict_row


class RosterEnhancementRulesMixin:
    def validate_enhancements(self, conn, roster, units, messages):
        detachment_ids = set(self.roster_detachment_ids(conn, roster["id"]))
        selected = []
        for unit in units:
            unit_selected = []
            for enhancement in unit["unitEnhancements"]:
                selected.append((unit, enhancement, set(unit["keywordIds"]), unit["name"], None, "unit"))
                unit_selected.append(enhancement)
            for enhancement in unit["miniatureEnhancements"]:
                miniature = next((item for item in unit["miniatures"] if item["rosterUnitMiniatureId"] == enhancement["targetId"]), None)
                keyword_ids = self.miniature_keyword_ids(conn, miniature["miniatureId"]) if miniature else set(unit["keywordIds"])
                target_name = miniature["name"] if miniature else unit["name"]
                selected.append((unit, enhancement, keyword_ids, target_name, miniature, "miniature"))
                unit_selected.append(enhancement)
                if miniature and miniature["count"] <= 0:
                    messages.append({"level": "error", "text": f"{target_name} cannot take enhancements with a model count of 0."})
            if len(unit_selected) > 1:
                messages.append({"level": "error", "text": f"{unit['name']} has selected more than 1 Enhancement."})

        included = [item for item in selected if item[1]["isIncludedInEnhancementLimit"]]
        limit = roster.get("enhancementLimit") or 0
        if limit and len(included) > limit:
            messages.append({"level": "error", "text": f"Roster has {len(included)} enhancements; limit is {limit}."})

        by_enhancement = {}
        for _, enhancement, _, _, _, _ in selected:
            by_enhancement.setdefault(enhancement["id"], []).append(enhancement)
        for enhancement_id, items in by_enhancement.items():
            limit_row = conn.execute('select name, "limit" from enhancement where id = ?', [enhancement_id]).fetchone()
            if limit_row and limit_row["limit"] is not None and len(items) > limit_row["limit"]:
                messages.append({"level": "error", "text": f"{limit_row['name']} selected {len(items)} times; limit is {limit_row['limit']}."})

        for unit, enhancement, keyword_ids, target_name, miniature, target_kind in selected:
            if enhancement["detachmentId"] and enhancement["detachmentId"] not in detachment_ids:
                names = self.detachment_names(conn, [enhancement["detachmentId"]])
                detachment_name = names[0] if names else "its detachment"
                messages.append({"level": "error", "text": f"{enhancement['name']} requires the {detachment_name} detachment."})
            if target_kind == "miniature" and enhancement["enhancementType"] != "miniature":
                messages.append({"level": "error", "text": f"{enhancement['name']} must be selected for a unit, not a model."})
            if target_kind == "unit" and enhancement["enhancementType"] == "miniature":
                messages.append({"level": "error", "text": f"{enhancement['name']} must be selected for a model, not a unit."})
            if unit.get("allyType", "native") != "native":
                allied_faction = conn.execute(
                    "select canTakeEnhancements from allied_faction where id = ?",
                    [unit["allyType"]],
                ).fetchone()
                if allied_faction and not allied_faction["canTakeEnhancements"]:
                    messages.append({"level": "error", "text": f"{unit['name']} cannot take enhancements as an allied unit."})
            if miniature and miniature.get("excludedFromEnhancements"):
                messages.append({"level": "error", "text": f"{target_name} cannot take enhancements."})
            if not enhancement["isEquipableByEpicHero"] and self.keyword_name_in_ids(conn, keyword_ids, "Epic Hero"):
                messages.append({"level": "error", "text": f"{target_name} cannot take {enhancement['name']} as an Epic Hero."})
            if not enhancement["isEquipableByNonCharacterUnit"] and not self.keyword_name_in_ids(conn, keyword_ids, "Character"):
                messages.append({"level": "error", "text": f"{target_name} does not have the required Character keyword for {enhancement['name']}."})
            if not self.enhancement_required_keywords_satisfied(conn, enhancement["id"], unit, keyword_ids, roster):
                messages.append({"level": "error", "text": f"{target_name} does not have the required keywords for {enhancement['name']}."})
            excluded = self.enhancement_excluded_keyword_names(conn, enhancement["id"], keyword_ids)
            if excluded:
                messages.append({"level": "error", "text": f"{target_name} cannot take {enhancement['name']} with keyword {', '.join(excluded)}."})
            required_wargear = [
                row["wargearItemId"] for row in conn.execute(
                    "select wargearItemId from enhancement_required_wargear_item where enhancementId = ?",
                    [enhancement["id"]],
                )
            ]
            for wargear_item_id in required_wargear:
                has_required_wargear = (
                    self.miniature_has_wargear_item(conn, miniature["rosterUnitMiniatureId"], wargear_item_id)
                    if miniature
                    else self.unit_has_wargear_item(conn, unit["id"], wargear_item_id)
                )
                if not has_required_wargear:
                    messages.append({"level": "error", "text": f"{target_name} must have {self.wargear_item_name(conn, wargear_item_id)} for {enhancement['name']}."})
            if not self.enhancement_bodyguard_requirement_satisfied(conn, roster["id"], unit["id"], enhancement["id"]):
                messages.append({"level": "error", "text": f"{unit['name']} does not meet the attached-unit requirement for {enhancement['name']}."})
            if enhancement["cannotBeWarlord"] and unit.get("isWarlord"):
                messages.append({"level": "error", "text": f"{unit['name']} cannot be your Warlord with {enhancement['name']}."})

        self.validate_attached_unit_enhancement_limits(conn, roster["id"], messages)
        self.validate_combat_patrol_enhancements(conn, roster["id"], selected, messages)

    def enhancement_required_keywords_satisfied(self, conn, enhancement_id, unit, target_keyword_ids, roster):
        groups = conn.execute(
            """
            select id, datasheetId
            from enhancement_required_keyword_group
            where enhancementId = ?
            """,
            [enhancement_id],
        ).fetchall()
        if not groups:
            return True
        for group in groups:
            if group["datasheetId"] and group["datasheetId"] != unit["datasheetId"]:
                continue
            keyword_ids = {
                row["keywordId"] for row in conn.execute(
                    """
                    select keywordId
                    from enhancement_required_keyword_group_keyword
                    where enhancementRequiredKeywordGroupId = ?
                    """,
                    [group["id"]],
                )
            }
            faction_ids = {
                row["factionKeywordId"] for row in conn.execute(
                    """
                    select factionKeywordId
                    from enhancement_required_keyword_group_faction_keyword
                    where enhancementRequiredKeywordGroupId = ?
                    """,
                    [group["id"]],
                )
            }
            if keyword_ids and not keyword_ids.issubset(target_keyword_ids):
                continue
            allowed_faction_ids = set(self.composition_faction_keyword_ids(
                conn,
                roster.get("factionKeywordId"),
                unit.get("allyType", "native"),
            ))
            allowed_faction_ids.update(unit.get("factionKeywordIds", []))
            if faction_ids and not allowed_faction_ids.intersection(faction_ids):
                continue
            return True
        return False

    def enhancement_excluded_keyword_names(self, conn, enhancement_id, keyword_ids):
        if not keyword_ids:
            return []
        placeholders = ",".join("?" for _ in keyword_ids)
        return [
            row["name"] for row in conn.execute(
                f"""
                select k.name
                from enhancement_excluded_keyword eek
                join keyword k on k.id = eek.keywordId
                where eek.enhancementId = ?
                  and eek.keywordId in ({placeholders})
                order by k.name
                """,
                [enhancement_id, *keyword_ids],
            )
        ]

    def enhancement_bodyguard_requirement_satisfied(self, conn, roster_id, roster_unit_id, enhancement_id):
        roster = conn.execute("select factionKeywordId from roster where id = ?", [roster_id]).fetchone()
        detachment_ids = self.roster_detachment_ids(conn, roster_id)
        rows = conn.execute(
            """
            select ebg.id, ebg.bodyguardType, ebg.factionKeywordId
            from enhancement_bodyguard_group ebg
            where ebg.enhancementId = ?
            """,
            [enhancement_id],
        ).fetchall()
        if not rows:
            return True
        for row in rows:
            if row["factionKeywordId"] and (not roster or row["factionKeywordId"] != roster["factionKeywordId"]):
                continue
            attached = conn.execute(
                """
                select rauru.rosterAttachedUnitId
                from roster_attached_unit_roster_unit rauru
                join roster_attached_unit rau on rau.id = rauru.rosterAttachedUnitId
                where rau.rosterId = ?
                  and rauru.rosterUnitId = ?
                  and rauru.attachmentType = ?
                """,
                [roster_id, roster_unit_id, row["bodyguardType"]],
            ).fetchall()
            for attached_row in attached:
                bodyguards = conn.execute(
                    """
                    select ru.id as rosterUnitId, ru.datasheetId
                    from roster_attached_unit_roster_unit rauru
                    join roster_unit ru on ru.id = rauru.rosterUnitId
                    where rauru.rosterAttachedUnitId = ?
                      and rauru.attachmentType = 'bodyguard'
                    """,
                    [attached_row["rosterAttachedUnitId"]],
                ).fetchall()
                allowed_datasheets = {
                    item["datasheetId"] for item in conn.execute(
                        "select datasheetId from enhancement_bodyguard_group_datasheet where enhancementBodyguardGroupId = ?",
                        [row["id"]],
                    )
                }
                allowed_keywords = {
                    item["keywordId"] for item in conn.execute(
                        "select keywordId from enhancement_bodyguard_group_keyword where enhancementBodyguardGroupId = ?",
                        [row["id"]],
                    )
                }
                for bodyguard in bodyguards:
                    if allowed_datasheets and bodyguard["datasheetId"] not in allowed_datasheets:
                        continue
                    if not allowed_keywords:
                        return True
                    bodyguard_keywords = {
                        item["id"] for item in self.unit_keywords(
                            conn,
                            bodyguard["rosterUnitId"],
                            bodyguard["datasheetId"],
                            dict_row(roster) if roster else {},
                            detachment_ids,
                            [],
                        )
                    }
                    if allowed_keywords.intersection(bodyguard_keywords):
                        return True
        return False

    def validate_attached_unit_enhancement_limits(self, conn, roster_id, messages):
        rows = conn.execute(
            """
            select rau.id,
                   count(distinct rue.enhancementId) + count(distinct rume.enhancementId) as enhancementCount
            from roster_attached_unit rau
            join roster_attached_unit_roster_unit rauru on rauru.rosterAttachedUnitId = rau.id
            join roster_unit ru on ru.id = rauru.rosterUnitId
            left join roster_unit_miniature rum on rum.rosterUnitId = ru.id
            left join roster_unit_enhancement rue on rue.rosterUnitId = ru.id
            left join roster_unit_miniature_enhancement rume on rume.rosterUnitMiniatureId = rum.id
            where rau.rosterId = ?
            group by rau.id
            having enhancementCount > 1
            """,
            [roster_id],
        ).fetchall()
        for row in rows:
            messages.append({"level": "error", "text": f"Attached unit {row['id']} has more than 1 enhancement."})

    def validate_combat_patrol_enhancements(self, conn, roster_id, selected, messages):
        detachment_ids = self.roster_detachment_ids(conn, roster_id)
        if not detachment_ids:
            return
        placeholders = ",".join("?" for _ in detachment_ids)
        combat_patrols = conn.execute(
            f"""
            select id, name
            from detachment
            where isCombatPatrol = 1
              and id in ({placeholders})
            order by name
            """,
            detachment_ids,
        ).fetchall()
        if not combat_patrols:
            return
        selected_by_id = {}
        for _, enhancement, _, _, _, _ in selected:
            selected_by_id[enhancement["id"]] = selected_by_id.get(enhancement["id"], 0) + 1
        for detachment in combat_patrols:
            defaults = conn.execute(
                """
                select id, name
                from enhancement
                where detachmentId = ?
                  and isCombatPatrolDefault = 1
                order by name
                """,
                [detachment["id"]],
            ).fetchall()
            if not defaults:
                continue
            default_ids = {row["id"] for row in defaults}
            for default in defaults:
                count = selected_by_id.get(default["id"], 0)
                if count == 0:
                    messages.append({
                        "level": "error",
                        "text": f"{detachment['name']} requires {default['name']} as its Combat Patrol enhancement.",
                    })
                elif count > 1:
                    messages.append({
                        "level": "error",
                        "text": f"{default['name']} selected {count} times; Combat Patrol requires it exactly once.",
                    })
            for _, enhancement, _, _, _, _ in selected:
                if enhancement["detachmentId"] == detachment["id"] and enhancement["id"] not in default_ids:
                    messages.append({"level": "error", "text": f"{enhancement['name']} is not the Combat Patrol enhancement for {detachment['name']}."})
