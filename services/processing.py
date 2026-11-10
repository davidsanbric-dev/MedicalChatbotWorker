"""Tidy up a scraped page into a clean record: step 1 on
https://medicalchatbot.demos.davieldev.com/worker
The "One record, three forms" tab (#stages) shows a real record before and after.

Pure functions: no database and no model, so the rules are unit-tested.
"""

import re
import unicodedata
from collections.abc import Iterator
from typing import Any

# Bump whenever the output changes: the next run then replaces what an older
# version produced (and its documents) instead of skipping it.
#   v5: restructure, merge and deduplicate
#   v6: + Unicode normalization (NFKC: non-breaking spaces become plain spaces)
PROCESSOR_VERSION = "v6"

TITLE_SUFFIXES = (
    " treatment online",
    " advice and refills online",
    " online",
    " | medical for patients",
    " - medical",
    " — online care",
)
TITLE_PREFIXES = ("online relief for ", "get telehealth care for ", "online care for ")

_SPACE_RUNS = re.compile(r"[ \t]{2,}")


def normalize_text(value: str) -> str:
    """NFKC-normalize (U+00A0 and other compatibility spaces become plain spaces), then collapse space runs."""
    return _SPACE_RUNS.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def normalize_content(value: Any) -> Any:
    """normalize_text applied to every string inside a JSON-like structure."""
    match value:
        case str():
            return normalize_text(value)
        case list():
            return [normalize_content(item) for item in value]
        case dict():
            return {key: normalize_content(item) for key, item in value.items()}
    return value


def condition_name(title: str) -> str:
    """The display name in a page title: "Acne treatment online" → "Acne", "Online care for bug bites" → "Bug bites"."""
    name = normalize_text(title)
    for suffix in TITLE_SUFFIXES:
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)].strip()
    had_prefix = False
    for prefix in TITLE_PREFIXES:
        if name.lower().startswith(prefix):
            name, had_prefix = name[len(prefix):].strip(), True
    return name[:1].upper() + name[1:] if had_prefix else name


def condition_name_of(page: dict, slug: str) -> str:
    """From the page title, or from the slug for a page without one."""
    return condition_name(page["title"] or "") if "title" in page else slug.replace("-", "_")


def process_page(page: dict) -> dict:
    """Raw page → clean record.

    The symptom card becomes [heading, symptoms], and the clinical text becomes
    {"paragraphs": [...], "lists": [...]}, where related blocks are merged and
    repeated lists dropped. Every string is normalized.
    """
    record = dict(page)
    symptoms = page.get("symptoms")
    if isinstance(symptoms, dict) and "heading" in symptoms and "list" in symptoms:
        record["symptoms"] = [symptoms["heading"], symptoms["list"]]

    clinical_text = page.get("onlineDiagnosingAndTreating")
    if isinstance(clinical_text, dict) and "content" in clinical_text:
        blocks = _drop_repeated_lists(_merge_related([_simplify(block) for block in clinical_text["content"]]))
        record["onlineDiagnosingAndTreating"] = {
            **clinical_text,
            "content": {
                "paragraphs": [block for block in blocks if isinstance(block, str)],
                "lists": [block for block in blocks if not isinstance(block, str)],
            },
        }
    return normalize_content(record)


# --- 1. Simplify each typed block from the scraper ---------------------------


def _simplify(block: Any) -> Any:
    """A paragraph becomes its text; a bold lead-in keeps {"text"}; a list keeps its cleaned {"items"}."""
    if not isinstance(block, dict):
        return block
    if "text" in block and block.get("type", "paragraph") == "paragraph":
        return block["text"]
    simplified = {key: value for key, value in block.items() if key != "type"}
    if "items" in block:
        simplified["items"] = _clean_items(block["items"], seen=set())
    return simplified


def _clean_items(items: list, seen: set[str]) -> list:
    """Top-level list items: stripped, without repeats, nested lists kept as [lead-in, sub-items].

    A lead-in is cut at its colon ("For mild acne: try…" → "For mild acne:").
    """
    cleaned: list = []
    for item in items:
        match item:
            case str():
                _keep_if_new(item.strip(), cleaned, seen)
            case {"subitems": subitems}:
                lead_in = _cut_at_colon(item.get("text", "").strip())
                if nested := _clean_subitems(subitems, seen):
                    cleaned.append([lead_in, nested])
                    seen.add(lead_in)
                elif lead_in:
                    cleaned.append(lead_in)
                    seen.add(lead_in)
            case dict():
                _keep_if_new(item.get("text", "").strip(), cleaned, seen)
    return cleaned


def _clean_subitems(subitems: list, seen: set[str]) -> list:
    """Nested items, at any depth. Repeats are dropped across the whole list (`seen` is shared)."""
    cleaned: list = []
    for item in subitems:
        match item:
            case str():
                _keep_if_new(item.strip(), cleaned, seen)
            case {"subitems": nested_items}:
                text = item.get("text", "").strip()
                if nested := _clean_subitems(nested_items, seen):
                    cleaned.append([text, nested])
                elif text:
                    cleaned.append(text)
            case dict():
                _keep_if_new(item.get("text", "").strip(), cleaned, seen)
            case list():
                cleaned.extend(_clean_subitems(item, seen))
    return cleaned


def _keep_if_new(text: str, cleaned: list, seen: set[str]) -> None:
    if text and text not in seen:
        cleaned.append(text)
        seen.add(text)


def _cut_at_colon(text: str) -> str:
    head, colon, _ = text.partition(":")
    return f"{head.strip()}:" if colon else text


# --- 2. Merge blocks that belong together -------------------------------------


def _merge_related(blocks: list) -> list:
    """Join each heading, intro paragraph and list that read as one unit.

    After _simplify, a bold lead-in is {"text": ...}, a paragraph is a str and a
    list is {"items": [...]}. The first matching rule wins:
      lead-in + paragraph + lead-in: + list + lead-in: + list → [lead-in, paragraph, {lead-in: list, lead-in: list}]
      lead-in + paragraph + list                              → [lead-in, paragraph, list]
      lead-in + paragraph                                     → "lead-in: paragraph"
      lead-in + list                                          → [lead-in, list]
      paragraph + list                                        → [paragraph, list]
    """
    merged: list = []
    i = 0
    while i < len(blocks):
        match blocks[i : i + 6]:
            case [
                {"text": heading},
                str(intro),
                {"text": first_label},
                {"items": _} as first_list,
                {"text": second_label},
                {"items": _} as second_list,
            ] if _ends_with_colon(first_label) and _ends_with_colon(second_label):
                merged.append([heading, intro, {first_label: first_list, second_label: second_list}])
                i += 6
            case [{"text": heading}, str(intro), {"items": _} as items, *_]:
                merged.append([heading, intro, items])
                i += 3
            case [{"text": heading}, str(paragraph), *_]:
                merged.append(f"{heading}: {paragraph}")
                i += 2
            case [{"text": heading}, {"items": _} as items, *_]:
                merged.append([heading, items])
                i += 2
            case [str(paragraph), {"items": _} as items, *_]:
                merged.append([paragraph, items])
                i += 2
            case [block, *_]:
                merged.append(block)
                i += 1
    return merged


def _ends_with_colon(label: str) -> bool:
    return label.strip().endswith(":")


# --- 3. Drop lists that repeat others -----------------------------------------


def _drop_repeated_lists(blocks: list) -> list:
    """Drop a standalone list that repeats an earlier one (in any order), or whose items
    are just the sub-items of a nested list elsewhere on the page."""
    standalone_lists = [block for block in blocks if _is_list(block)]
    sublist_keys = {key for block in standalone_lists for item in block["items"] for key in _sublist_keys(item)}
    seen: set[tuple] = set()
    kept = []
    for block in blocks:
        if not _is_list(block):
            kept.append(block)
            continue
        key = _items_key(block["items"])
        repeats_a_sublist = all(isinstance(item, str) for item in block["items"]) and key in sublist_keys
        if key not in seen and not repeats_a_sublist:
            kept.append(block)
            seen.add(key)
    return kept


def _is_list(block: Any) -> bool:
    return isinstance(block, dict) and "items" in block


def _items_key(items: list) -> tuple:
    """An order-insensitive, hashable fingerprint of a list's items."""
    return tuple(sorted((key for item in items if (key := _item_key(item)) is not None), key=str))


def _item_key(item: Any) -> Any:
    match item:
        case str():
            return item.strip()
        case [text, subitems] if isinstance(item, list):
            return str(text).strip(), _items_key(subitems) if isinstance(subitems, (list, tuple)) else ()
        case {"subitems": subitems}:
            return item.get("text", "").strip(), _items_key(subitems)
        case dict():
            return item.get("text", "").strip()
    return None


def _sublist_keys(item: Any) -> Iterator[tuple]:
    """Fingerprints of every nested sub-list inside one list item, at any depth."""
    if isinstance(item, dict) and "subitems" in item:
        sublist = item["subitems"]
    elif isinstance(item, list) and len(item) == 2 and isinstance(item[1], list):
        sublist = item[1]
    else:
        return
    yield _items_key(sublist)
    for subitem in sublist:
        if isinstance(subitem, (dict, list)):
            yield from _sublist_keys(subitem)
