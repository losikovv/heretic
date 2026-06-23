from roster_builder_utils import dict_row

class RosterAttachmentRulesMixin:
    def validate_attached_units(self, conn, roster, detachments, messages):
        rows = conn.execute(
            """
            select rau.id as attachedUnitId, rauru.rosterUnitId, rauru.attachmentType,
                   ru.datasheetId, d.name
            from roster_attached_unit rau
            join roster_attached_unit_roster_unit rauru on rauru.rosterAttachedUnitId = rau.id
            join roster_unit ru on ru.id = rauru.rosterUnitId
            join datasheet d on d.id = ru.datasheetId
            where rau.rosterId = ?
            order by rau.id, rauru.attachmentType
            """,
            [roster["id"]],
        ).fetchall()
        if not rows:
            return
        by_attached = {}
        for row in rows:
            by_attached.setdefault(row["attachedUnitId"], []).append(dict_row(row))
        detachment_ids = {item["id"] for item in detachments}
        for attached_id, members in by_attached.items():
            bodyguards = [item for item in members if item["attachmentType"] == "bodyguard"]
            attached_models = [item for item in members if item["attachmentType"] in ("leader", "support")]
            if not bodyguards or not attached_models:
                messages.append({"level": "error", "text": f"Attached unit {attached_id} is incomplete."})
                continue
            bodyguard = bodyguards[0]
            for attached in attached_models:
                if not self.attached_unit_can_attach(conn, roster, detachment_ids, attached, bodyguard):
                    messages.append({"level": "error", "text": f"{attached['name']} cannot attach to {bodyguard['name']} as {attached['attachmentType']}."})

    def attached_unit_can_attach(self, conn, roster, detachment_ids, attached, bodyguard):
        rows = conn.execute(
            """
            select dbg.*
            from datasheet_bodyguard_group dbg
            where dbg.datasheetId = ?
              and dbg.bodyguardType = ?
            """,
            [attached["datasheetId"], attached["attachmentType"]],
        ).fetchall()
        for row in rows:
            if row["factionKeywordId"] and row["factionKeywordId"] != roster["factionKeywordId"]:
                continue
            if row["excludedDetachmentId"] and row["excludedDetachmentId"] in detachment_ids:
                continue
            if row["requiredDetachmentId"] and row["requiredDetachmentId"] not in detachment_ids:
                continue
            datasheets = {
                item["datasheetId"] for item in conn.execute(
                    "select datasheetId from datasheet_bodyguard_group_datasheet where datasheetBodyguardGroupId = ?",
                    [row["id"]],
                )
            }
            keyword_ids = {
                item["keywordId"] for item in conn.execute(
                    "select keywordId from datasheet_bodyguard_group_keyword where datasheetBodyguardGroupId = ?",
                    [row["id"]],
                )
            }
            if datasheets and bodyguard["datasheetId"] not in datasheets:
                continue
            if keyword_ids:
                bodyguard_keywords = self.unit_keywords(conn, bodyguard["rosterUnitId"], bodyguard["datasheetId"], roster, detachment_ids, [])
                bodyguard_keyword_ids = {item["id"] for item in bodyguard_keywords}
                if not keyword_ids.intersection(bodyguard_keyword_ids):
                    continue
            if row["requiresAllUnitsHaveKeywordId"]:
                attached_keywords = {item["id"] for item in self.unit_keywords(conn, attached["rosterUnitId"], attached["datasheetId"], roster, detachment_ids, [])}
                bodyguard_keywords = {item["id"] for item in self.unit_keywords(conn, bodyguard["rosterUnitId"], bodyguard["datasheetId"], roster, detachment_ids, [])}
                required = row["requiresAllUnitsHaveKeywordId"]
                if required not in attached_keywords or required not in bodyguard_keywords:
                    continue
            return True
        return False
