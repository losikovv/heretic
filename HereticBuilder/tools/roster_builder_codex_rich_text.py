import html
import re


def escape_html(value):
    return html.escape(str(value), quote=False)


def escape_attr(value):
    return html.escape(str(value), quote=True)


def normalize_rule_reference_code(value):
    match = re.fullmatch(r"\s*(\d{1,2})(?:\.(\d{1,2}))?\s*", str(value or ""))
    if not match:
        return ""
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    return f"{major:02d}.{minor:02d}"


def core_rule_href(reference):
    normalized = normalize_rule_reference_code(reference)
    if not normalized:
        return ""
    return f"/codex/core-rules/rule/{normalized}"


def normalize_rule_text(value):
    text = html.unescape(str(value or "").replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(b|strong|k|u)>\s*</\1>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:i|em)>", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:b|strong|k|u)>", "**", text, flags=re.IGNORECASE)
    text = re.sub(r"<ul[^>]*>\s*<li[^>]*>", "\n■ ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>\s*<li[^>]*>", "\n■ ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>\s*</ul>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def is_empty_rule_text(value):
    return normalize_rule_text(value) in {"", "-", "–", "—"}


def rule_component_accent_color(value):
    color = normalize_rule_text(value)
    if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        return color
    return ""


def render_rule_component_heading(title, subtitle):
    title = "" if is_empty_rule_text(title) else normalize_rule_text(title)
    subtitle = "" if is_empty_rule_text(subtitle) else normalize_rule_text(subtitle)
    if not title and not subtitle:
        return ""
    title_html = f"<h3>{escape_html(title)}</h3>" if title else ""
    subtitle_html = f'<div class="rule-card-subtitle">{escape_html(subtitle)}</div>' if subtitle else ""
    return f'<div class="rule-card-heading">{title_html}{subtitle_html}</div>'


def apply_rule_inline_markup(text, current_rule_reference=None):
    current_reference = normalize_rule_reference_code(current_rule_reference)

    def render_rule_reference(reference, wrap=True):
        normalized = normalize_rule_reference_code(reference)
        target_reference = normalized
        if reference.count(".") >= 2:
            target_reference = normalize_rule_reference_code(".".join(reference.split(".")[:2]))
        label = escape_html(reference)
        if target_reference and target_reference == current_reference:
            return f"({label})" if wrap else label
        link_label = f"({label})" if wrap else label
        return f'<a class="rule-ref-link" href="{core_rule_href(target_reference or reference)}">{link_label}</a>'

    def render_parenthetical_rule_references(match):
        inner = match.group(1)
        if re.fullmatch(r"\s*\d{1,2}(?:\.\d{1,2})?\s*", inner):
            return render_rule_reference(inner.strip())

        def replace_code(code_match):
            reference = code_match.group(1)
            return render_rule_reference(reference, wrap=False)

        linked_inner = re.sub(r"\b(\d{1,2}(?:\.\d{1,2}){1,2})\b", replace_code, inner)
        return f"({linked_inner})"

    text = re.sub(r"\*\*\*(.+?)\*\*(.*?)\*", r"<em><strong>\1</strong>\2</em>", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(
        r"\(([^()]*(?:\d{1,2}(?:\.\d{1,2}){1,2})[^()]*)\)",
        render_parenthetical_rule_references,
        text,
    )
    return text


def render_rule_inline_text(value, current_rule_reference=None, preserve_line_breaks=True):
    text = escape_html(normalize_rule_text(value))
    text = apply_rule_inline_markup(text, current_rule_reference)
    if preserve_line_breaks:
        return text.replace("\n", "<br>")
    return text


def render_rule_table(table_html, current_rule_reference=None):
    rows = []
    header_labels = []
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL):
        cells = []
        raw_cells = []
        for cell_match in re.finditer(r"<(th|td)[^>]*>(.*?)</\1>", row_match.group(1), flags=re.IGNORECASE | re.DOTALL):
            tag = cell_match.group(1).lower()
            body = render_rule_inline_text(cell_match.group(2), current_rule_reference)
            raw_cells.append((tag, body))
        if not rows and any(tag == "th" for tag, _body in raw_cells):
            header_labels = [re.sub(r"<[^>]+>", "", body).strip() for _tag, body in raw_cells]
        for index, (tag, body) in enumerate(raw_cells):
            label_attr = ""
            if header_labels and tag == "td":
                header_label = header_labels[index] if index < len(header_labels) else ""
                label_attr = f' data-label="{escape_attr(header_label)}"'
            cells.append(f'<{tag}{label_attr}><span class="rule-table-cell-value">{body}</span></{tag}>')
        if cells:
            rows.append(f"<tr>{''.join(cells)}</tr>")
    if not rows:
        return ""
    table_class = "rule-table has-header" if header_labels else "rule-table"
    return f'<div class="rule-table-wrap"><table class="{table_class}">' + "".join(rows) + "</table></div>"


def render_rich_text(value, current_rule_reference=None):
    raw = str(value or "")
    if re.search(r"<table\b", raw, flags=re.IGNORECASE):
        pieces = []
        for part in re.split(r"(<table\b.*?</table>)", raw, flags=re.IGNORECASE | re.DOTALL):
            if not part:
                continue
            if re.match(r"<table\b", part, flags=re.IGNORECASE | re.DOTALL):
                pieces.append(render_rule_table(part, current_rule_reference))
            else:
                pieces.append(render_rich_text(part, current_rule_reference))
        return "".join(pieces)

    text = render_rule_inline_text(value, current_rule_reference, preserve_line_breaks=False)
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs and text:
        paragraphs = [text]
    return "".join(f"<p>{paragraph.replace(chr(10), '<br>')}</p>" for paragraph in paragraphs)


def render_rule_component(component, current_rule_reference=None):
    component_type = component.get("type") or ""
    title = component.get("title") or ""
    subtitle = component.get("subtitle") or ""
    text = component.get("textContent") or ""
    image_url = normalize_rule_text(component.get("imageUrl"))
    classes = ["rule-card"]
    accent_color = rule_component_accent_color(component.get("backgroundColor"))
    if "lore" in component_type.lower():
        classes.append("is-lore")
    if component_type == "quote":
        classes.append("is-quote")
    elif component_type == "textBold":
        classes.append("is-bold-text")
    elif component_type == "boxedText":
        classes.append("is-boxed-text")
    elif component_type == "triggerEffectAccordion":
        classes.append("is-trigger-effect")
    elif component_type == "accordion":
        classes.append("is-accordion")
    if accent_color:
        classes.append("has-accent")
    class_attr = " ".join(classes)
    style_attr = f' style="--rule-card-accent: {escape_attr(accent_color)};"' if accent_color else ""

    if component_type == "image":
        if not image_url:
            return ""
        caption = "" if is_empty_rule_text(title) else title
        if not caption and not is_empty_rule_text(text):
            caption = text
        alt_text = component.get("altText") or caption
        caption_html = f"<figcaption>{escape_html(normalize_rule_text(caption))}</figcaption>" if caption else ""
        return (
            '<figure class="rule-card rule-image-card">'
            f'<img class="rule-image" src="{escape_attr(image_url)}" alt="{escape_attr(normalize_rule_text(alt_text))}">'
            f"{caption_html}"
            "</figure>"
        )

    if component_type == "header":
        heading = title or text
        if is_empty_rule_text(heading):
            return ""
        return f'<section class="{class_attr}"{style_attr}><h3>{escape_html(heading)}</h3></section>'

    pieces = []
    heading = render_rule_component_heading(title, subtitle)
    if heading:
        pieces.append(heading)
    if not is_empty_rule_text(text):
        pieces.append(render_rich_text(text, current_rule_reference))
    if not is_empty_rule_text(component.get("trigger")):
        pieces.append(f"<h3>Trigger</h3>{render_rich_text(component['trigger'], current_rule_reference)}")
    if not is_empty_rule_text(component.get("effect")):
        pieces.append(f"<h3>Effect</h3>{render_rich_text(component['effect'], current_rule_reference)}")
    if not pieces:
        return ""
    return f'<section class="{class_attr}"{style_attr}>{"".join(pieces)}</section>'
