import sqlite3
from pathlib import Path
from urllib.parse import quote

from roster_builder_rules import RosterRulesMixin
from roster_builder_utils import (
    composition_label,
    composition_label_from_current,
    dict_row,
    new_id,
    plain_text,
    select_matching_composition,
)
from roster_builder_wargear import WargearValidationMixin


class HereticBuilder(RosterRulesMixin, WargearValidationMixin):
    def __init__(self, db_path):
        self.db_path = Path(db_path).resolve()

    def connect(self, readonly=False):
        if readonly:
            uri = f"file:{quote(str(self.db_path))}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma busy_timeout = 3000")
        return conn

    def bootstrap(self):
        with self.connect(readonly=True) as conn:
            factions = [dict_row(row) for row in conn.execute(
                """
                select id, name
                from faction_keyword
                where excludedFromArmyBuilder = 0
                order by lower(name)
                """
            )]
            battle_sizes = [dict_row(row) for row in conn.execute(
                "select id, name, pointsLimit from battle_size order by pointsLimit"
            )]
            rosters = [dict_row(row) for row in conn.execute(
                """
                select r.id, r.name, r.modifiedAt, r.factionKeywordId, r.battleSizeId,
                       fk.name as factionName, bs.name as battleSizeName
                from roster r
                join faction_keyword fk on fk.id = r.factionKeywordId
                left join battle_size bs on bs.id = r.battleSizeId
                order by r.modifiedAt desc, r.name
                """
            )]
        default_faction = next((item["id"] for item in factions if item["name"] == "Heretic Astartes"), factions[0]["id"] if factions else "")
        default_size = next((item["id"] for item in battle_sizes if item["name"] == "Strike Force"), battle_sizes[0]["id"] if battle_sizes else "")
        return {
            "database": self.db_path.name,
            "factions": factions,
            "battleSizes": battle_sizes,
            "rosters": rosters,
            "defaultFactionId": default_faction,
            "defaultBattleSizeId": default_size,
        }

    def detachments(self, faction_id):
        with self.connect(readonly=True) as conn:
            rows = conn.execute(
                """
                select d.id, d.name,
                       coalesce(dfdpc.detachmentPointsCost, d.detachmentPointsCost) as detachmentPointsCost,
                       d.isCombatPatrol
                from detachment d
                join detachment_faction_keyword dfk on dfk.detachmentId = d.id
                left join detachment_faction_detachment_points_cost dfdpc
                  on dfdpc.detachmentId = d.id and dfdpc.factionKeywordId = ?
                where dfk.factionKeywordId = ?
                order by d.isCombatPatrol, d.displayOrder, lower(d.name)
                """,
                [faction_id, faction_id],
            ).fetchall()
        return {"detachments": [dict_row(row) for row in rows]}

    def datasheets(self, faction_id, detachment_id, query):
        params = [faction_id]
        excluded = ""
        if detachment_id:
            excluded = """
              and not exists (
                select 1 from detachment_excluded_datasheet ded
                where ded.detachmentId = ? and ded.datasheetId = d.id
              )
            """
            params.append(detachment_id)
        search = ""
        if query:
            search = "and d.name like ?"
            params.append(f"%{query}%")
        sql = f"""
            select d.id, d.name, d.baseSize, d.unitComposition,
                   coalesce((
                     select uc.points
                     from unit_composition uc
                     where uc.datasheetId = d.id
                     order by uc.isDefault desc, uc.displayOrder
                     limit 1
                   ), 0) as points
            from datasheet d
            join datasheet_faction_keyword dfk on dfk.datasheetId = d.id
            where dfk.factionKeywordId = ?
              {excluded}
              {search}
            order by dfk.displayOrder, lower(d.name)
            limit 250
        """
        with self.connect(readonly=True) as conn:
            rows = conn.execute(sql, params).fetchall()
        data = []
        for row in rows:
            item = dict_row(row)
            item["unitComposition"] = plain_text(item["unitComposition"])[:220]
            data.append(item)
        return {"datasheets": data}

    def create_roster(self, payload):
        roster_id = new_id()
        name = payload.get("name") or "New Roster"
        faction_id = payload["factionKeywordId"]
        battle_size_id = payload["battleSizeId"]
        detachment_id = payload.get("detachmentId")
        with self.connect() as conn:
            conn.execute(
                """
                insert into roster (id, name, factionKeywordId, battleSizeId, rosterType)
                values (?, ?, ?, ?, 'Warhammer40k')
                """,
                [roster_id, name, faction_id, battle_size_id],
            )
            if detachment_id:
                conn.execute(
                    "insert into roster_detachment (rosterId, detachmentId) values (?, ?)",
                    [roster_id, detachment_id],
                )
            conn.execute(
                "insert or replace into roster_validation_state (id, rosterId, validationState) values (?, ?, 'valid')",
                [roster_id, roster_id],
            )
        return {"id": roster_id}

    def delete_roster(self, roster_id):
        with self.connect() as conn:
            exists = conn.execute("select 1 from roster where id = ?", [roster_id]).fetchone()
            if not exists:
                raise ValueError("Roster not found")
            conn.execute("delete from roster_validation_state where rosterId = ?", [roster_id])
            conn.execute("delete from roster where id = ?", [roster_id])
        return {"ok": True}

    def roster(self, roster_id):
        with self.connect(readonly=True) as conn:
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
            if not roster:
                raise ValueError("Roster not found")
            detachments = [dict_row(row) for row in conn.execute(
                """
                select d.*,
                       coalesce(dfdpc.detachmentPointsCost, d.detachmentPointsCost) as detachmentPointsCost
                from roster_detachment rd
                join detachment d on d.id = rd.detachmentId
                left join detachment_faction_detachment_points_cost dfdpc
                  on dfdpc.detachmentId = d.id and dfdpc.factionKeywordId = ?
                where rd.rosterId = ?
                order by d.displayOrder, d.name
                """,
                [roster["factionKeywordId"], roster_id],
            )]
            unit_rows = conn.execute(
                """
                select ru.id, ru.datasheetId, ru.allyType, d.name
                from roster_unit ru
                join datasheet d on d.id = ru.datasheetId
                where ru.rosterId = ?
                order by d.name, ru.id
                """,
                [roster_id],
            ).fetchall()
            roster_dict = dict_row(roster)
            detachment_ids = [item["id"] for item in detachments]
            units = [self.unit_summary(conn, dict_row(row), roster_dict, detachment_ids) for row in unit_rows]
            total = sum(unit["points"] for unit in units)
            validation = self.validate(conn, roster_dict, detachments, units, total)
        return {
            "roster": roster_dict,
            "detachments": detachments,
            "units": units,
            "points": {"total": total, "limit": roster_dict.get("pointsLimit") or 0},
            "validation": validation,
        }

    def add_unit(self, roster_id, datasheet_id):
        roster_unit_id = new_id()
        with self.connect() as conn:
            roster = conn.execute("select factionKeywordId from roster where id = ?", [roster_id]).fetchone()
            if not roster:
                raise ValueError("Roster not found")
            detachment_ids = self.roster_detachment_ids(conn, roster_id)
            conn.execute(
                "insert into roster_unit (id, datasheetId, rosterId, allyType) values (?, ?, ?, 'native')",
                [roster_unit_id, datasheet_id, roster_id],
            )
            composition = self.default_composition(conn, datasheet_id, roster["factionKeywordId"], detachment_ids)
            if composition:
                self.apply_composition(conn, roster_unit_id, composition["id"])
        return {"id": roster_unit_id}

    def delete_unit(self, roster_unit_id):
        with self.connect() as conn:
            conn.execute("delete from roster_unit where id = ?", [roster_unit_id])
        return {"ok": True}

    def set_composition(self, roster_unit_id, composition_id):
        with self.connect() as conn:
            self.apply_composition(conn, roster_unit_id, composition_id)
        return {"ok": True}

    def set_wargear(self, roster_unit_miniature_id, wargear_option_id, count):
        count = max(0, int(count or 0))
        with self.connect() as conn:
            if count:
                conn.execute(
                    """
                    insert into roster_unit_miniature_wargear_option
                      (rosterUnitMiniatureId, wargearOptionId, count)
                    values (?, ?, ?)
                    on conflict(rosterUnitMiniatureId, wargearOptionId) do update set count = excluded.count
                    """,
                    [roster_unit_miniature_id, wargear_option_id, count],
                )
            else:
                conn.execute(
                    """
                    delete from roster_unit_miniature_wargear_option
                    where rosterUnitMiniatureId = ? and wargearOptionId = ?
                    """,
                    [roster_unit_miniature_id, wargear_option_id],
                )
        return {"ok": True}

    def set_unit_wargear(self, roster_unit_id, wargear_option_id, count):
        count = max(0, int(count or 0))
        with self.connect() as conn:
            if count:
                conn.execute(
                    """
                    insert into roster_unit_wargear_option
                      (rosterUnitId, wargearOptionId, count)
                    values (?, ?, ?)
                    on conflict(rosterUnitId, wargearOptionId) do update set count = excluded.count
                    """,
                    [roster_unit_id, wargear_option_id, count],
                )
            else:
                conn.execute(
                    """
                    delete from roster_unit_wargear_option
                    where rosterUnitId = ? and wargearOptionId = ?
                    """,
                    [roster_unit_id, wargear_option_id],
                )
        return {"ok": True}

    def set_warlord(self, roster_unit_miniature_id, enabled):
        with self.connect() as conn:
            row = conn.execute(
                """
                select rum.id, rum.miniatureId, rum.rosterUnitId, rum.count, ru.rosterId,
                       ru.datasheetId, ru.allyType, d.name,
                       m.cannotBeWarlord, m.canBeNonCharacterWarlord
                from roster_unit_miniature rum
                join roster_unit ru on ru.id = rum.rosterUnitId
                join datasheet d on d.id = ru.datasheetId
                join miniature m on m.id = rum.miniatureId
                where rum.id = ?
                """,
                [roster_unit_miniature_id],
            ).fetchone()
            if not row:
                raise ValueError("Model not found")
            if enabled and row["count"] <= 0:
                raise ValueError("This model is not present in the unit")
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
                [row["rosterId"]],
            ).fetchone()
            detachment_ids = self.roster_detachment_ids(conn, row["rosterId"])
            unit = self.unit_summary(
                conn,
                {
                    "id": row["rosterUnitId"],
                    "datasheetId": row["datasheetId"],
                    "allyType": row["allyType"],
                    "name": row["name"],
                },
                dict_row(roster),
                detachment_ids,
            )
            warlord_miniature_ids = set(self.roster_warlord_miniature_ids(conn, row["rosterId"]))
            if enabled:
                warlord_miniature_ids.add(row["miniatureId"])
            conditional_character = self.conditional_keyword_applies(
                conn,
                row["datasheetId"],
                "Character",
                dict_row(roster),
                detachment_ids,
                [item["id"] for item in unit.get("allegianceAbilities", [])],
                warlord_miniature_ids,
            )
            if enabled and not self.can_be_warlord(
                conn,
                row["miniatureId"],
                row["cannotBeWarlord"],
                row["canBeNonCharacterWarlord"],
                detachment_ids,
                conditional_character,
            ):
                raise ValueError("This model cannot be your Warlord")
            if enabled:
                conn.execute(
                    """
                    update roster_unit_miniature
                    set isWarlord = 0
                    where rosterUnitId in (select id from roster_unit where rosterId = ?)
                    """,
                    [row["rosterId"]],
                )
            conn.execute(
                "update roster_unit_miniature set isWarlord = ? where id = ?",
                [1 if enabled else 0, roster_unit_miniature_id],
            )
        return {"ok": True}

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
        return {
            "summary": summary,
            "compositions": compositions,
            "unitWargearGroups": unit_wargear_groups,
            "miniatures": miniatures,
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
