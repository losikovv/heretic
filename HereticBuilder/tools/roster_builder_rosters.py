from roster_builder_utils import dict_row, new_id

class RosterMutationMixin:
    def create_roster(self, payload):
        roster_id = new_id()
        name = payload.get("name") or "New Roster"
        faction_id = payload["factionKeywordId"]
        battle_size_id = payload["battleSizeId"]
        detachment_ids = self.normalize_ids(payload.get("detachmentIds"))
        if not detachment_ids and payload.get("detachmentId"):
            detachment_ids = [payload["detachmentId"]]
        with self.connect() as conn:
            conn.execute(
                """
                insert into roster (id, name, factionKeywordId, battleSizeId, rosterType)
                values (?, ?, ?, ?, 'Warhammer40k')
                """,
                [roster_id, name, faction_id, battle_size_id],
            )
            for detachment_id in detachment_ids:
                conn.execute(
                    "insert into roster_detachment (rosterId, detachmentId) values (?, ?)",
                    [roster_id, detachment_id],
                )
            conn.execute(
                "insert or replace into roster_validation_state (id, rosterId, validationState) values (?, ?, 'valid')",
                [roster_id, roster_id],
            )
        return {"id": roster_id}

    def set_roster_detachments(self, roster_id, detachment_ids):
        detachment_ids = self.normalize_ids(detachment_ids)
        with self.connect() as conn:
            roster = conn.execute("select 1 from roster where id = ?", [roster_id]).fetchone()
            if not roster:
                raise ValueError("Roster not found")
            conn.execute("delete from roster_detachment where rosterId = ?", [roster_id])
            for detachment_id in dict.fromkeys(detachment_ids):
                conn.execute(
                    "insert into roster_detachment (rosterId, detachmentId) values (?, ?)",
                    [roster_id, detachment_id],
                )
        return {"ok": True}

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

    def add_unit(self, roster_id, datasheet_id, ally_type="native"):
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
            if ally_type and ally_type != "native":
                conn.execute("update roster_unit set allyType = ? where id = ?", [ally_type, roster_unit_id])
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

    def set_allegiance_ability(self, roster_unit_id, allegiance_ability_id, enabled):
        with self.connect() as conn:
            if enabled:
                ability = conn.execute(
                    "select allegianceAbilityGroupId from allegiance_ability where id = ?",
                    [allegiance_ability_id],
                ).fetchone()
                if ability:
                    conn.execute(
                        """
                        delete from roster_unit_allegiance_ability
                        where rosterUnitId = ?
                          and allegianceAbilityId in (
                            select id
                            from allegiance_ability
                            where allegianceAbilityGroupId = ?
                          )
                        """,
                        [roster_unit_id, ability["allegianceAbilityGroupId"]],
                    )
                conn.execute(
                    """
                    insert or ignore into roster_unit_allegiance_ability
                      (rosterUnitId, allegianceAbilityId)
                    values (?, ?)
                    """,
                    [roster_unit_id, allegiance_ability_id],
                )
            else:
                conn.execute(
                    """
                    delete from roster_unit_allegiance_ability
                    where rosterUnitId = ? and allegianceAbilityId = ?
                    """,
                    [roster_unit_id, allegiance_ability_id],
                )
        return {"ok": True}

    def set_unit_enhancement(self, roster_unit_id, enhancement_id, enabled):
        with self.connect() as conn:
            if enabled:
                conn.execute(
                    """
                    insert or ignore into roster_unit_enhancement
                      (rosterUnitId, enhancementId)
                    values (?, ?)
                    """,
                    [roster_unit_id, enhancement_id],
                )
            else:
                conn.execute(
                    """
                    delete from roster_unit_enhancement
                    where rosterUnitId = ? and enhancementId = ?
                    """,
                    [roster_unit_id, enhancement_id],
                )
        return {"ok": True}

    def set_miniature_enhancement(self, roster_unit_miniature_id, enhancement_id, enabled):
        with self.connect() as conn:
            if enabled:
                conn.execute(
                    """
                    insert or ignore into roster_unit_miniature_enhancement
                      (rosterUnitMiniatureId, enhancementId)
                    values (?, ?)
                    """,
                    [roster_unit_miniature_id, enhancement_id],
                )
            else:
                conn.execute(
                    """
                    delete from roster_unit_miniature_enhancement
                    where rosterUnitMiniatureId = ? and enhancementId = ?
                    """,
                    [roster_unit_miniature_id, enhancement_id],
                )
        return {"ok": True}

    def create_attached_unit(self, bodyguard_unit_id, attached_unit_id, attached_type):
        if attached_type not in ("leader", "support"):
            raise ValueError("Attachment type must be leader or support")
        attached_id = new_id()
        with self.connect() as conn:
            bodyguard = conn.execute("select rosterId from roster_unit where id = ?", [bodyguard_unit_id]).fetchone()
            attached = conn.execute("select rosterId from roster_unit where id = ?", [attached_unit_id]).fetchone()
            if not bodyguard or not attached or bodyguard["rosterId"] != attached["rosterId"]:
                raise ValueError("Attached units must be in the same roster")
            conn.execute("insert into roster_attached_unit (id, rosterId) values (?, ?)", [attached_id, bodyguard["rosterId"]])
            conn.execute(
                """
                insert into roster_attached_unit_roster_unit
                  (rosterAttachedUnitId, rosterUnitId, attachmentType)
                values (?, ?, 'bodyguard')
                """,
                [attached_id, bodyguard_unit_id],
            )
            conn.execute(
                """
                insert into roster_attached_unit_roster_unit
                  (rosterAttachedUnitId, rosterUnitId, attachmentType)
                values (?, ?, ?)
                """,
                [attached_id, attached_unit_id, attached_type],
            )
        return {"id": attached_id}

    def delete_attached_unit(self, attached_unit_id):
        with self.connect() as conn:
            conn.execute(
                "delete from roster_attached_unit_roster_unit where rosterAttachedUnitId = ?",
                [attached_unit_id],
            )
            conn.execute("delete from roster_attached_unit where id = ?", [attached_unit_id])
        return {"ok": True}
