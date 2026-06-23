from collections import Counter
from itertools import combinations, combinations_with_replacement, product

from roster_builder_utils import dedupe_counters, dict_row, sum_counters


class WargearValidationMixin:
    def validate_wargear_loadouts(self, conn, units, messages):
        for unit in units:
            invalid_unit_options = conn.execute(
                """
                select wi.name
                from roster_unit_wargear_option ruwo
                join wargear_option wo on wo.id = ruwo.wargearOptionId
                join wargear_item wi on wi.id = wo.wargearItemId
                left join wargear_option_group wog on wog.id = wo.wargearOptionGroupId
                where ruwo.rosterUnitId = ?
                  and ruwo.count > 0
                  and (wog.datasheetId is null or wog.datasheetId != ? or wog.miniatureId is not null)
                """,
                [unit["id"], unit["datasheetId"]],
            ).fetchall()
            for row in invalid_unit_options:
                messages.append({"level": "error", "text": f"{unit['name']} has invalid unit wargear selected: {row['name']}."})
            invalid_model_options = conn.execute(
                """
                select m.name as modelName, wi.name
                from roster_unit_miniature_wargear_option rumwo
                join roster_unit_miniature rum on rum.id = rumwo.rosterUnitMiniatureId
                join miniature m on m.id = rum.miniatureId
                join wargear_option wo on wo.id = rumwo.wargearOptionId
                join wargear_item wi on wi.id = wo.wargearItemId
                left join wargear_option_group wog on wog.id = wo.wargearOptionGroupId
                where rum.rosterUnitId = ?
                  and rumwo.count > 0
                  and (
                    wog.datasheetId is null or wog.datasheetId != ?
                    or wog.miniatureId is null
                    or wog.miniatureId != rum.miniatureId
                  )
                """,
                [unit["id"], unit["datasheetId"]],
            ).fetchall()
            for row in invalid_model_options:
                messages.append({"level": "error", "text": f"{unit['name']} has invalid wargear for {row['modelName']}: {row['name']}."})

            unit_counts = self.selected_unit_wargear_item_counts(conn, unit["id"])
            if not self.wargear_loadout_matches_choice_sets(conn, unit["datasheetId"], None, unit_counts, 1):
                messages.append({"level": "error", "text": f"{unit['name']} has an invalid unit wargear configuration."})

            for miniature in unit.get("miniatures", []):
                selected = self.selected_miniature_wargear_item_counts(conn, miniature["rosterUnitMiniatureId"])
                if miniature["count"] == 0:
                    if selected:
                        messages.append({"level": "error", "text": f"{unit['name']} has wargear selected for a model count of 0: {miniature['name']}."})
                    continue
                if not self.wargear_loadout_matches_choice_sets(
                    conn,
                    unit["datasheetId"],
                    miniature["miniatureId"],
                    selected,
                    miniature["count"],
                ):
                    if unit["modelCount"] == 1:
                        messages.append({"level": "error", "text": f"Invalid wargear selected for {unit['name']}."})
                    else:
                        messages.append({"level": "error", "text": f"Invalid wargear selected for {miniature['name']} model in {unit['name']}."})

            self.validate_limited_wargear_choice_sets(conn, unit, messages)
            self.validate_all_model_wargear_choice_sets(conn, unit, messages)

    def selected_unit_wargear_item_counts(self, conn, roster_unit_id):
        return Counter({
            row["wargearItemId"]: row["count"] for row in conn.execute(
                """
                select wo.wargearItemId, sum(ruwo.count) as count
                from roster_unit_wargear_option ruwo
                join wargear_option wo on wo.id = ruwo.wargearOptionId
                where ruwo.rosterUnitId = ?
                  and ruwo.count > 0
                group by wo.wargearItemId
                """,
                [roster_unit_id],
            )
        })

    def selected_miniature_wargear_item_counts(self, conn, roster_unit_miniature_id):
        return Counter({
            row["wargearItemId"]: row["count"] for row in conn.execute(
                """
                select wo.wargearItemId, sum(rumwo.count) as count
                from roster_unit_miniature_wargear_option rumwo
                join wargear_option wo on wo.id = rumwo.wargearOptionId
                where rumwo.rosterUnitMiniatureId = ?
                  and rumwo.count > 0
                group by wo.wargearItemId
                """,
                [roster_unit_miniature_id],
            )
        })

    def selected_roster_unit_wargear_item_counts(self, conn, roster_unit_id):
        counts = self.selected_unit_wargear_item_counts(conn, roster_unit_id)
        for row in conn.execute(
            """
            select wo.wargearItemId, sum(rumwo.count) as count
            from roster_unit_miniature_wargear_option rumwo
            join roster_unit_miniature rum on rum.id = rumwo.rosterUnitMiniatureId
            join wargear_option wo on wo.id = rumwo.wargearOptionId
            where rum.rosterUnitId = ?
              and rumwo.count > 0
            group by wo.wargearItemId
            """,
            [roster_unit_id],
        ):
            counts[row["wargearItemId"]] += row["count"]
        return +counts

    def selected_scope_wargear_item_counts(self, conn, unit, miniature_id):
        if miniature_id is None:
            return self.selected_roster_unit_wargear_item_counts(conn, unit["id"])
        row = next((item for item in unit.get("miniatures", []) if item["miniatureId"] == miniature_id), None)
        if not row:
            return Counter()
        return self.selected_miniature_wargear_item_counts(conn, row["rosterUnitMiniatureId"])

    def wargear_loadout_matches_choice_sets(self, conn, datasheet_id, miniature_id, selected_counts, model_count):
        selected_counts = +Counter(selected_counts)
        sets = self.loadout_choice_sets(conn, datasheet_id, miniature_id)
        if not sets:
            return not selected_counts
        valid_loadouts = self.valid_loadouts_from_choice_sets(sets)
        if model_count <= 1:
            return any(loadout == selected_counts for loadout in valid_loadouts)
        return self.can_partition_loadouts(selected_counts, valid_loadouts, model_count)

    def loadout_choice_sets(self, conn, datasheet_id, miniature_id):
        if miniature_id is None:
            rows = conn.execute(
                """
                select id, "limit", allowDuplicates, alternate
                from loadout_choice_set
                where datasheetId = ?
                  and miniatureId is null
                order by alternate, id
                """,
                [datasheet_id],
            ).fetchall()
        else:
            rows = conn.execute(
                """
                select id, "limit", allowDuplicates, alternate
                from loadout_choice_set
                where datasheetId = ?
                  and miniatureId = ?
                order by alternate, id
                """,
                [datasheet_id, miniature_id],
            ).fetchall()
        sets = []
        for row in rows:
            item = dict_row(row)
            item["choices"] = self.loadout_choices(conn, item["id"])
            sets.append(item)
        return sets

    def loadout_choices(self, conn, loadout_choice_set_id):
        rows = conn.execute(
            """
            select id
            from loadout_choice
            where loadoutChoiceSetId = ?
            order by id
            """,
            [loadout_choice_set_id],
        ).fetchall()
        return [self.loadout_choice_items(conn, "loadout_choice_wargear_item", "loadoutChoiceId", row["id"]) for row in rows]

    def loadout_choice_items(self, conn, table, id_column, choice_id):
        return Counter({
            row["wargearItemId"]: row["count"] for row in conn.execute(
                f"""
                select wargearItemId, count
                from {table}
                where {id_column} = ?
                """,
                [choice_id],
            )
        })

    def valid_loadouts_from_choice_sets(self, sets):
        regular_sets = [item for item in sets if not item["alternate"]]
        alternate_sets = [item for item in sets if item["alternate"]]
        loadouts = []
        if regular_sets:
            set_loadouts = [self.choice_set_loadouts(item) for item in regular_sets]
            if all(set_loadouts):
                for pieces in product(*set_loadouts):
                    loadouts.append(sum_counters(pieces))
        else:
            loadouts.append(Counter())
        for item in alternate_sets:
            loadouts.extend(self.choice_set_loadouts(item))
        return dedupe_counters(loadouts)

    def choice_set_loadouts(self, choice_set):
        choices = choice_set["choices"]
        limit = choice_set["limit"]
        if limit == 0:
            return [Counter()]
        if not choices:
            return []
        if choice_set["allowDuplicates"]:
            raw = combinations_with_replacement(choices, limit)
        else:
            empty_choices = [choice for choice in choices if not choice]
            if empty_choices:
                non_empty_choices = [choice for choice in choices if choice]
                raw = []
                for selected_count in range(0, min(limit, len(non_empty_choices)) + 1):
                    raw.extend(combinations(non_empty_choices, selected_count))
                return dedupe_counters(sum_counters(items) for items in raw)
            if limit > len(choices):
                return []
            raw = combinations(choices, limit)
        return dedupe_counters(sum_counters(items) for items in raw)

    def can_partition_loadouts(self, selected_counts, valid_loadouts, model_count):
        keys = tuple(sorted(selected_counts))
        target = tuple(selected_counts[key] for key in keys)
        vectors = []
        for loadout in valid_loadouts:
            if any(key not in selected_counts for key in loadout):
                continue
            vector = tuple(loadout.get(key, 0) for key in keys)
            if all(value <= target[index] for index, value in enumerate(vector)):
                vectors.append(vector)
        vectors = sorted(set(vectors), key=sum, reverse=True)
        if not vectors:
            return not selected_counts and model_count == 0
        memo = {}

        def fits(vector, remaining):
            return all(vector[index] <= remaining[index] for index in range(len(remaining)))

        def subtract(vector, remaining):
            return tuple(remaining[index] - vector[index] for index in range(len(remaining)))

        def search(remaining, models_left):
            key = (remaining, models_left)
            if key in memo:
                return memo[key]
            if models_left == 0:
                memo[key] = all(value == 0 for value in remaining)
                return memo[key]
            if sum(remaining) < 0:
                memo[key] = False
                return False
            for vector in vectors:
                if fits(vector, remaining) and search(subtract(vector, remaining), models_left - 1):
                    memo[key] = True
                    return True
            memo[key] = False
            return False

        return search(target, model_count)

    def validate_limited_wargear_choice_sets(self, conn, unit, messages):
        rows = conn.execute(
            """
            select id, miniatureId, mandatory
            from limited_wargear_choice_set
            where datasheetId = ?
            """,
            [unit["datasheetId"]],
        ).fetchall()
        for row in rows:
            limit = self.effective_wargear_limit(conn, row["id"], unit["modelCount"])
            if not limit:
                continue
            selected = self.selected_scope_wargear_item_counts(conn, unit, row["miniatureId"])
            choices = self.limited_wargear_choices(conn, row["id"])
            if self.limited_choice_cover_is_valid(selected, choices, limit["choiceLimit"], limit["duplicateLimit"], row["mandatory"]):
                continue
            messages.append({"level": "error", "text": f"Invalid wargear configuration for {unit['name']}."})

    def effective_wargear_limit(self, conn, limited_wargear_choice_set_id, model_count):
        rows = conn.execute(
            """
            select modelCount, choiceLimit, duplicateLimit
            from wargear_limit
            where limitedWargearChoiceSetId = ?
            order by modelCount
            """,
            [limited_wargear_choice_set_id],
        ).fetchall()
        if not rows:
            return None
        eligible = [row for row in rows if row["modelCount"] <= model_count]
        return dict_row(eligible[-1] if eligible else rows[0])

    def limited_wargear_choices(self, conn, limited_wargear_choice_set_id):
        rows = conn.execute(
            """
            select id
            from limited_wargear_choice
            where limitedWargearChoiceSetId = ?
            order by id
            """,
            [limited_wargear_choice_set_id],
        ).fetchall()
        return [
            self.loadout_choice_items(
                conn,
                "limited_wargear_choice_wargear_item",
                "limitedWargearChoiceId",
                row["id"],
            )
            for row in rows
        ]

    def limited_choice_cover_is_valid(self, selected_counts, choices, choice_limit, duplicate_limit, mandatory=False):
        relevant_ids = {key for choice in choices for key in choice}
        target_counts = Counter({key: value for key, value in selected_counts.items() if key in relevant_ids})
        if not target_counts:
            return not mandatory
        keys = tuple(sorted(target_counts))
        target = tuple(target_counts[key] for key in keys)
        vectors = [
            tuple(choice.get(key, 0) for key in keys)
            for choice in choices
            if choice and not any(key not in relevant_ids for key in choice)
        ]
        vectors = [vector for vector in vectors if any(vector)]
        if not vectors:
            return False
        states = {tuple(0 for _ in keys): 0}
        cap_per_choice = choice_limit if duplicate_limit is None else min(choice_limit, duplicate_limit)
        for vector in vectors:
            next_states = dict(states)
            for current, used in states.items():
                for repeats in range(1, cap_per_choice + 1):
                    total_used = used + repeats
                    if total_used > choice_limit:
                        break
                    candidate = tuple(current[index] + vector[index] * repeats for index in range(len(keys)))
                    if any(candidate[index] > target[index] for index in range(len(keys))):
                        break
                    previous = next_states.get(candidate)
                    if previous is None or total_used < previous:
                        next_states[candidate] = total_used
            states = next_states
        return target in states and states[target] <= choice_limit

    def validate_all_model_wargear_choice_sets(self, conn, unit, messages):
        rows = conn.execute(
            """
            select id, miniatureId
            from all_model_wargear_choice_set
            where datasheetId = ?
            """,
            [unit["datasheetId"]],
        ).fetchall()
        invalid = False
        for row in rows:
            choices = self.all_model_wargear_choices(conn, row["id"])
            base_choices = [choice for choice in choices if not choice["substitute"]]
            selected = self.selected_scope_wargear_item_counts(conn, unit, row["miniatureId"])
            model_count = self.scope_model_count(unit, row["miniatureId"])
            if model_count <= 0:
                continue
            active_base = []
            for choice in base_choices:
                occurrences = self.choice_occurrences(selected, choice["items"])
                if occurrences:
                    active_base.append((choice, occurrences))
            substitute_count = sum(
                self.choice_occurrences(selected, choice["items"])
                for choice in choices
                if choice["substitute"]
            )
            if len(active_base) > 1:
                invalid = True
                continue
            if len(active_base) == 1 and active_base[0][1] + substitute_count != model_count:
                invalid = True
        if invalid:
            messages.append({"level": "error", "text": f"Invalid wargear configuration for {unit['name']}."})

    def all_model_wargear_choices(self, conn, all_model_wargear_choice_set_id):
        rows = conn.execute(
            """
            select id, substitute
            from all_model_wargear_choice
            where allModelWargearChoiceSetId = ?
            order by id
            """,
            [all_model_wargear_choice_set_id],
        ).fetchall()
        return [
            {
                "substitute": row["substitute"],
                "items": self.loadout_choice_items(
                    conn,
                    "all_model_wargear_choice_wargear_item",
                    "allModelWargearChoiceId",
                    row["id"],
                ),
            }
            for row in rows
        ]

    def choice_occurrences(self, selected_counts, choice):
        if not choice:
            return 0
        return min(selected_counts.get(key, 0) // count for key, count in choice.items())

    def scope_model_count(self, unit, miniature_id):
        if miniature_id is None:
            return unit["modelCount"]
        miniature = next(
            (item for item in unit.get("miniatures", []) if item["miniatureId"] == miniature_id),
            None,
        )
        return miniature["count"] if miniature else 0
