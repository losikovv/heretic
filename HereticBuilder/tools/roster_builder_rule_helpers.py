from roster_builder_utils import dict_row

class RosterRuleHelpersMixin:
    def faction_keyword_scope(self, conn, faction_keyword_id):
        if not faction_keyword_id:
            return []
        scope = []
        seen = set()
        current_id = faction_keyword_id
        while current_id and current_id not in seen:
            seen.add(current_id)
            scope.append(current_id)
            row = conn.execute(
                "select parentFactionKeywordId from faction_keyword where id = ?",
                [current_id],
            ).fetchone()
            current_id = row["parentFactionKeywordId"] if row else None
        return scope

    def faction_keyword_scopes(self, conn, faction_keyword_ids):
        scope = []
        seen = set()
        for faction_keyword_id in faction_keyword_ids or []:
            for scoped_id in self.faction_keyword_scope(conn, faction_keyword_id):
                if scoped_id in seen:
                    continue
                seen.add(scoped_id)
                scope.append(scoped_id)
        return scope

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
