from roster_builder_utils import dict_row, plain_text

class RosterCatalogMixin:
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

    def detachments(self, faction_id, include_combat_patrol=False):
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
                  and (? or d.isCombatPatrol = 0)
                order by d.isCombatPatrol, d.displayOrder, lower(d.name)
                """,
                [faction_id, faction_id, 1 if include_combat_patrol else 0],
            ).fetchall()
        return {"detachments": [dict_row(row) for row in rows]}

    def datasheets(self, faction_id, detachment_ids=None, query="", ally_type="native"):
        detachment_ids = self.normalize_ids(detachment_ids)
        params = []
        excluded = ""
        if detachment_ids:
            placeholders = ",".join("?" for _ in detachment_ids)
            excluded = """
              and not exists (
                select 1 from detachment_excluded_datasheet ded
                where ded.datasheetId = d.id
                  and ded.detachmentId in ({placeholders})
              )
            """.format(placeholders=placeholders)
        faction_excluded = ""
        if not ally_type or ally_type == "native":
            faction_excluded = """
              and not exists (
                select 1 from faction_keyword_excluded_datasheet fked
                where fked.datasheetId = d.id
                  and fked.factionKeywordId = ?
              )
            """
        with self.connect(readonly=True) as conn:
            composition_faction_ids = self.composition_faction_keyword_ids(conn, faction_id, ally_type)
        if not composition_faction_ids:
            composition_faction_ids = [faction_id or ""]
        composition_faction_placeholders = ",".join("?" for _ in composition_faction_ids)
        composition_detachment = ""
        if detachment_ids:
            placeholders = ",".join("?" for _ in detachment_ids)
            composition_detachment = """
                 or exists (
                   select 1 from unit_composition_required_detachment ucrd
                   where ucrd.unitCompositionId = uc.id
                     and ucrd.detachmentId in ({placeholders})
                 )
            """.format(placeholders=placeholders)
        composition = f"""
          and exists (
            select 1
            from unit_composition uc
            where uc.datasheetId = d.id
              and (
                not exists (
                  select 1 from unit_composition_required_faction_keyword ucrfk
                  where ucrfk.unitCompositionId = uc.id
                )
                or exists (
                  select 1 from unit_composition_required_faction_keyword ucrfk
                  where ucrfk.unitCompositionId = uc.id
                    and ucrfk.factionKeywordId in ({composition_faction_placeholders})
                )
              )
              and (
                not exists (
                  select 1 from unit_composition_required_detachment ucrd
                  where ucrd.unitCompositionId = uc.id
                )
                {composition_detachment}
              )
          )
        """
        search = ""
        if query:
            search = "and d.name like ?"
        if ally_type and ally_type != "native":
            source_join = "join allied_faction_datasheet afd on afd.datasheetId = d.id and afd.alliedFactionId = ?"
            source_where = ""
            params = [ally_type]
        else:
            source_join = "join datasheet_faction_keyword dfk on dfk.datasheetId = d.id"
            source_placeholders = ",".join("?" for _ in composition_faction_ids)
            source_where = f"and dfk.factionKeywordId in ({source_placeholders})"
            params = [*composition_faction_ids]
        params.extend(detachment_ids)
        if faction_excluded:
            params.append(faction_id)
        params.extend([*composition_faction_ids, *detachment_ids])
        if query:
            params.append(f"%{query}%")
        sql = f"""
            select distinct d.id, d.name, d.baseSize, d.unitComposition,
                   coalesce((
                     select uc.points
                     from unit_composition uc
                     where uc.datasheetId = d.id
                     order by uc.isDefault desc, uc.displayOrder
                     limit 1
                   ), 0) as points
            from datasheet d
            {source_join}
            where 1 = 1
              {source_where}
              {excluded}
              {faction_excluded}
              {composition}
              {search}
            order by lower(d.name)
            limit 250
        """
        with self.connect(readonly=True) as conn:
            rows = conn.execute(sql, params).fetchall()
        data = []
        for row in rows:
            item = dict_row(row)
            composition = self.default_composition(conn, item["id"], composition_faction_ids, detachment_ids)
            if composition:
                item["points"] = composition["points"]
            item["unitComposition"] = plain_text(item["unitComposition"])[:220]
            data.append(item)
        return {"datasheets": data}

    def normalize_ids(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [item for item in value.split(",") if item]
        return [item for item in value if item]

    def allied_factions(self, roster_id):
        with self.connect(readonly=True) as conn:
            roster = conn.execute("select factionKeywordId from roster where id = ?", [roster_id]).fetchone()
            if not roster:
                raise ValueError("Roster not found")
            rows = conn.execute(
                """
                select af.id, af.canTakeEnhancements, af.isMutuallyExclusiveKeywordLimit,
                       af.requiredWarlordMiniatureId, af.requiredDetachmentId,
                       group_concat(distinct fk.name) as name
                from faction_keyword_allied_faction fkaf
                join allied_faction af on af.id = fkaf.alliedFactionId
                left join allied_faction_parent_faction_keyword afpfk on afpfk.alliedFactionId = af.id
                left join faction_keyword fk on fk.id = afpfk.factionKeywordId
                where fkaf.factionKeywordId = ?
                group by af.id
                order by lower(coalesce(name, 'Allied'))
                """,
                [roster["factionKeywordId"]],
            ).fetchall()
        return {
            "alliedFactions": [
                {**dict_row(row), "name": row["name"] or "Allied"}
                for row in rows
            ]
        }
