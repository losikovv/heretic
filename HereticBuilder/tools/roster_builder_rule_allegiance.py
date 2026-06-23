class RosterAllegianceRulesMixin:
    def validate_allegiance_abilities(self, conn, roster, detachments, units, messages):
        detachment_ids = {detachment["id"] for detachment in detachments}
        group_counts = {}
        for unit in units:
            group_id = unit.get("allegianceAbilityGroupId")
            selected_abilities = unit.get("allegianceAbilities", [])
            if not group_id:
                for ability in selected_abilities:
                    messages.append({"level": "error", "text": f"{unit['name']} cannot select {ability['name']} from {ability['groupName']}."})
                continue
            group = conn.execute(
                "select * from allegiance_ability_group where id = ?",
                [group_id],
            ).fetchone()
            if not group:
                continue
            if group["detachmentId"] and group["detachmentId"] not in detachment_ids:
                for ability in selected_abilities:
                    if ability["groupId"] == group_id:
                        messages.append({"level": "error", "text": f"{unit['name']} cannot select {ability['name']} without its required detachment."})
                continue
            for ability in selected_abilities:
                if ability["groupId"] != group_id:
                    messages.append({"level": "error", "text": f"{unit['name']} cannot select {ability['name']} from {ability['groupName']}."})
            selected = [item for item in selected_abilities if item["groupId"] == group_id]
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
