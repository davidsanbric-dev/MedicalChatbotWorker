"""Cut a clean record into passages: step 2 on https://medicalchatbot.demos.davieldev.com/worker

One passage for the symptom list, one per paragraph and one per list, following
the page's own structure instead of a fixed token window. Passage counts and
lengths are in the "Chunk stats" tab (#chunks); the "Audit & fixes" tab (#fixes)
shows a list passage before and after the v6 rendering.

Pure functions: the exact text that gets embedded is unit-tested.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    content_type: str  # "symptom" | "paragraph" | "list_item"
    content: str
    metadata: dict = field(default_factory=dict)


def build_chunks(content: dict, condition_name: str, processor_version: str) -> list[Chunk]:
    """Split one processed record into retrieval passages."""
    base = {"condition": condition_name, "processor_version": processor_version}
    chunks: list[Chunk] = []

    symptoms = content.get("symptoms")
    if isinstance(symptoms, list) and len(symptoms) >= 2:
        description, symptom_list = symptoms[0], symptoms[1]
        if isinstance(symptom_list, list) and symptom_list:
            text = f"{_label(description)} {', '.join(s.strip() for s in symptom_list if isinstance(s, str))}"
        else:
            text = str(description)
        chunks.append(Chunk("symptom", text.strip(), {**base, "source": "symptoms"}))

    section = content.get("onlineDiagnosingAndTreating", {})
    body = section.get("content", {}) if isinstance(section, dict) else {}
    if not isinstance(body, dict):
        return chunks

    for i, paragraph in enumerate(body.get("paragraphs", [])):
        if isinstance(paragraph, str) and paragraph.strip():
            chunks.append(Chunk("paragraph", paragraph.strip(), {**base, "source": "paragraph", "paragraph_index": i}))

    for i, block in enumerate(body.get("lists", [])):
        if text := render_list_block(block):
            chunks.append(Chunk("list_item", text, {**base, "source": "list", "list_index": i}))

    return chunks


def render_list_block(block: Any) -> str:
    """Turn one entry of `content.lists` into readable text.

    Handles every shape the processor emits (see _merge_related in processing.py):
      - [heading, {"items": [...]}]
      - [heading, description, {"items": [...]}]
      - [heading, description, {subheading: {"items": [...]}, ...}]
    """
    if isinstance(block, dict) and isinstance(block.get("items"), list):
        return "\n".join(_render_items(block["items"], 0))
    if not isinstance(block, list):
        return str(block).strip()

    prose: list[str] = []
    bullets: list[str] = []
    for part in block:
        if isinstance(part, str):
            if part.strip():
                prose.append(part.strip())
        elif isinstance(part, dict) and isinstance(part.get("items"), list):
            bullets.extend(_render_items(part["items"], 0))
        elif isinstance(part, dict):
            # {subheading: {"items": [...]} | [...]} produced by the merge rules
            for subheading, sub in part.items():
                bullets.append(f"- {_label(subheading)}")
                sub_items = sub.get("items", []) if isinstance(sub, dict) else sub
                bullets.extend(_render_items(sub_items if isinstance(sub_items, list) else [sub_items], 1))
        elif isinstance(part, list):
            bullets.extend(_render_items(part, 0))

    # A bare heading ("Risk Factors") must not run into the sentence after it.
    prose = [_label(p) for p in prose[:-1]] + prose[-1:]
    if prose and bullets:
        prose[-1] = _label(prose[-1])
    return "\n".join([" ".join(prose), *bullets] if prose else bullets).strip()


def _label(text: str) -> str:
    """A heading that introduces what follows ends with a colon, unless it is
    already terminated (":", or a full sentence ending in ".", "?" or "!")."""
    text = text.strip()
    return text if text and text[-1] in ".:?!" else f"{text}:"


def _render_items(items: list, depth: int) -> list[str]:
    """Processed list items as indented markdown bullets.

    Items are plain strings or [text, [subitems...]] pairs, nested to any depth.
    """
    lines: list[str] = []
    indent = "  " * depth
    for item in items:
        if isinstance(item, str):
            if item.strip():
                lines.append(f"{indent}- {item.strip()}")
        elif isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], list):
            lines.append(f"{indent}- {item[0].strip()}")
            lines.extend(_render_items(item[1], depth + 1))
        elif isinstance(item, list):
            lines.extend(_render_items(item, depth))
        elif isinstance(item, dict) and isinstance(item.get("items"), list):
            lines.extend(_render_items(item["items"], depth))
    return lines
