from collections import Counter

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

    def composition_faction_keyword_ids(self, conn, roster_faction_keyword_id, ally_type="native"):
        if ally_type and ally_type != "native":
            parent_ids = [
                row["factionKeywordId"] for row in conn.execute(
                    """
                    select factionKeywordId
                    from allied_faction_parent_faction_keyword
                    where alliedFactionId = ?
                    order by factionKeywordId
                    """,
                    [ally_type],
                )
            ]
            if parent_ids:
                return self.faction_keyword_scopes(conn, parent_ids)
        return self.faction_keyword_scope(conn, roster_faction_keyword_id)

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
            comp["available"] = self.composition_is_available(comp, (roster or {}).get("factionKeywordId"), detachment_ids or [])
            result.append(comp)
        return result

    def composition_is_available(self, comp, faction_keyword_id, detachment_ids):
        if isinstance(faction_keyword_id, (list, tuple, set)):
            faction_keyword_ids = set(faction_keyword_id)
        elif faction_keyword_id:
            faction_keyword_ids = {faction_keyword_id}
        else:
            faction_keyword_ids = set()
        if comp.get("requiredFactionKeywordIds") and not faction_keyword_ids.intersection(comp["requiredFactionKeywordIds"]):
            return False
        if comp.get("requiredDetachmentIds") and not set(comp["requiredDetachmentIds"]).intersection(detachment_ids):
            return False
        return True

    def datasheet_points_step_for_unit(self, conn, roster_id, roster_unit_id, datasheet_id):
        if not roster_id:
            return 0
        step = conn.execute(
            """
            select stepAt, stepPoints
            from datasheet_points_step
            where datasheetId = ?
            """,
            [datasheet_id],
        ).fetchone()
        if not step:
            return 0
        same_datasheet_ids = [
            row["id"] for row in conn.execute(
                """
                select id
                from roster_unit
                where rosterId = ? and datasheetId = ?
                order by id
                """,
                [roster_id, datasheet_id],
            )
        ]
        try:
            position = same_datasheet_ids.index(roster_unit_id) + 1
        except ValueError:
            return 0
        return step["stepPoints"] if position >= step["stepAt"] else 0

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
              and datasheetId = ?
            order by case when datasheetId = ? then 0 else 1 end
            limit 1
            """,
            [miniature_id, datasheet_id, datasheet_id],
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
            self.normalize_default_miniature_wargear(conn, roster_miniature_id, datasheet_id, miniature_id, model_count)
            return
        options = conn.execute(
            """
            select wargearOptionId, count
            from base_miniature_loadout_wargear_option bmlo
            join wargear_option wo on wo.id = bmlo.wargearOptionId
            join wargear_option_group wog on wog.id = wo.wargearOptionGroupId
            where bmlo.baseMiniatureLoadoutId = ?
              and wog.datasheetId = ?
              and wog.miniatureId = ?
            """,
            [loadout["id"], datasheet_id, miniature_id],
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
        self.normalize_default_miniature_wargear(conn, roster_miniature_id, datasheet_id, miniature_id, model_count)

    def normalize_default_miniature_wargear(self, conn, roster_miniature_id, datasheet_id, miniature_id, model_count):
        selected = self.selected_miniature_wargear_item_counts(conn, roster_miniature_id)
        if self.wargear_loadout_matches_choice_sets(conn, datasheet_id, miniature_id, selected, model_count):
            return
        option_by_key = self.default_wargear_options_by_key(conn, datasheet_id, miniature_id)
        replacement = self.closest_valid_default_loadout(conn, datasheet_id, miniature_id, selected, model_count, option_by_key)
        if replacement is None:
            return
        conn.execute(
            "delete from roster_unit_miniature_wargear_option where rosterUnitMiniatureId = ?",
            [roster_miniature_id],
        )
        for key, count in replacement.items():
            if count <= 0:
                continue
            option_id = option_by_key.get(key)
            if not option_id:
                return
            conn.execute(
                """
                insert into roster_unit_miniature_wargear_option
                  (rosterUnitMiniatureId, wargearOptionId, count)
                values (?, ?, ?)
                """,
                [roster_miniature_id, option_id, count],
            )

    def default_wargear_options_by_key(self, conn, datasheet_id, miniature_id):
        rows = conn.execute(
            """
            select lower(wi.name) as wargearItemKey, wo.id
            from wargear_option_group wog
            join wargear_option wo on wo.wargearOptionGroupId = wog.id
            join wargear_item wi on wi.id = wo.wargearItemId
            where wog.datasheetId = ?
              and wog.miniatureId = ?
            order by case when wo.defaultValue > 0 then 0 else 1 end, wo.displayOrder
            """,
            [datasheet_id, miniature_id],
        )
        options = {}
        for row in rows:
            options.setdefault(row["wargearItemKey"], row["id"])
        return options

    def closest_valid_default_loadout(self, conn, datasheet_id, miniature_id, preferred, model_count, option_by_key):
        sets = self.loadout_choice_sets(conn, datasheet_id, miniature_id)
        if not sets:
            return Counter() if not preferred else None
        valid = [
            loadout for loadout in self.valid_loadouts_from_choice_sets(sets)
            if all(key in option_by_key for key in loadout)
        ]
        if not valid:
            return None
        if model_count <= 1:
            candidates = valid
        else:
            candidates = [Counter()]
            for _ in range(model_count):
                next_candidates = []
                seen = set()
                for base in candidates:
                    for loadout in valid:
                        candidate = +(base + loadout)
                        key = tuple(sorted(candidate.items()))
                        if key in seen:
                            continue
                        seen.add(key)
                        next_candidates.append(candidate)
                candidates = sorted(next_candidates, key=lambda item: self.default_loadout_score(item, preferred), reverse=True)[:2000]
        return max(candidates, key=lambda item: self.default_loadout_score(item, preferred))

    def default_loadout_score(self, candidate, preferred):
        keys = set(candidate) | set(preferred)
        overlap = sum(min(candidate.get(key, 0), preferred.get(key, 0)) for key in keys)
        over = sum(max(0, candidate.get(key, 0) - preferred.get(key, 0)) for key in keys)
        under = sum(max(0, preferred.get(key, 0) - candidate.get(key, 0)) for key in keys)
        return (overlap, -over, -under, -sum(candidate.values()))

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
        composition_faction_ids = self.composition_faction_keyword_ids(
            conn,
            roster.get("factionKeywordId"),
            unit.get("allyType", "native"),
        )
        compositions = self.compositions(conn, unit["datasheetId"], {"factionKeywordId": composition_faction_ids}, detachment_ids)
        selected = select_matching_composition(compositions, miniatures)
        composition_points = selected["points"] if selected else (compositions[0]["points"] if compositions else 0)
        points_step = self.datasheet_points_step_for_unit(conn, roster.get("id"), unit["id"], unit["datasheetId"])
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
            "points": composition_points + points_step + wargear_points + enhancement_points,
            "datasheetPointsStep": points_step,
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
