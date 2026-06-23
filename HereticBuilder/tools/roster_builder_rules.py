from roster_builder_utils import dict_row


class RosterRulesMixin:
    def validate(self, conn, roster, detachments, units, total_points):
        messages = []
        limit = roster.get("pointsLimit") or 0
        if limit and total_points > limit:
            messages.append({"level": "error", "text": f"Roster is {total_points - limit} points over the {limit} point limit."})
        if not detachments:
            messages.append({"level": "error", "text": "Pick a detachment."})
        detachment_points_limit = roster.get("detachmentPointsLimit") or 0
        if detachments and detachment_points_limit:
            detachment_points = sum(detachment["detachmentPointsCost"] or 0 for detachment in detachments)
            if detachment_points > detachment_points_limit:
                messages.append({"level": "error", "text": f"Roster uses {detachment_points} detachment points; limit is {detachment_points_limit}."})
        for detachment in detachments:
            allowed = conn.execute(
                """
                select 1
                from detachment_faction_keyword
                where detachmentId = ? and factionKeywordId = ?
                """,
                [detachment["id"], roster["factionKeywordId"]],
            ).fetchone()
            if not allowed:
                messages.append({"level": "error", "text": f"{detachment['name']} is not available to {roster['factionName']}."})

        self.validate_detachment_unique_keywords(conn, detachments, messages)
        self.validate_warlord(conn, roster, detachments, units, messages)
        self.validate_allegiance_abilities(conn, roster, detachments, units, messages)
        self.validate_allied_units(conn, roster, detachments, units, messages)
        self.validate_enhancements(conn, roster, units, messages)
        self.validate_attached_units(conn, roster, detachments, messages)
        self.validate_detachment_datasheets(conn, roster, detachments, units, messages)
        self.validate_keyword_restrictions(conn, roster, detachments, units, messages)
        self.validate_unit_compositions(conn, roster, detachments, units, messages)
        self.validate_wargear_loadouts(conn, units, messages)

        duplicate_limit = roster.get("duplicateUnitLimit") or 3
        counts = {}
        first_by_datasheet = {}
        for unit in units:
            counts[unit["datasheetId"]] = counts.get(unit["datasheetId"], 0) + 1
            first_by_datasheet.setdefault(unit["datasheetId"], unit)
            if unit.get("allyType", "native") == "native":
                allowed = conn.execute(
                    """
                    select 1
                    from datasheet_faction_keyword
                    where datasheetId = ? and factionKeywordId = ?
                    """,
                    [unit["datasheetId"], roster["factionKeywordId"]],
                ).fetchone()
                if not allowed:
                    messages.append({"level": "error", "text": f"{unit['name']} is not native to {roster['factionName']}."})
            faction_excluded = conn.execute(
                """
                select 1
                from faction_keyword_excluded_datasheet
                where factionKeywordId = ? and datasheetId = ?
                """,
                [roster["factionKeywordId"], unit["datasheetId"]],
            ).fetchone()
            if faction_excluded:
                messages.append({"level": "error", "text": f"{unit['name']} is excluded from {roster['factionName']} rosters."})
        for datasheet_id, count in counts.items():
            unit = first_by_datasheet[datasheet_id]
            effective_limit = self.duplicate_limit_for_unit(unit, duplicate_limit)
            if count > effective_limit:
                messages.append({"level": "error", "text": f"{unit['name']} has {count} units; limit is {effective_limit}."})
        self.validate_successor_chapter_epic_heroes(units, messages)
        if not units:
            messages.append({"level": "warning", "text": "Roster has no units."})
        state = "invalid" if any(item["level"] == "error" for item in messages) else "valid"
        return {"state": state, "messages": messages}

    def unit_keywords(self, conn, roster_unit_id, datasheet_id, roster=None, detachment_ids=None, allegiance_ability_ids=None):
        roster = roster or {}
        detachment_ids = set(detachment_ids or [])
        allegiance_ability_ids = set(allegiance_ability_ids or [])
        rows = conn.execute(
            """
            select distinct k.id, k.name
            from roster_unit_miniature rum
            join miniature_keyword mk on mk.miniatureId = rum.miniatureId
            join keyword k on k.id = mk.keywordId
            where rum.rosterUnitId = ?
              and rum.count > 0
            order by k.name
            """,
            [roster_unit_id],
        ).fetchall()
        if not rows:
            has_roster_miniatures = conn.execute(
                "select 1 from roster_unit_miniature where rosterUnitId = ? limit 1",
                [roster_unit_id],
            ).fetchone()
            if has_roster_miniatures:
                return []
            rows = conn.execute(
                """
                select distinct k.id, k.name
                from miniature m
                join miniature_keyword mk on mk.miniatureId = m.id
                join keyword k on k.id = mk.keywordId
                where m.datasheetId = ?
                order by k.name
                """,
                [datasheet_id],
            ).fetchall()
        keywords = {row["id"]: dict_row(row) for row in rows}
        if roster.get("id"):
            warlord_miniature_ids = set(self.roster_warlord_miniature_ids(conn, roster["id"]))
            conditional_rows = conn.execute(
                """
                select ck.*, k.name
                from conditional_keyword ck
                join keyword k on k.id = ck.keywordId
                where ck.datasheetId = ?
                """,
                [datasheet_id],
            ).fetchall()
            for row in conditional_rows:
                if not self.conditional_keyword_row_applies(
                    row,
                    roster,
                    detachment_ids,
                    allegiance_ability_ids,
                    warlord_miniature_ids,
                ):
                    continue
                keywords[row["keywordId"]] = {"id": row["keywordId"], "name": row["name"]}
        return sorted(keywords.values(), key=lambda item: item["name"].lower())

    def conditional_keyword_row_applies(self, row, roster, detachment_ids, allegiance_ability_ids, warlord_miniature_ids):
        if row["requiredWarlordMiniatureId"] and row["requiredWarlordMiniatureId"] not in warlord_miniature_ids:
            return False
        if row["requiredAllegianceAbilityId"] and row["requiredAllegianceAbilityId"] not in allegiance_ability_ids:
            return False
        if row["requiredRosterFactionKeywordId"] and row["requiredRosterFactionKeywordId"] != roster.get("factionKeywordId"):
            return False
        if row["requiredDetachmentId"] and row["requiredDetachmentId"] not in detachment_ids:
            return False
        return True

    def conditional_keyword_applies(
        self,
        conn,
        datasheet_id,
        keyword_name,
        roster=None,
        detachment_ids=None,
        allegiance_ability_ids=None,
        warlord_miniature_ids=None,
    ):
        roster = roster or {}
        detachment_ids = set(detachment_ids or [])
        allegiance_ability_ids = set(allegiance_ability_ids or [])
        if warlord_miniature_ids is None:
            warlord_miniature_ids = set(self.roster_warlord_miniature_ids(conn, roster["id"])) if roster.get("id") else set()
        else:
            warlord_miniature_ids = set(warlord_miniature_ids)
        rows = conn.execute(
            """
            select ck.*
            from conditional_keyword ck
            join keyword k on k.id = ck.keywordId
            where ck.datasheetId = ?
              and lower(k.name) = ?
            """,
            [datasheet_id, keyword_name.lower()],
        ).fetchall()
        return any(
            self.conditional_keyword_row_applies(
                row,
                roster,
                detachment_ids,
                allegiance_ability_ids,
                warlord_miniature_ids,
            )
            for row in rows
        )

    def miniature_keyword_ids(self, conn, miniature_id):
        return {
            row["keywordId"] for row in conn.execute(
                "select keywordId from miniature_keyword where miniatureId = ?",
                [miniature_id],
            )
        }

    def roster_warlord_miniature_ids(self, conn, roster_id):
        return [
            row["miniatureId"] for row in conn.execute(
                """
                select rum.miniatureId
                from roster_unit_miniature rum
                join roster_unit ru on ru.id = rum.rosterUnitId
                where ru.rosterId = ? and rum.isWarlord = 1
                  and rum.count > 0
                """,
                [roster_id],
            )
        ]

    def unit_allegiance_abilities(self, conn, roster_unit_id):
        return [
            dict_row(row) for row in conn.execute(
                """
                select aa.id, aa.name, aa.requiresWargearItemId,
                       aag.id as groupId, aag.name as groupName
                from roster_unit_allegiance_ability ruaa
                join allegiance_ability aa on aa.id = ruaa.allegianceAbilityId
                join allegiance_ability_group aag on aag.id = aa.allegianceAbilityGroupId
                where ruaa.rosterUnitId = ?
                order by aag.name, aa.name
                """,
                [roster_unit_id],
            )
        ]

    def unit_enhancements(self, conn, roster_unit_id, keyword_ids):
        return [
            self.enhancement_item(conn, row, keyword_ids) for row in conn.execute(
                """
                select e.*, rue.rosterUnitId as targetId
                from roster_unit_enhancement rue
                join enhancement e on e.id = rue.enhancementId
                where rue.rosterUnitId = ?
                order by e.name
                """,
                [roster_unit_id],
            )
        ]

    def miniature_enhancements(self, conn, roster_unit_miniature_id, keyword_ids):
        return [
            self.enhancement_item(conn, row, keyword_ids) for row in conn.execute(
                """
                select e.*, rume.rosterUnitMiniatureId as targetId
                from roster_unit_miniature_enhancement rume
                join enhancement e on e.id = rume.enhancementId
                where rume.rosterUnitMiniatureId = ?
                order by e.name
                """,
                [roster_unit_miniature_id],
            )
        ]

    def enhancement_item(self, conn, row, keyword_ids):
        item = dict_row(row)
        item["points"] = self.enhancement_points(conn, row["id"], keyword_ids)
        return item

    def enhancement_points(self, conn, enhancement_id, keyword_ids):
        if keyword_ids:
            placeholders = ",".join("?" for _ in keyword_ids)
            row = conn.execute(
                f"""
                select pointsCost
                from enhancement_keyword_points_cost
                where enhancementId = ? and keywordId in ({placeholders})
                order by displayOrder
                limit 1
                """,
                [enhancement_id, *keyword_ids],
            ).fetchone()
            if row:
                return row["pointsCost"] or 0
        row = conn.execute("select basePointsCost from enhancement where id = ?", [enhancement_id]).fetchone()
        return (row["basePointsCost"] if row else 0) or 0

    def roster_detachment_ids(self, conn, roster_id):
        return [
            row["detachmentId"] for row in conn.execute(
                "select detachmentId from roster_detachment where rosterId = ?",
                [roster_id],
            )
        ]

    def can_be_warlord(self, conn, miniature_id, cannot_be_warlord, can_be_non_character_warlord, detachment_ids, conditional_character=False):
        if detachment_ids:
            placeholders = ",".join("?" for _ in detachment_ids)
            granted = conn.execute(
                f"""
                select 1
                from detachment_granted_warlord_miniature
                where miniatureId = ? and detachmentId in ({placeholders})
                """,
                [miniature_id, *detachment_ids],
            ).fetchone()
            if granted:
                return True
        if cannot_be_warlord:
            return False
        if can_be_non_character_warlord:
            return True
        character = conn.execute(
            """
            select 1
            from miniature_keyword mk
            join keyword k on k.id = mk.keywordId
            where mk.miniatureId = ? and lower(k.name) = 'character'
            """,
            [miniature_id],
        ).fetchone()
        return bool(character) or bool(conditional_character)

    def duplicate_limit_for_unit(self, unit, base_limit):
        names = {name.lower() for name in unit.get("keywordNames", [])}
        if "epic hero" in names:
            return 1
        if "battleline" in names or "dedicated transport" in names:
            return 6
        return base_limit

    def validate_detachment_unique_keywords(self, conn, detachments, messages):
        if len(detachments) < 2:
            return
        selected_ids = [item["id"] for item in detachments]
        placeholders = ",".join("?" for _ in selected_ids)
        rows = conn.execute(
            f"""
            select k.name as keywordName, d.name as detachmentName
            from detachment_unique_keyword duk
            join keyword k on k.id = duk.keywordId
            join detachment d on d.id = duk.detachmentId
            where duk.detachmentId in ({placeholders})
            order by k.name, d.name
            """,
            selected_ids,
        ).fetchall()
        by_keyword = {}
        for row in rows:
            by_keyword.setdefault(row["keywordName"], []).append(row["detachmentName"])
        for keyword, names in by_keyword.items():
            if len(names) > 1:
                messages.append({"level": "error", "text": f"Detachments share unique keyword {keyword}: {', '.join(names)}."})

    def validate_unit_compositions(self, conn, roster, detachments, units, messages):
        for unit in units:
            if unit.get("maxModelCount") and unit["modelCount"] > unit["maxModelCount"]:
                messages.append({"level": "error", "text": f"{unit['name']} has {unit['modelCount']} models; limit is {unit['maxModelCount']}."})
            if not unit["selectedCompositionId"]:
                messages.append({"level": "error", "text": f"{unit['name']} has an invalid unit composition."})
            elif not unit.get("selectedCompositionAvailable", True):
                messages.append({"level": "error", "text": f"{unit['name']} uses a composition that is not available to this faction or detachment."})

    def validate_successor_chapter_epic_heroes(self, units, messages):
        successor_units = [unit for unit in units if unit.get("isSuccessorChapter") and self.unit_has_keyword(unit, "epic hero")]
        if not successor_units:
            return
        epic_units = [unit for unit in units if self.unit_has_keyword(unit, "epic hero")]
        for successor in successor_units:
            shared = []
            successor_factions = set(successor.get("factionKeywordIds", []))
            for unit in epic_units:
                if unit["id"] == successor["id"]:
                    continue
                if successor_factions.intersection(unit.get("factionKeywordIds", [])):
                    shared.append(unit["name"])
            if shared:
                messages.append({"level": "error", "text": f"{successor['name']} cannot be included with other Epic Heroes from the same parent faction: {', '.join(shared)}."})

    def validate_allegiance_abilities(self, conn, roster, detachments, units, messages):
        detachment_ids = {detachment["id"] for detachment in detachments}
        group_counts = {}
        for unit in units:
            group_id = unit.get("allegianceAbilityGroupId")
            if not group_id:
                continue
            group = conn.execute(
                "select * from allegiance_ability_group where id = ?",
                [group_id],
            ).fetchone()
            if not group:
                continue
            if group["detachmentId"] and group["detachmentId"] not in detachment_ids:
                continue
            selected = [item for item in unit["allegianceAbilities"] if item["groupId"] == group_id]
            group_counts[group_id] = group_counts.get(group_id, 0) + len(selected)
            if group["isMandatory"] and not selected:
                messages.append({"level": "error", "text": f"{unit['name']} must select one {group['name']}."})
            if len(selected) > 1:
                messages.append({"level": "error", "text": f"{unit['name']} has too many {group['name']} selections."})
            for ability in selected:
                if ability["requiresWargearItemId"] and not self.unit_has_wargear_item(conn, unit["id"], ability["requiresWargearItemId"]):
                    item_name = self.wargear_item_name(conn, ability["requiresWargearItemId"])
                    messages.append({"level": "error", "text": f"{unit['name']} with {ability['name']} must be equipped with {item_name}."})

        rows = conn.execute(
            """
            select *
            from allegiance_ability_group
            where minRosterLimit is not null or maxRosterLimit is not null
            """
        ).fetchall()
        for group in rows:
            if group["detachmentId"] and group["detachmentId"] not in detachment_ids:
                continue
            count = group_counts.get(group["id"], 0)
            if group["minRosterLimit"] is not None and count < group["minRosterLimit"]:
                messages.append({"level": "error", "text": f"Select at least {group['minRosterLimit']} {group['name']} choices."})
            if group["maxRosterLimit"] is not None and count > group["maxRosterLimit"]:
                messages.append({"level": "error", "text": f"Select at most {group['maxRosterLimit']} {group['name']} choices."})

        self.validate_mandatory_faction_allegiance_abilities(conn, roster, units, messages)

    def validate_mandatory_faction_allegiance_abilities(self, conn, roster, units, messages):
        rows = conn.execute(
            """
            select aa.id, aa.name, aag.id as groupId, aag.name as groupName
            from faction_keyword_mandatory_allegiance_ability fkmaa
            join allegiance_ability aa on aa.id = fkmaa.allegianceAbilityId
            join allegiance_ability_group aag on aag.id = aa.allegianceAbilityGroupId
            where fkmaa.factionKeywordId = ?
            order by aag.name, aa.name
            """,
            [roster["factionKeywordId"]],
        ).fetchall()
        if not rows:
            return
        for unit in units:
            selected_ids = {item["id"] for item in unit.get("allegianceAbilities", [])}
            if not selected_ids:
                continue
            for row in rows:
                if row["groupId"] != unit.get("allegianceAbilityGroupId"):
                    continue
                if row["id"] not in selected_ids:
                    messages.append({"level": "error", "text": f"{unit['name']} must select {row['name']} for {roster['factionName']}."})

    def validate_allied_units(self, conn, roster, detachments, units, messages):
        allied_units = [unit for unit in units if unit.get("allyType", "native") != "native"]
        if not allied_units:
            return
        detachment_ids = {detachment["id"] for detachment in detachments}
        warlord_ids = {miniature_id for unit in units for miniature_id in unit.get("warlordMiniatureIds", [])}
        by_ally = {}
        for unit in allied_units:
            by_ally.setdefault(unit["allyType"], []).append(unit)
        for allied_faction_id, items in by_ally.items():
            label = self.allied_faction_name(conn, allied_faction_id)
            allowed = conn.execute(
                """
                select 1
                from faction_keyword_allied_faction
                where factionKeywordId = ? and alliedFactionId = ?
                """,
                [roster["factionKeywordId"], allied_faction_id],
            ).fetchone()
            if not allowed:
                messages.append({"level": "error", "text": f"{label} allies are not available to {roster['factionName']}."})
            allied_faction = conn.execute("select * from allied_faction where id = ?", [allied_faction_id]).fetchone()
            if allied_faction and allied_faction["requiredWarlordMiniatureId"] and allied_faction["requiredWarlordMiniatureId"] not in warlord_ids:
                name = self.miniature_name(conn, allied_faction["requiredWarlordMiniatureId"])
                messages.append({"level": "error", "text": f"Your Warlord must be {name} to include {label} allies."})
            allowed_warlords = [
                row["miniatureId"] for row in conn.execute(
                    """
                    select miniatureId
                    from allied_faction_allowed_warlord_miniature
                    where alliedFactionId = ?
                    """,
                    [allied_faction_id],
                )
            ]
            if allowed_warlords and not warlord_ids.intersection(allowed_warlords):
                names = ", ".join(self.miniature_names(conn, allowed_warlords))
                messages.append({"level": "error", "text": f"Your Warlord must be one of these models to include {label} allies: {names}."})
            required_detachments = []
            if allied_faction and allied_faction["requiredDetachmentId"]:
                required_detachments.append(allied_faction["requiredDetachmentId"])
            required_detachments.extend(
                row["detachmentId"] for row in conn.execute(
                    "select detachmentId from allied_faction_required_detachment where alliedFactionId = ?",
                    [allied_faction_id],
                )
            )
            required_detachments = list(dict.fromkeys(required_detachments))
            if required_detachments and not detachment_ids.intersection(required_detachments):
                names = self.detachment_names(conn, required_detachments)
                messages.append({"level": "error", "text": f"{label} allies require one of these detachments: {', '.join(names)}."})
            for unit in items:
                allowed_datasheet = conn.execute(
                    """
                    select 1
                    from allied_faction_datasheet
                    where alliedFactionId = ? and datasheetId = ?
                    """,
                    [allied_faction_id, unit["datasheetId"]],
                ).fetchone()
                if not allowed_datasheet:
                    messages.append({"level": "error", "text": f"{unit['name']} is not allowed for {label} allies."})
            points_limit = conn.execute(
                """
                select pointsLimit
                from allied_faction_points_limit
                where alliedFactionId = ? and battleSizeId = ?
                """,
                [allied_faction_id, roster.get("battleSizeId")],
            ).fetchone()
            if points_limit:
                total = sum(unit["points"] for unit in items)
                if total > points_limit["pointsLimit"]:
                    messages.append({"level": "error", "text": f"{label} allies use {total} points; limit is {points_limit['pointsLimit']}."})
            self.validate_allied_keyword_limits(conn, roster, allied_faction_id, label, items, warlord_ids, messages)
            self.validate_allied_required_allegiance_abilities(conn, allied_faction_id, label, items, messages)
            self.validate_ally_restricting_keywords(conn, label, items, messages)

    def validate_allied_required_allegiance_abilities(self, conn, allied_faction_id, label, units, messages):
        rows = conn.execute(
            """
            select aa.id, aa.name, aag.name as groupName
            from allied_faction_allegiance_ability afaa
            join allegiance_ability aa on aa.id = afaa.allegianceAbilityId
            join allegiance_ability_group aag on aag.id = aa.allegianceAbilityGroupId
            where afaa.alliedFactionId = ?
            order by aag.name, aa.name
            """,
            [allied_faction_id],
        ).fetchall()
        if not rows:
            return
        selected_ids = {
            ability["id"]
            for unit in units
            for ability in unit.get("allegianceAbilities", [])
        }
        for row in rows:
            if row["id"] not in selected_ids:
                messages.append({"level": "error", "text": f"{label} allies must select {row['name']} from {row['groupName']}."})

    def validate_ally_restricting_keywords(self, conn, label, units, messages):
        rows = conn.execute(
            """
            select kar.keywordId, k.name as keywordName,
                   kar.restrictingKeywordId, rk.name as restrictingKeywordName
            from keyword_ally_restricting_keyword kar
            join keyword k on k.id = kar.keywordId
            join keyword rk on rk.id = kar.restrictingKeywordId
            order by k.name, rk.name
            """
        ).fetchall()
        if not rows:
            return
        for row in rows:
            unrestricted = [
                unit for unit in units
                if row["keywordId"] in unit.get("keywordIds", [])
                and row["restrictingKeywordId"] not in unit.get("keywordIds", [])
            ]
            restricting = [
                unit for unit in units
                if row["keywordId"] in unit.get("keywordIds", [])
                and row["restrictingKeywordId"] in unit.get("keywordIds", [])
            ]
            if len(unrestricted) > len(restricting):
                messages.append({
                    "level": "error",
                    "text": (
                        f"{label} allies with {row['keywordName']} but not {row['restrictingKeywordName']} "
                        f"have {len(unrestricted)} units; limit is {len(restricting)}."
                    ),
                })

    def validate_allied_keyword_limits(self, conn, roster, allied_faction_id, label, units, warlord_ids, messages):
        rows = conn.execute(
            """
            select afk.*, k.name as keywordName
            from allied_faction_keyword afk
            join keyword k on k.id = afk.keywordId
            where afk.alliedFactionId = ?
              and (afk.battleSizeId is null or afk.battleSizeId = ?)
            """,
            [allied_faction_id, roster.get("battleSizeId")],
        ).fetchall()
        active_keyword_counts = 0
        for row in rows:
            if row["requiredWarlordMiniatureId"] and row["requiredWarlordMiniatureId"] not in warlord_ids:
                continue
            count = sum(1 for unit in units if row["keywordId"] in unit.get("keywordIds", []))
            count = max(0, count - self.slotless_allied_keyword_count(conn, row["id"], units))
            if count:
                active_keyword_counts += 1
            if count > row["limitCount"]:
                messages.append({"level": "error", "text": f"{label} allies with {row['keywordName']} have {count} units; limit is {row['limitCount']}."})
        mutually_exclusive = conn.execute(
            "select isMutuallyExclusiveKeywordLimit from allied_faction where id = ?",
            [allied_faction_id],
        ).fetchone()
        if mutually_exclusive and mutually_exclusive["isMutuallyExclusiveKeywordLimit"] and active_keyword_counts > 1:
            messages.append({"level": "error", "text": f"{label} allied keyword limits are mutually exclusive."})

    def slotless_allied_keyword_count(self, conn, allied_faction_keyword_id, units):
        groups = conn.execute(
            """
            select id
            from allied_faction_keyword_slotless_keyword_group
            where alliedFactionKeywordId = ?
            """,
            [allied_faction_keyword_id],
        ).fetchall()
        slotless = 0
        for group in groups:
            donor_keywords = {
                row["keywordId"] for row in conn.execute(
                    """
                    select keywordId
                    from allied_faction_keyword_slotless_keyword_group_donor_keyword
                    where alliedFactionKeywordSlotlessKeywordGroupId = ?
                    """,
                    [group["id"]],
                )
            }
            receiver_keywords = {
                row["keywordId"] for row in conn.execute(
                    """
                    select keywordId
                    from allied_faction_keyword_slotless_keyword_group_receiver_keyword
                    where alliedFactionKeywordSlotlessKeywordGroupId = ?
                    """,
                    [group["id"]],
                )
            }
            if not donor_keywords or not receiver_keywords:
                continue
            donor_count = sum(
                1 for unit in units
                if donor_keywords.issubset(set(unit.get("keywordIds", [])))
            )
            receiver_count = sum(
                1 for unit in units
                if receiver_keywords.issubset(set(unit.get("keywordIds", [])))
            )
            slotless += min(donor_count, receiver_count)
        return slotless

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

    def validate_attached_units(self, conn, roster, detachments, messages):
        rows = conn.execute(
            """
            select rau.id as attachedUnitId, rauru.rosterUnitId, rauru.attachmentType,
                   ru.datasheetId, d.name
            from roster_attached_unit rau
            join roster_attached_unit_roster_unit rauru on rauru.rosterAttachedUnitId = rau.id
            join roster_unit ru on ru.id = rauru.rosterUnitId
            join datasheet d on d.id = ru.datasheetId
            where rau.rosterId = ?
            order by rau.id, rauru.attachmentType
            """,
            [roster["id"]],
        ).fetchall()
        if not rows:
            return
        by_attached = {}
        for row in rows:
            by_attached.setdefault(row["attachedUnitId"], []).append(dict_row(row))
        detachment_ids = {item["id"] for item in detachments}
        for attached_id, members in by_attached.items():
            bodyguards = [item for item in members if item["attachmentType"] == "bodyguard"]
            attached_models = [item for item in members if item["attachmentType"] in ("leader", "support")]
            if not bodyguards or not attached_models:
                messages.append({"level": "error", "text": f"Attached unit {attached_id} is incomplete."})
                continue
            bodyguard = bodyguards[0]
            for attached in attached_models:
                if not self.attached_unit_can_attach(conn, roster, detachment_ids, attached, bodyguard):
                    messages.append({"level": "error", "text": f"{attached['name']} cannot attach to {bodyguard['name']} as {attached['attachmentType']}."})

    def unit_has_keyword(self, unit, keyword_name):
        keyword_name = keyword_name.lower()
        return any(name.lower() == keyword_name for name in unit.get("keywordNames", []))

    def keyword_name_in_ids(self, conn, keyword_ids, keyword_name):
        if not keyword_ids:
            return False
        placeholders = ",".join("?" for _ in keyword_ids)
        row = conn.execute(
            f"select 1 from keyword where id in ({placeholders}) and lower(name) = ? limit 1",
            [*keyword_ids, keyword_name.lower()],
        ).fetchone()
        return bool(row)

    def wargear_item_name(self, conn, wargear_item_id):
        row = conn.execute("select name from wargear_item where id = ?", [wargear_item_id]).fetchone()
        return row["name"] if row else "required wargear"

    def miniature_name(self, conn, miniature_id):
        row = conn.execute("select name from miniature where id = ?", [miniature_id]).fetchone()
        return row["name"] if row else "required model"

    def miniature_names(self, conn, miniature_ids):
        if not miniature_ids:
            return []
        placeholders = ",".join("?" for _ in miniature_ids)
        return [
            row["name"] for row in conn.execute(
                f"select name from miniature where id in ({placeholders}) order by name",
                miniature_ids,
            )
        ]

    def detachment_names(self, conn, detachment_ids):
        if not detachment_ids:
            return []
        placeholders = ",".join("?" for _ in detachment_ids)
        return [
            row["name"] for row in conn.execute(
                f"select name from detachment where id in ({placeholders}) order by name",
                detachment_ids,
            )
        ]

    def allied_faction_name(self, conn, allied_faction_id):
        row = conn.execute(
            """
            select group_concat(fk.name, ', ') as names
            from allied_faction_parent_faction_keyword afpfk
            join faction_keyword fk on fk.id = afpfk.factionKeywordId
            where afpfk.alliedFactionId = ?
            """,
            [allied_faction_id],
        ).fetchone()
        if row and row["names"]:
            return row["names"]
        return "Allied"

    def unit_has_wargear_item(self, conn, roster_unit_id, wargear_item_id):
        row = conn.execute(
            """
            select 1
            from roster_unit_wargear_option ruwo
            join wargear_option wo on wo.id = ruwo.wargearOptionId
            where ruwo.rosterUnitId = ?
              and wo.wargearItemId = ?
              and ruwo.count > 0
            union
            select 1
            from roster_unit_miniature_wargear_option rumwo
            join roster_unit_miniature rum on rum.id = rumwo.rosterUnitMiniatureId
            join wargear_option wo on wo.id = rumwo.wargearOptionId
            where rum.rosterUnitId = ?
              and wo.wargearItemId = ?
              and rumwo.count > 0
            limit 1
            """,
            [roster_unit_id, wargear_item_id, roster_unit_id, wargear_item_id],
        ).fetchone()
        return bool(row)

    def miniature_has_wargear_item(self, conn, roster_unit_miniature_id, wargear_item_id):
        row = conn.execute(
            """
            select 1
            from roster_unit_miniature_wargear_option rumwo
            join wargear_option wo on wo.id = rumwo.wargearOptionId
            where rumwo.rosterUnitMiniatureId = ?
              and wo.wargearItemId = ?
              and rumwo.count > 0
            limit 1
            """,
            [roster_unit_miniature_id, wargear_item_id],
        ).fetchone()
        return bool(row)

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
            if faction_ids and roster.get("factionKeywordId") not in faction_ids:
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

    def attached_unit_can_attach(self, conn, roster, detachment_ids, attached, bodyguard):
        rows = conn.execute(
            """
            select dbg.*
            from datasheet_bodyguard_group dbg
            where dbg.datasheetId = ?
              and dbg.bodyguardType = ?
            """,
            [attached["datasheetId"], attached["attachmentType"]],
        ).fetchall()
        for row in rows:
            if row["factionKeywordId"] and row["factionKeywordId"] != roster["factionKeywordId"]:
                continue
            if row["excludedDetachmentId"] and row["excludedDetachmentId"] in detachment_ids:
                continue
            if row["requiredDetachmentId"] and row["requiredDetachmentId"] not in detachment_ids:
                continue
            datasheets = {
                item["datasheetId"] for item in conn.execute(
                    "select datasheetId from datasheet_bodyguard_group_datasheet where datasheetBodyguardGroupId = ?",
                    [row["id"]],
                )
            }
            keyword_ids = {
                item["keywordId"] for item in conn.execute(
                    "select keywordId from datasheet_bodyguard_group_keyword where datasheetBodyguardGroupId = ?",
                    [row["id"]],
                )
            }
            if datasheets and bodyguard["datasheetId"] not in datasheets:
                continue
            if keyword_ids:
                bodyguard_keywords = self.unit_keywords(conn, bodyguard["rosterUnitId"], bodyguard["datasheetId"], roster, detachment_ids, [])
                bodyguard_keyword_ids = {item["id"] for item in bodyguard_keywords}
                if not keyword_ids.intersection(bodyguard_keyword_ids):
                    continue
            if row["requiresAllUnitsHaveKeywordId"]:
                attached_keywords = {item["id"] for item in self.unit_keywords(conn, attached["rosterUnitId"], attached["datasheetId"], roster, detachment_ids, [])}
                bodyguard_keywords = {item["id"] for item in self.unit_keywords(conn, bodyguard["rosterUnitId"], bodyguard["datasheetId"], roster, detachment_ids, [])}
                required = row["requiresAllUnitsHaveKeywordId"]
                if required not in attached_keywords or required not in bodyguard_keywords:
                    continue
            return True
        return False

    def validate_warlord(self, conn, roster, detachments, units, messages):
        warlord_units = [unit for unit in units if unit.get("isWarlord")]
        warlord_ids = [miniature_id for unit in warlord_units for miniature_id in unit.get("warlordMiniatureIds", [])]
        if not units:
            return
        mandatory_faction_warlord = conn.execute(
            """
            select m.id, m.name
            from faction_keyword fk
            join miniature m on m.id = fk.mandatoryWarlordId
            where fk.id = ? and fk.mandatoryWarlordId is not null
            """,
            [roster["factionKeywordId"]],
        ).fetchone()
        if mandatory_faction_warlord:
            mandatory_present = any(
                miniature["miniatureId"] == mandatory_faction_warlord["id"]
                for unit in units
                for miniature in unit.get("miniatures", [])
            )
            if not mandatory_present:
                messages.append({"level": "error", "text": f"{roster['factionName']} requires {mandatory_faction_warlord['name']} in your army."})
            elif not warlord_ids:
                messages.append({"level": "error", "text": f"{roster['factionName']} requires {mandatory_faction_warlord['name']} as Warlord."})
        if not warlord_ids:
            if not mandatory_faction_warlord:
                messages.append({"level": "error", "text": "Pick one Warlord."})
            return
        if len(warlord_ids) > 1:
            messages.append({"level": "error", "text": "Roster has more than one Warlord."})

        detachment_ids = [detachment["id"] for detachment in detachments]
        selected_warlord_id = warlord_ids[0]
        supreme_commanders = []
        for unit in units:
            supreme_commanders.extend(
                miniature for miniature in unit["miniatures"] if miniature.get("isSupremeCommander")
            )
        if supreme_commanders and selected_warlord_id not in {item["miniatureId"] for item in supreme_commanders}:
            messages.append({"level": "error", "text": "One of the Supreme Commander units must be your Warlord."})

        if detachment_ids:
            placeholders = ",".join("?" for _ in detachment_ids)
            mandatory = conn.execute(
                f"""
                select m.id, m.name, d.name as detachmentName
                from detachment_mandatory_warlord_miniature dm
                join miniature m on m.id = dm.miniatureId
                join detachment d on d.id = dm.detachmentId
                where dm.detachmentId in ({placeholders})
                order by d.name, m.name
                """,
                detachment_ids,
            ).fetchall()
            if mandatory and selected_warlord_id not in {row["id"] for row in mandatory}:
                names = ", ".join(row["name"] for row in mandatory)
                messages.append({"level": "error", "text": f"{mandatory[0]['detachmentName']} requires one of these Warlords: {names}."})

        if mandatory_faction_warlord and selected_warlord_id != mandatory_faction_warlord["id"]:
            messages.append({"level": "error", "text": f"{roster['factionName']} requires {mandatory_faction_warlord['name']} as Warlord."})

        selected_unit = next((unit for unit in units if selected_warlord_id in unit.get("warlordMiniatureIds", [])), None)
        selected_miniature = None
        if selected_unit:
            selected_miniature = next(
                (miniature for miniature in selected_unit["miniatures"] if miniature["miniatureId"] == selected_warlord_id),
                None,
            )
        conditional_character = False
        if selected_unit:
            conditional_character = self.conditional_keyword_applies(
                conn,
                selected_unit["datasheetId"],
                "Character",
                roster,
                detachment_ids,
                [item["id"] for item in selected_unit.get("allegianceAbilities", [])],
                warlord_ids,
            )
        if selected_unit and selected_miniature and not self.can_be_warlord(
            conn,
            selected_warlord_id,
            selected_miniature["cannotBeWarlord"],
            selected_miniature["canBeNonCharacterWarlord"],
            detachment_ids,
            conditional_character,
        ):
            messages.append({"level": "error", "text": "Selected Warlord is not eligible."})

    def validate_detachment_datasheets(self, conn, roster, detachments, units, messages):
        counts = {}
        for unit in units:
            counts[unit["datasheetId"]] = counts.get(unit["datasheetId"], 0) + 1
        for detachment in detachments:
            for unit in units:
                excluded = conn.execute(
                    """
                    select 1
                    from detachment_excluded_datasheet
                    where detachmentId = ? and datasheetId = ?
                    """,
                    [detachment["id"], unit["datasheetId"]],
                ).fetchone()
                if excluded:
                    messages.append({"level": "error", "text": f"{unit['name']} is excluded from {detachment['name']}."})
            required_rows = conn.execute(
                """
                select d.id, d.name
                from detachment_required_datasheet drd
                join datasheet d on d.id = drd.datasheetId
                where drd.detachmentId = ?
                order by d.name
                """,
                [detachment["id"]],
            ).fetchall()
            for required in required_rows:
                if counts.get(required["id"], 0) == 0:
                    messages.append({"level": "error", "text": f"{detachment['name']} requires {required['name']}."})

    def validate_keyword_restrictions(self, conn, roster, detachments, units, messages):
        groups = self.keyword_restriction_groups(conn, roster["factionKeywordId"])
        warlord_ids = {miniature_id for unit in units for miniature_id in unit.get("warlordMiniatureIds", [])}
        for group in groups.values():
            if group["requiresWarlordMiniatureId"] and group["requiresWarlordMiniatureId"] not in warlord_ids:
                continue
            if not self.keyword_restriction_group_is_active(units, group):
                continue
            count = self.count_keyword_restricted_units(units, group)
            if group["limit"] is not None and count > group["limit"]:
                self.add_keyword_limit_message(messages, group, count, group["limit"], None)

        detachment_ids = [detachment["id"] for detachment in detachments]
        if not detachment_ids:
            return
        placeholders = ",".join("?" for _ in detachment_ids)
        rows = conn.execute(
            f"""
            select rgdl.restrictionGroupId, rgdl.minRosterLimit, rgdl.maxRosterLimit,
                   d.name as detachmentName
            from restriction_group_detachment_limit rgdl
            join detachment d on d.id = rgdl.detachmentId
            where rgdl.detachmentId in ({placeholders})
            """,
            detachment_ids,
        ).fetchall()
        for row in rows:
            group = groups.get(row["restrictionGroupId"])
            if not group:
                group = self.keyword_restriction_group(conn, row["restrictionGroupId"])
            if not group:
                continue
            if not self.keyword_restriction_group_is_active(units, group):
                continue
            count = self.count_keyword_restricted_units(units, group)
            if row["minRosterLimit"] is not None and count < row["minRosterLimit"]:
                labels = ", ".join(group["keywordNames"])
                messages.append({"level": "error", "text": f"{row['detachmentName']} requires at least {row['minRosterLimit']} {labels} unit(s)."})
            if row["maxRosterLimit"] is not None and count > row["maxRosterLimit"]:
                self.add_keyword_limit_message(messages, group, count, row["maxRosterLimit"], row["detachmentName"])

    def keyword_restriction_groups(self, conn, faction_keyword_id):
        rows = conn.execute(
            """
            select id, "limit", requiresWarlordMiniatureId, excludedFactionKeywordId
            from keyword_restriction_group
            where factionKeywordId = ?
            """,
            [faction_keyword_id],
        ).fetchall()
        return {row["id"]: self.keyword_restriction_group_from_row(conn, row) for row in rows}

    def keyword_restriction_group(self, conn, group_id):
        row = conn.execute(
            """
            select id, "limit", requiresWarlordMiniatureId, excludedFactionKeywordId
            from keyword_restriction_group
            where id = ?
            """,
            [group_id],
        ).fetchone()
        return self.keyword_restriction_group_from_row(conn, row) if row else None

    def keyword_restriction_group_from_row(self, conn, row):
        keywords = [dict_row(item) for item in conn.execute(
            """
            select k.id, k.name
            from keyword_restriction_group_keyword krgk
            join keyword k on k.id = krgk.keywordId
            where krgk.keywordRestrictionGroupId = ?
            order by k.name
            """,
            [row["id"]],
        )]
        excluded_name = None
        if row["excludedFactionKeywordId"]:
            excluded = conn.execute(
                "select name from faction_keyword where id = ?",
                [row["excludedFactionKeywordId"]],
            ).fetchone()
            excluded_name = excluded["name"] if excluded else None
        return {
            "id": row["id"],
            "limit": row["limit"],
            "requiresWarlordMiniatureId": row["requiresWarlordMiniatureId"],
            "excludedFactionKeywordId": row["excludedFactionKeywordId"],
            "excludedFactionKeywordName": excluded_name,
            "keywordIds": {item["id"] for item in keywords},
            "keywordNames": [item["name"] for item in keywords],
        }

    def keyword_restriction_group_is_active(self, units, group):
        return True

    def count_keyword_restricted_units(self, units, group):
        count = 0
        for unit in units:
            if group["excludedFactionKeywordId"] and group["excludedFactionKeywordId"] in unit.get("factionKeywordIds", []):
                continue
            unit_keyword_ids = set(unit.get("keywordIds", []))
            if unit_keyword_ids.intersection(group["keywordIds"]):
                count += 1
        return count

    def add_keyword_limit_message(self, messages, group, count, limit, detachment_name):
        labels = ", ".join(group["keywordNames"])
        scope = f" in {detachment_name}" if detachment_name else ""
        excluded = group.get("excludedFactionKeywordName")
        prefix = f"Excluding {excluded} units, " if excluded else ""
        if limit == 0:
            messages.append({"level": "error", "text": f"{prefix}{labels} units are not allowed{scope}."})
        else:
            messages.append({"level": "error", "text": f"{prefix}{labels} has {count} units{scope}; limit is {limit}."})
