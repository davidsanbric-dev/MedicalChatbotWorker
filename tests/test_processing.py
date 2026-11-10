from services.processing import condition_name, condition_name_of, process_page

NBSP = " "


def test_condition_name_strips_title_boilerplate():
    assert condition_name("Acne treatment online") == "Acne"
    assert condition_name("Anxiety advice and refills online") == "Anxiety"
    assert condition_name("Online care for bug bites") == "Bug bites"
    assert condition_name(f"Ear pain{NBSP}treatment online") == "Ear pain"


def test_condition_name_falls_back_to_the_slug():
    assert condition_name_of({}, "ear-pain") == "ear_pain"


def clinical_text(*blocks: dict) -> dict:
    return process_page({"onlineDiagnosingAndTreating": {"heading": "H", "content": list(blocks)}})[
        "onlineDiagnosingAndTreating"
    ]["content"]


def test_symptoms_become_heading_and_list():
    page = {"symptoms": {"heading": f"Patients{NBSP}experience", "list": ["Cough"]}}
    assert process_page(page)["symptoms"] == ["Patients experience", ["Cough"]]


def test_related_blocks_merge():
    lead_in = {"type": "strong_paragraph", "text": "Diagnosis"}
    paragraph = {"type": "paragraph", "text": "A doctor asks questions."}
    bullets = {"type": "ul", "items": [{"text": "Rest"}]}

    assert clinical_text(lead_in, paragraph) == {"paragraphs": ["Diagnosis: A doctor asks questions."], "lists": []}
    assert clinical_text(paragraph, bullets) == {"paragraphs": [], "lists": [["A doctor asks questions.", {"items": ["Rest"]}]]}
    assert clinical_text(lead_in, paragraph, bullets)["lists"] == [["Diagnosis", "A doctor asks questions.", {"items": ["Rest"]}]]


def test_lead_in_with_two_labelled_lists_merges_into_one_block():
    content = clinical_text(
        {"type": "strong_paragraph", "text": "Treatment"},
        {"type": "paragraph", "text": "Options vary."},
        {"type": "strong_paragraph", "text": "At home:"},
        {"type": "ul", "items": [{"text": "Rest"}]},
        {"type": "strong_paragraph", "text": "With a doctor:"},
        {"type": "ul", "items": [{"text": "Antibiotics"}]},
    )
    assert content["lists"] == [
        ["Treatment", "Options vary.", {"At home:": {"items": ["Rest"]}, "With a doctor:": {"items": ["Antibiotics"]}}]
    ]


def test_list_items_are_cleaned():
    bullets = {
        "type": "ul",
        "items": [
            {"text": "For mild acne: start here", "subitems": [{"text": " Gentle cleansing "}, {"text": "Gentle cleansing"}]},
            {"text": "Gentle cleansing"},  # already listed as a sub-item
            {"text": "Retinoids"},
        ],
    }
    assert clinical_text(bullets)["lists"] == [{"items": [["For mild acne:", ["Gentle cleansing"]], "Retinoids"]}]


def test_a_list_repeating_an_earlier_one_is_dropped():
    first = {"type": "ul", "items": [{"text": "C"}, {"text": "D"}]}
    same_items_reordered = {"type": "ul", "items": [{"text": "D"}, {"text": "C"}]}
    assert clinical_text(first, same_items_reordered)["lists"] == [{"items": ["C", "D"]}]


def test_a_list_repeating_nested_sub_items_is_dropped():
    nested = {"type": "ul", "items": [{"text": "Options:", "subitems": [{"text": "A"}, {"text": "B"}]}]}
    flat_repeat = {"type": "ul", "items": [{"text": "B"}, {"text": "A"}]}
    assert clinical_text(nested, flat_repeat)["lists"] == [{"items": [["Options:", ["A", "B"]]]}]


def test_only_standalone_lists_are_deduplicated():
    bullets = {"type": "ul", "items": [{"text": "C"}]}
    intro = {"type": "paragraph", "text": "Also:"}
    # The paragraph merges with the list after it, so that copy is part of a block and stays.
    assert clinical_text(bullets, intro, bullets)["lists"] == [{"items": ["C"]}, ["Also:", {"items": ["C"]}]]


def test_input_is_not_modified():
    page = {"onlineDiagnosingAndTreating": {"content": [{"type": "paragraph", "text": "P"}]}}
    process_page(page)
    assert page == {"onlineDiagnosingAndTreating": {"content": [{"type": "paragraph", "text": "P"}]}}
