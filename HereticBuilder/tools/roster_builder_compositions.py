from roster_builder_utils import (
    composition_label,
    composition_label_from_current,
    dict_row,
    new_id,
    select_matching_composition,
)

class RosterCompositionMixin:
    def default_composition(self, conn, datasheet_id, faction_keyword_id=None, detachment_ids=None):
        for comp in self.compositions(conn, datasheet_id, {"factionKeywordId": faction_keyword_id}, detachment_ids or []):
            if self.composition_is_available(comp, faction_keyword_id, detachment_ids or []):
                return comp
        return None

    def compositions(self, conn, datasheet_id, roster=None, detachment_ids=None):
        rows = conn.execute(
            """
            select *
            from unit_composition
            where datasheetId = ?
            order by isDefault desc, displayOrder
            """,
            [datasheet_id],
        ).fetchall()
        result = []
        for row in rows:
            comp = dict_row(row)
            models = [dict_row(model) for model in conn.execute(
                """
                select ucm.*, m.name
                from unit_composition_miniature ucm
                join miniature m on m.id = ucm.miniatureId
                where ucm.unitCompositionId = ?
                order by m.displayOrder, m.name
                """,
                [comp["id"]],
            )]
            comp["models"] = models
            comp["label"] = composition_label(models)
            comp["requiredFactionKeywordIds"] = [
                item["factionKeywordId"] for item in conn.execute(
                    "select factionKeywordId from unit_composition_required_faction_keyword where unitCompositionId = ?",
                    [comp["id"]],
                )
            ]
            comp["requiredDetachmentIds"] = [
                item["detachmentId"] for item in conn.execute(
                    "select detachmentId from unit_composition_required_detachment where unitCompositionId = ?",
                    [comp["id"]],
                )
            ]
            comp["available"] = self.composition_is_available(
                comp,
                (roster or {}).get("factionKeywordId"),
                detachment_ids or [],
            )
            result.append(comp)
        return result

    def composition_is_available(self, comp, faction_keyword_id, detachment_ids):
        if comp.get("requiredFactionKeywordIds") and faction_keyword_id not in comp["requiredFactionKeywordIds"]:
            return False
        if comp.get("requiredDetachmentIds") and not set(comp["requiredDetachmentIds"]).intersection(detachment_ids):
            return False
        return True

    def apply_composition(self, conn, roster_unit_id, composition_id):
        unit = conn.execute("select datasheetId from roster_unit where id = ?", [roster_unit_id]).fetchone()
        if not unit:
            raise ValueError("Unit not found")
        models = conn.execute(
            """
            select ucm.*, m.name
            from unit_composition_miniature ucm
            join miniature m on m.id = ucm.miniatureId
            where ucm.unitCompositionId = ?
            order by m.displayOrder, m.name
            """,
            [composition_id],
        ).fetchall()
        if not models:
            raise ValueError("Composition has no models")
        conn.execute("delete from roster_unit_miniature where rosterUnitId = ?", [roster_unit_id])
        conn.execute("delete from roster_unit_wargear_option where rosterUnitId = ?", [roster_unit_id])
        for model in models:
            roster_miniature_id = new_id()
            conn.execute(
                """
                insert into roster_unit_miniature
                  (id, count, miniatureId, rosterUnitId, isWarlord)
                values (?, ?, ?, ?, 0)
                """,
                [roster_miniature_id, model["min"], model["miniatureId"], roster_unit_id],
            )
            self.apply_base_loadout(
                conn,
                roster_miniature_id,
                unit["datasheetId"],
                model["miniatureId"],
                model["min"],
            )
        self.apply_unit_default_wargear(conn, roster_unit_id, unit["datasheetId"])

    def apply_unit_default_wargear(self, conn, roster_unit_id, datasheet_id):
        options = conn.execute(
            """
            select wo.id as wargearOptionId, wo.defaultValue as count
            from wargear_option_group wog
            join wargear_option wo on wo.wargearOptionGroupId = wog.id
            where wog.datasheetId = ?
              and wog.miniatureId is null
              and wo.defaultValue > 0
            """,
            [datasheet_id],
        ).fetchall()
        for option in options:
            conn.execute(
                """
                insert or replace into roster_unit_wargear_option
                  (rosterUnitId, wargearOptionId, count)
                values (?, ?, ?)
                """,
                [roster_unit_id, option["wargearOptionId"], option["count"]],
            )

    def apply_base_loadout(self, conn, roster_miniature_id, datasheet_id, miniature_id, model_count=1):
        loadout = conn.execute(
            """
            select id
            from base_miniature_loadout
            where miniatureId = ?
            order by case when datasheetId = ? then 0 else 1 end
            limit 1
            """,
            [miniature_id, datasheet_id],
        ).fetchone()
        if not loadout:
            loadout = conn.execute(
                """
                select id
                from base_miniature_loadout
                where datasheetId = ? and miniatureId is null
                limit 1
                """,
                [datasheet_id],
            ).fetchone()
        if not loadout:
            self.apply_miniature_default_wargear(conn, roster_miniature_id, datasheet_id, miniature_id)
            return
        options = conn.execute(
            """
            select wargearOptionId, count
            from base_miniature_loadout_wargear_option
            where baseMiniatureLoadoutId = ?
            """,
            [loadout["id"]],
        ).fetchall()
        for option in options:
            conn.execute(
                """
                insert or replace into roster_unit_miniature_wargear_option
                  (rosterUnitMiniatureId, wargearOptionId, count)
                values (?, ?, ?)
                """,
                [roster_miniature_id, option["wargearOptionId"], option["count"] * model_count],
            )
        self.apply_missing_miniature_default_wargear(conn, roster_miniature_id, datasheet_id, miniature_id)

    def apply_miniature_default_wargear(self, conn, roster_miniature_id, datasheet_id, miniature_id):
        options = conn.execute(
            """
            select wo.id as wargearOptionId, wo.defaultValue as count
            from wargear_option_group wog
            join wargear_option wo on wo.wargearOptionGroupId = wog.id
            where wog.datasheetId = ?
              and wog.miniatureId = ?
              and wo.defaultValue > 0
            """,
            [datasheet_id, miniature_id],
        ).fetchall()
        for option in options:
            conn.execute(
                """
                insert or replace into roster_unit_miniature_wargear_option
                  (rosterUnitMiniatureId, wargearOptionId, count)
                values (?, ?, ?)
                """,
                [roster_miniature_id, option["wargearOptionId"], option["count"]],
            )

    def apply_missing_miniature_default_wargear(self, conn, roster_miniature_id, datasheet_id, miniature_id):
        options = conn.execute(
            """
            select wo.id as wargearOptionId, wo.defaultValue as count
            from wargear_option_group wog
            join wargear_option wo on wo.wargearOptionGroupId = wog.id
            where wog.datasheetId = ?
              and wog.miniatureId = ?
              and wo.defaultValue > 0
              and not exists (
                select 1
                from roster_unit_miniature_wargear_option rumwo
                where rumwo.rosterUnitMiniatureId = ?
                  and rumwo.wargearOptionId = wo.id
              )
            """,
            [datasheet_id, miniature_id, roster_miniature_id],
        ).fetchall()
        for option in options:
            conn.execute(
                """
                insert into roster_unit_miniature_wargear_option
                  (rosterUnitMiniatureId, wargearOptionId, count)
                values (?, ?, ?)
                """,
                [roster_miniature_id, option["wargearOptionId"], option["count"]],
            )

    def unit_summary(self, conn, unit, roster=None, detachment_ids=None):
        roster = roster or {}
        detachment_ids = detachment_ids or []
        datasheet = conn.execute(
            """
            select id, name, maxModelCount, isSuccessorChapter, allegianceAbilityGroupId
            from datasheet
            where id = ?
            """,
            [unit["datasheetId"]],
        ).fetchone()
        miniatures = [dict_row(row) for row in conn.execute(
            """
            select rum.id as rosterUnitMiniatureId, rum.miniatureId, rum.count, rum.isWarlord,
                   m.name, m.cannotBeWarlord, m.canBeNonCharacterWarlord,
                   m.excludedFromEnhancements, m.isSupremeCommander
            from roster_unit_miniature rum
            join miniature m on m.id = rum.miniatureId
            where rum.rosterUnitId = ?
            order by m.displayOrder, m.name
            """,
            [unit["id"]],
        )]
        compositions = self.compositions(conn, unit["datasheetId"], roster, detachment_ids)
        selected = select_matching_composition(compositions, miniatures)
        composition_points = selected["points"] if selected else (compositions[0]["points"] if compositions else 0)
        wargear_points = (conn.execute(
            """
            select coalesce(sum(rumwo.count * wo.points), 0)
            from roster_unit_miniature_wargear_option rumwo
            join roster_unit_miniature rum on rum.id = rumwo.rosterUnitMiniatureId
            join wargear_option wo on wo.id = rumwo.wargearOptionId
            where rum.rosterUnitId = ?
            """,
            [unit["id"]],
        ).fetchone()[0] or 0) + (conn.execute(
            """
            select coalesce(sum(ruwo.count * wo.points), 0)
            from roster_unit_wargear_option ruwo
            join wargear_option wo on wo.id = ruwo.wargearOptionId
            where ruwo.rosterUnitId = ?
            """,
            [unit["id"]],
        ).fetchone()[0] or 0)
        model_count = sum(item["count"] for item in miniatures)
        allegiance_abilities = self.unit_allegiance_abilities(conn, unit["id"])
        keywords = self.unit_keywords(
            conn,
            unit["id"],
            unit["datasheetId"],
            roster,
            detachment_ids,
            [item["id"] for item in allegiance_abilities],
        )
        faction_keyword_ids = [
            row["factionKeywordId"] for row in conn.execute(
                "select factionKeywordId from datasheet_faction_keyword where datasheetId = ?",
                [unit["datasheetId"]],
            )
        ]
        warlord_miniatures = [
            item["miniatureId"] for item in miniatures if item.get("isWarlord") and item["count"] > 0
        ]
        unit_enhancements = self.unit_enhancements(conn, unit["id"], set(item["id"] for item in keywords))
        miniature_enhancements = []
        for miniature in miniatures:
            miniature_keyword_ids = self.miniature_keyword_ids(conn, miniature["miniatureId"])
            miniature_enhancements.extend(
                self.miniature_enhancements(conn, miniature["rosterUnitMiniatureId"], miniature_keyword_ids)
            )
        enhancement_points = sum(item["points"] for item in unit_enhancements + miniature_enhancements)
        return {
            "id": unit["id"],
            "datasheetId": unit["datasheetId"],
            "name": unit["name"],
            "allyType": unit.get("allyType", "native"),
            "points": composition_points + wargear_points + enhancement_points,
            "modelCount": model_count,
            "maxModelCount": datasheet["maxModelCount"] if datasheet else None,
            "isSuccessorChapter": bool(datasheet["isSuccessorChapter"]) if datasheet else False,
            "allegianceAbilityGroupId": datasheet["allegianceAbilityGroupId"] if datasheet else None,
            "selectedCompositionId": selected["id"] if selected else None,
            "selectedCompositionAvailable": selected.get("available") if selected else False,
            "compositionLabel": selected["label"] if selected else composition_label_from_current(miniatures),
            "keywordIds": [item["id"] for item in keywords],
            "keywordNames": [item["name"] for item in keywords],
            "factionKeywordIds": faction_keyword_ids,
            "isWarlord": bool(warlord_miniatures),
            "warlordMiniatureIds": warlord_miniatures,
            "miniatures": miniatures,
            "allegianceAbilities": allegiance_abilities,
            "unitEnhancements": unit_enhancements,
            "miniatureEnhancements": miniature_enhancements,
        }
