import uuid
from collections import Counter


def new_id():
    return str(uuid.uuid4()).upper()


def dict_row(row):
    return {key: row[key] for key in row.keys()}


def sum_counters(counters):
    total = Counter()
    for counter in counters:
        total.update(counter)
    return +total


def dedupe_counters(counters):
    result = []
    seen = set()
    for counter in counters:
        clean = +Counter(counter)
        key = tuple(sorted(clean.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def select_matching_composition(compositions, miniatures):
    current = {item["miniatureId"]: item["count"] for item in miniatures}
    matches = []
    for comp in compositions:
        models = comp["models"]
        model_ids = {item["miniatureId"] for item in models}
        if set(current) != model_ids:
            continue
        ok = True
        for model in models:
            count = current.get(model["miniatureId"], 0)
            if count < model["min"] or count > model["max"]:
                ok = False
                break
        if ok:
            matches.append(comp)
    if not matches:
        return None
    available = [comp for comp in matches if comp.get("available", True)]
    return available[0] if available else matches[0]


def composition_label(models):
    pieces = []
    for model in models:
        count = str(model["min"]) if model["min"] == model["max"] else f"{model['min']}-{model['max']}"
        pieces.append(f"{count} {model['name']}")
    return " + ".join(pieces)


def composition_label_from_current(models):
    return " + ".join(f"{model['count']} {model['name']}" for model in models)


def plain_text(value):
    if not value:
        return ""
    text = str(value)
    text = text.replace("**", "").replace("■", "").replace("\n", " ")
    return " ".join(text.split())
