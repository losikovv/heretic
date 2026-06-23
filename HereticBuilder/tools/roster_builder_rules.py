from roster_builder_rule_allegiance import RosterAllegianceRulesMixin
from roster_builder_rule_allies import RosterAlliedRulesMixin
from roster_builder_rule_attachments import RosterAttachmentRulesMixin
from roster_builder_rule_enhancements import RosterEnhancementRulesMixin
from roster_builder_rule_helpers import RosterRuleHelpersMixin
from roster_builder_rule_restrictions import RosterRestrictionRulesMixin
from roster_builder_rule_warlord import RosterWarlordRulesMixin


class RosterRulesMixin(
    RosterRuleHelpersMixin,
    RosterAllegianceRulesMixin,
    RosterAlliedRulesMixin,
    RosterEnhancementRulesMixin,
    RosterAttachmentRulesMixin,
    RosterWarlordRulesMixin,
    RosterRestrictionRulesMixin,
):
    def validate(self, conn, roster, detachments, units, total_points):
        messages = []
        limit = roster.get("pointsLimit") or 0
        if limit and total_points > limit:
            messages.append({"level": "error", "text": f"Roster is {total_points - limit} points over the {limit} point limit."})
        if not detachments:
            messages.append({"level": "error", "text": "Pick a detachment."})
        detachment_points_limit = roster.get("detachmentPointsLimit") or 0
        if detachments and detachment_points_limit:
            detachment_points = sum(detachment["detachmentPointsCost"] or 0 for detachment in detachments)
            if detachment_points > detachment_points_limit:
                messages.append({"level": "error", "text": f"Roster uses {detachment_points} detachment points; limit is {detachment_points_limit}."})
        for detachment in detachments:
            allowed = conn.execute(
                """
                select 1
                from detachment_faction_keyword
                where detachmentId = ? and factionKeywordId = ?
                """,
                [detachment["id"], roster["factionKeywordId"]],
            ).fetchone()
            if not allowed:
                messages.append({"level": "error", "text": f"{detachment['name']} is not available to {roster['factionName']}."})

        self.validate_detachment_unique_keywords(conn, detachments, messages)
        self.validate_warlord(conn, roster, detachments, units, messages)
        self.validate_allegiance_abilities(conn, roster, detachments, units, messages)
        self.validate_allied_units(conn, roster, detachments, units, messages)
        self.validate_enhancements(conn, roster, units, messages)
        self.validate_attached_units(conn, roster, detachments, messages)
        self.validate_detachment_datasheets(conn, roster, detachments, units, messages)
        self.validate_keyword_restrictions(conn, roster, detachments, units, messages)
        self.validate_unit_compositions(conn, roster, detachments, units, messages)
        self.validate_wargear_loadouts(conn, units, messages)

        duplicate_limit = roster.get("duplicateUnitLimit") or 3
        counts = {}
        first_by_datasheet = {}
        for unit in units:
            counts[unit["datasheetId"]] = counts.get(unit["datasheetId"], 0) + 1
            first_by_datasheet.setdefault(unit["datasheetId"], unit)
            if unit.get("allyType", "native") == "native":
                allowed = conn.execute(
                    """
                    select 1
                    from datasheet_faction_keyword
                    where datasheetId = ? and factionKeywordId = ?
                    """,
                    [unit["datasheetId"], roster["factionKeywordId"]],
                ).fetchone()
                if not allowed:
                    messages.append({"level": "error", "text": f"{unit['name']} is not native to {roster['factionName']}."})
            faction_excluded = conn.execute(
                """
                select 1
                from faction_keyword_excluded_datasheet
                where factionKeywordId = ? and datasheetId = ?
                """,
                [roster["factionKeywordId"], unit["datasheetId"]],
            ).fetchone()
            if faction_excluded:
                messages.append({"level": "error", "text": f"{unit['name']} is excluded from {roster['factionName']} rosters."})
        for datasheet_id, count in counts.items():
            unit = first_by_datasheet[datasheet_id]
            effective_limit = self.duplicate_limit_for_unit(unit, duplicate_limit)
            if count > effective_limit:
                messages.append({"level": "error", "text": f"{unit['name']} has {count} units; limit is {effective_limit}."})
        self.validate_successor_chapter_epic_heroes(units, messages)
        if not units:
            messages.append({"level": "warning", "text": "Roster has no units."})
        state = "invalid" if any(item["level"] == "error" for item in messages) else "valid"
        return {"state": state, "messages": messages}
