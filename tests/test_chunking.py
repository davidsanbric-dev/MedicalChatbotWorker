from services.chunking import build_chunks, normalize_content, normalize_text, render_list_block

NBSP = " "


def test_normalize_text_replaces_non_breaking_spaces():
    assert normalize_text(f"Diagnosing{NBSP}and Treating Acne{NBSP} Online") == "Diagnosing and Treating Acne Online"


def test_normalize_content_walks_nested_structures():
    content = {"a": [f"x{NBSP}y", {"b": f"z{NBSP}"}], "n": 3}
    assert normalize_content(content) == {"a": ["x y", {"b": "z"}], "n": 3}


def test_nested_list_items_render_as_bullets_not_python_syntax():
    block = [
        "Options for treatment of acne may include:",
        {"items": [
            ["For mild acne:", ["Gentle cleansing", "Applying salicylic acid"]],
            ["For moderate to severe acne:", ["Benzoyl peroxide", ["A prescription for:", ["Retinoids", "Azelaic acid"]]]],
        ]},
    ]
    text = render_list_block(block)
    assert "['" not in text and "::" not in text
    assert text == "\n".join([
        "Options for treatment of acne may include:",
        "- For mild acne:",
        "  - Gentle cleansing",
        "  - Applying salicylic acid",
        "- For moderate to severe acne:",
        "  - Benzoyl peroxide",
        "  - A prescription for:",
        "    - Retinoids",
        "    - Azelaic acid",
    ])


def test_heading_description_items_shape_keeps_its_items():
    # Previously embedded as "heading: description" with every item dropped.
    block = ["Risk Factors", "Some risk factors include", {"items": ["A family history", "Stress"]}]
    assert render_list_block(block) == (
        "Risk Factors: Some risk factors include:\n- A family history\n- Stress"
    )


def test_subheading_mapping_shape():
    block = ["Treatment", "Options vary.", {"At home:": {"items": ["Rest"]}, "With a doctor": ["Antibiotics"]}]
    assert render_list_block(block) == (
        "Treatment: Options vary.\n- At home:\n  - Rest\n- With a doctor:\n  - Antibiotics"
    )


def test_build_chunks_follows_document_structure():
    content = {
        "symptoms": ["Acne symptoms can vary, but patients typically experience", ["Blackheads", "Cysts"]],
        "onlineDiagnosingAndTreating": {
            "content": {
                "paragraphs": ["First paragraph.", "  ", "Second paragraph."],
                "lists": [["Options include:", {"items": ["A", "B"]}]],
            }
        },
    }
    chunks = build_chunks(content, "Acne", "v6")

    assert [c.content_type for c in chunks] == ["symptom", "paragraph", "paragraph", "list_item"]
    assert chunks[0].content == "Acne symptoms can vary, but patients typically experience: Blackheads, Cysts"
    assert chunks[2].metadata == {
        "condition": "Acne", "processor_version": "v6", "source": "paragraph", "paragraph_index": 2,
    }
    assert chunks[3].content == "Options include:\n- A\n- B"


def test_build_chunks_respects_content_type_filter():
    content = {"symptoms": ["Signs:", ["Cough"]], "onlineDiagnosingAndTreating": {"content": {"paragraphs": ["P"]}}}
    assert [c.content_type for c in build_chunks(content, "Flu", "v6", ["paragraphs"])] == ["paragraph"]
