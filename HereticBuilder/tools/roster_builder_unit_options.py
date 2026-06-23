from roster_builder_utils import dict_row, plain_text

class RosterUnitOptionsMixin:
    def allegiance_options(self, conn, roster_unit_id, summary):
        group_id = summary.get("allegianceAbilityGroupId")
        if not group_id:
            return None
        group = conn.execute(
            "select * from allegiance_ability_group where id = ?",
            [group_id],
        ).fetchone()
        if not group:
            return None
        selected_ids = {item["id"] for item in summary.get("allegianceAbilities", [])}
        abilities = [
            {
                **dict_row(row),
                "rules": plain_text(row["rules"])[:360],
                "selected": row["id"] in selected_ids,
            }
            for row in conn.execute(
                """
                select *
                from allegiance_ability
                where allegianceAbilityGroupId = ?
                order by displayOrder, name
                """,
                [group_id],
            )
        ]
        return {
            "group": dict_row(group),
            "abilities": abilities,
        }

    def enhancement_options(self, conn, roster, detachment_ids, summary, miniatures):
        unit_selected = {item["id"] for item in summary.get("unitEnhancements", [])}
        miniature_selected = {}
        for enhancement in summary.get("miniatureEnhancements", []):
            miniature_selected.setdefault(enhancement["targetId"], set()).add(enhancement["id"])
        selected_ids = set(unit_selected)
        for ids in miniature_selected.values():
            selected_ids.update(ids)
        rows = self.available_enhancement_rows(conn, detachment_ids, selected_ids)
        unit_target = {
            "id": summary["id"],
            "name": summary["name"],
            "kind": "unit",
            "keywordIds": set(summary.get("keywordIds", [])),
            "selectedIds": unit_selected,
            "miniature": None,
        }
        unit_options = self.enhancement_target_options(conn, roster, summary, rows, unit_target)
        miniature_options = []
        for miniature in miniatures:
            target = {
                "id": miniature["id"],
                "name": miniature["name"],
                "kind": "miniature",
                "keywordIds": self.miniature_keyword_ids(conn, miniature["miniatureId"]),
                "selectedIds": miniature_selected.get(miniature["id"], set()),
                "miniature": miniature,
            }
            miniature_options.append({
                "rosterUnitMiniatureId": miniature["id"],
                "miniatureId": miniature["miniatureId"],
                "name": miniature["name"],
                "count": miniature["count"],
                "options": self.enhancement_target_options(conn, roster, summary, rows, target),
            })
        return {
            "unit": unit_options,
            "miniatures": miniature_options,
        }

    def available_enhancement_rows(self, conn, detachment_ids, selected_ids=None):
        params = []
        detachment_filter = "e.detachmentId is null"
        if detachment_ids:
            placeholders = ",".join("?" for _ in detachment_ids)
            detachment_filter = f"(e.detachmentId is null or e.detachmentId in ({placeholders}))"
            params.extend(detachment_ids)
        selected_ids = list(selected_ids or [])
        if selected_ids:
            placeholders = ",".join("?" for _ in selected_ids)
            detachment_filter = f"({detachment_filter} or e.id in ({placeholders}))"
            params.extend(selected_ids)
        return conn.execute(
            f"""
            select e.*, d.name as detachmentName
            from enhancement e
            left join detachment d on d.id = e.detachmentId
            where {detachment_filter}
            order by d.displayOrder, e.displayOrder, e.name
            """,
            params,
        ).fetchall()

    def enhancement_target_options(self, conn, roster, unit, rows, target):
        options = []
        target_keyword_ids = set(target["keywordIds"])
        for row in rows:
            if target["kind"] == "unit" and row["enhancementType"] == "miniature":
                continue
            if target["kind"] == "miniature" and row["enhancementType"] != "miniature":
                continue
            reasons = self.enhancement_unavailable_reasons(conn, roster, unit, row, target, target_keyword_ids)
            options.append({
                "id": row["id"],
                "name": row["name"],
                "rules": plain_text(row["rules"])[:360],
                "points": self.enhancement_points(conn, row["id"], target_keyword_ids),
                "detachmentId": row["detachmentId"],
                "detachmentName": row["detachmentName"],
                "enhancementType": row["enhancementType"],
                "selected": row["id"] in target["selectedIds"],
                "selectable": not reasons,
                "reasons": reasons,
            })
        return options

    def enhancement_unavailable_reasons(self, conn, roster, unit, enhancement, target, keyword_ids):
        reasons = []
        miniature = target["miniature"]
        if unit.get("allyType", "native") != "native":
            allied_faction = conn.execute(
                "select canTakeEnhancements from allied_faction where id = ?",
                [unit["allyType"]],
            ).fetchone()
            if allied_faction and not allied_faction["canTakeEnhancements"]:
                reasons.append("Allied unit cannot take enhancements")
        if miniature and miniature.get("count", 0) <= 0:
            reasons.append("Model count is 0")
        if miniature and miniature.get("excludedFromEnhancements"):
            reasons.append("Model cannot take enhancements")
        if not enhancement["isEquipableByEpicHero"] and self.keyword_name_in_ids(conn, keyword_ids, "Epic Hero"):
            reasons.append("Epic Hero is excluded")
        if not enhancement["isEquipableByNonCharacterUnit"] and not self.keyword_name_in_ids(conn, keyword_ids, "Character"):
            reasons.append("Requires Character")
        if not self.enhancement_required_keywords_satisfied(conn, enhancement["id"], unit, keyword_ids, roster):
            reasons.append("Required keywords missing")
        excluded = self.enhancement_excluded_keyword_names(conn, enhancement["id"], keyword_ids)
        if excluded:
            reasons.append("Excluded keyword: " + ", ".join(excluded))
        required_wargear = [
            row["wargearItemId"] for row in conn.execute(
                "select wargearItemId from enhancement_required_wargear_item where enhancementId = ?",
                [enhancement["id"]],
            )
        ]
        for wargear_item_id in required_wargear:
            if miniature:
                has_wargear = self.miniature_has_wargear_item(conn, miniature["id"], wargear_item_id)
            else:
                has_wargear = self.unit_has_wargear_item(conn, unit["id"], wargear_item_id)
            if not has_wargear:
                reasons.append("Requires " + self.wargear_item_name(conn, wargear_item_id))
        if not self.enhancement_bodyguard_requirement_satisfied(conn, roster["id"], unit["id"], enhancement["id"]):
            reasons.append("Attached-unit requirement missing")
        if enhancement["cannotBeWarlord"] and unit.get("isWarlord"):
            reasons.append("Cannot be used by the Warlord")
        return reasons

    def attachment_options(self, conn, roster, detachment_ids, summary):
        attached_groups = [
            group for group in self.roster_attachment_groups(conn, roster["id"])
            if any(member["rosterUnitId"] == summary["id"] for member in group["members"])
        ]
        unit_rows = [
            dict_row(row) for row in conn.execute(
                """
                select ru.id as rosterUnitId, ru.datasheetId, d.name
                from roster_unit ru
                join datasheet d on d.id = ru.datasheetId
                where ru.rosterId = ?
                order by d.name, ru.id
                """,
                [roster["id"]],
            )
        ]
        current = {
            "rosterUnitId": summary["id"],
            "datasheetId": summary["datasheetId"],
            "name": summary["name"],
        }
        candidates = []
        for other in unit_rows:
            if other["rosterUnitId"] == summary["id"]:
                continue
            for attached_type in ("leader", "support"):
                attached = {**current, "attachmentType": attached_type}
                if self.attached_unit_can_attach(conn, roster, detachment_ids, attached, other):
                    candidates.append({
                        "bodyguardUnitId": other["rosterUnitId"],
                        "attachedUnitId": summary["id"],
                        "attachedType": attached_type,
                        "label": f"{summary['name']} as {attached_type} -> {other['name']}",
                    })
                other_attached = {**other, "attachmentType": attached_type}
                if self.attached_unit_can_attach(conn, roster, detachment_ids, other_attached, current):
                    candidates.append({
                        "bodyguardUnitId": summary["id"],
                        "attachedUnitId": other["rosterUnitId"],
                        "attachedType": attached_type,
                        "label": f"{other['name']} as {attached_type} -> {summary['name']}",
                    })
        return {
            "groups": attached_groups,
            "candidates": candidates,
        }

    def roster_attachment_groups(self, conn, roster_id):
        rows = conn.execute(
            """
            select rau.id as attachedUnitId, rauru.attachmentType,
                   ru.id as rosterUnitId, d.name
            from roster_attached_unit rau
            join roster_attached_unit_roster_unit rauru on rauru.rosterAttachedUnitId = rau.id
            join roster_unit ru on ru.id = rauru.rosterUnitId
            join datasheet d on d.id = ru.datasheetId
            where rau.rosterId = ?
            order by rau.id, rauru.attachmentType, d.name
            """,
            [roster_id],
        ).fetchall()
        groups = []
        by_id = {}
        for row in rows:
            group = by_id.get(row["attachedUnitId"])
            if not group:
                group = {"id": row["attachedUnitId"], "members": []}
                by_id[row["attachedUnitId"]] = group
                groups.append(group)
            group["members"].append(dict_row(row))
        return groups

    def unit_detail(self, roster_unit_id):
        with self.connect(readonly=True) as conn:
            row = conn.execute(
                """
                select ru.id, ru.datasheetId, ru.allyType, d.name
                from roster_unit ru
                join datasheet d on d.id = ru.datasheetId
                where ru.id = ?
                """,
                [roster_unit_id],
            ).fetchone()
            if not row:
                raise ValueError("Unit not found")
            roster_id = conn.execute(
                "select rosterId from roster_unit where id = ?",
                [roster_unit_id],
            ).fetchone()["rosterId"]
            roster = conn.execute(
                """
                select r.*, fk.name as factionName, bs.name as battleSizeName,
                       bs.pointsLimit, bs.detachmentPointsLimit,
                       bs.enhancementLimit, bs.duplicateUnitLimit
                from roster r
                join faction_keyword fk on fk.id = r.factionKeywordId
                left join battle_size bs on bs.id = r.battleSizeId
                where r.id = ?
                """,
                [roster_id],
            ).fetchone()
            detachment_ids = self.roster_detachment_ids(conn, roster_id)
            roster_dict = dict_row(roster)
            summary = self.unit_summary(conn, dict_row(row), roster_dict, detachment_ids)
            compositions = self.compositions(conn, row["datasheetId"], roster_dict, detachment_ids)
            miniature_rows = conn.execute(
                """
                select rum.id, rum.count, rum.isWarlord,
                       m.id as miniatureId, m.name, m.movement, m.toughness, m.save,
                       m.wounds, m.leadership, m.objectiveControl, m.statlineHidden,
                       m.isSupremeCommander, m.cannotBeWarlord,
                       m.excludedFromEnhancements, m.datasheetId, m.displayOrder,
                       m.isIndividualModels, m.canBeNonCharacterWarlord,
                       m.miniatureSlots
                from roster_unit_miniature rum
                join miniature m on m.id = rum.miniatureId
                where rum.rosterUnitId = ?
                order by m.displayOrder, m.name
                """,
                [roster_unit_id],
            ).fetchall()
            miniatures = []
            current_warlord_miniature_ids = set(self.roster_warlord_miniature_ids(conn, roster_id))
            for miniature in miniature_rows:
                item = dict_row(miniature)
                candidate_warlord_miniature_ids = set(current_warlord_miniature_ids)
                if item["count"] > 0:
                    candidate_warlord_miniature_ids.add(item["miniatureId"])
                conditional_character = self.conditional_keyword_applies(
                    conn,
                    row["datasheetId"],
                    "Character",
                    roster_dict,
                    detachment_ids,
                    [ability["id"] for ability in summary.get("allegianceAbilities", [])],
                    candidate_warlord_miniature_ids,
                )
                item["canBeWarlord"] = item["count"] > 0 and self.can_be_warlord(
                    conn,
                    item["miniatureId"],
                    item["cannotBeWarlord"],
                    item["canBeNonCharacterWarlord"],
                    detachment_ids,
                    conditional_character,
                )
                item["groups"] = self.wargear_groups(conn, row["datasheetId"], item["id"], item["miniatureId"])
                miniatures.append(item)
            unit_wargear_groups = self.unit_wargear_groups(conn, roster_unit_id, row["datasheetId"])
            allegiance_options = self.allegiance_options(conn, roster_unit_id, summary)
            enhancement_options = self.enhancement_options(conn, roster_dict, detachment_ids, summary, miniatures)
            attachment_options = self.attachment_options(conn, roster_dict, detachment_ids, summary)
        return {
            "summary": summary,
            "compositions": compositions,
            "unitWargearGroups": unit_wargear_groups,
            "miniatures": miniatures,
            "allegianceOptions": allegiance_options,
            "enhancementOptions": enhancement_options,
            "attachmentOptions": attachment_options,
        }

    def unit_wargear_groups(self, conn, roster_unit_id, datasheet_id):
        rows = conn.execute(
            """
            select wog.id as groupId, wog.instructionText, wog.displayOrder as groupOrder,
                   wo.id, wo.inputType, wo.defaultValue, wo.points, wo.displayOrder,
                   wi.name,
                   coalesce(ruwo.count, 0) as selectedCount
            from wargear_option_group wog
            join wargear_option wo on wo.wargearOptionGroupId = wog.id
            join wargear_item wi on wi.id = wo.wargearItemId
            left join roster_unit_wargear_option ruwo
              on ruwo.wargearOptionId = wo.id and ruwo.rosterUnitId = ?
            where wog.datasheetId = ?
              and wog.miniatureId is null
            order by wog.displayOrder, wo.displayOrder, wi.name
            """,
            [roster_unit_id, datasheet_id],
        ).fetchall()
        return self.group_wargear_rows(rows)

    def wargear_groups(self, conn, datasheet_id, roster_miniature_id, miniature_id):
        rows = conn.execute(
            """
            select wog.id as groupId, wog.instructionText, wog.displayOrder as groupOrder,
                   wo.id, wo.inputType, wo.defaultValue, wo.points, wo.displayOrder,
                   wi.name,
                   coalesce(rumwo.count, 0) as selectedCount
            from wargear_option_group wog
            join wargear_option wo on wo.wargearOptionGroupId = wog.id
            join wargear_item wi on wi.id = wo.wargearItemId
            left join roster_unit_miniature_wargear_option rumwo
              on rumwo.wargearOptionId = wo.id and rumwo.rosterUnitMiniatureId = ?
            where wog.datasheetId = ?
              and wog.miniatureId = ?
            order by wog.displayOrder, wo.displayOrder, wi.name
            """,
            [roster_miniature_id, datasheet_id, miniature_id],
        ).fetchall()
        return self.group_wargear_rows(rows)

    def group_wargear_rows(self, rows):
        groups = []
        by_id = {}
        for row in rows:
            group_id = row["groupId"]
            if group_id not in by_id:
                group = {
                    "id": group_id,
                    "instructionText": row["instructionText"],
                    "options": [],
                }
                by_id[group_id] = group
                groups.append(group)
            by_id[group_id]["options"].append({
                "id": row["id"],
                "name": row["name"],
                "inputType": row["inputType"],
                "defaultValue": row["defaultValue"],
                "points": row["points"],
                "selectedCount": row["selectedCount"],
            })
        return groups
