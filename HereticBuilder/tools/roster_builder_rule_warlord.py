class RosterWarlordRulesMixin:
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
