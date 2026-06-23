from roster_builder_utils import dict_row

class RosterRestrictionRulesMixin:
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
            if detachment.get("isCombatPatrol"):
                linked_rows = conn.execute(
                    """
                    select dld.datasheetId, dld.count, d.name
                    from detachment_linked_datasheet dld
                    join datasheet d on d.id = dld.datasheetId
                    where dld.detachmentId = ?
                    order by d.name
                    """,
                    [detachment["id"]],
                ).fetchall()
                if not linked_rows:
                    continue
                linked_counts = {row["datasheetId"]: row["count"] for row in linked_rows}
                for linked in linked_rows:
                    actual = counts.get(linked["datasheetId"], 0)
                    if actual != linked["count"]:
                        messages.append({
                            "level": "error",
                            "text": (
                                f"{detachment['name']} requires exactly "
                                f"{linked['count']} {linked['name']} unit(s); roster has {actual}."
                            ),
                        })
                for unit in units:
                    if unit["datasheetId"] not in linked_counts:
                        messages.append({"level": "error", "text": f"{unit['name']} is not part of {detachment['name']}."})

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
