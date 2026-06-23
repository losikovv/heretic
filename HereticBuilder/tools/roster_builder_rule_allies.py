class RosterAlliedRulesMixin:
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
            self.validate_ally_restricting_keywords(conn, allied_faction_id, label, items, messages)

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

    def validate_ally_restricting_keywords(self, conn, allied_faction_id, label, units, messages):
        rows = conn.execute(
            """
            select distinct keywordId, keywordName, restrictingKeywordId, restrictingKeywordName
            from (
                select kar.keywordId, k.name as keywordName,
                       kar.restrictingKeywordId, rk.name as restrictingKeywordName
                from keyword_ally_restricting_keyword kar
                join keyword k on k.id = kar.keywordId
                join keyword rk on rk.id = kar.restrictingKeywordId

                union all

                select k.id as keywordId, k.name as keywordName,
                       k.allyRestrictingKeywordId as restrictingKeywordId,
                       rk.name as restrictingKeywordName
                from keyword k
                join keyword rk on rk.id = k.allyRestrictingKeywordId
                join allied_faction_parent_faction_keyword afpfk
                  on afpfk.factionKeywordId = k.allyRestrictingFactionKeywordId
                where afpfk.alliedFactionId = ?
            )
            order by keywordName, restrictingKeywordName
            """,
            [allied_faction_id],
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
