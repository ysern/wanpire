"""The logo proposals: three forms each, well-formed, self-contained (spec: logo)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

DIR = Path(__file__).resolve().parents[2] / "docs" / "logo-proposals"
PROPOSALS = ["a-on-the-line", "b-count", "c-bite", "d-emblem"]
FORMS = ["full", "mono", "favicon"]
NS = "{http://www.w3.org/2000/svg}"


def colours(text: str) -> set[str]:
    found = set(c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", text))
    found |= set(re.findall(r"\b(?:fill|stroke)=\"(?!none|url|#|currentColor)([a-z]+)\"", text))
    return found


@pytest.mark.parametrize("name", PROPOSALS)
@pytest.mark.parametrize("form", FORMS)
def test_a_form_is_well_formed_and_self_contained(name, form):
    path = DIR / f"{name}-{form}.svg"
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.tag == f"{NS}svg"
    assert root.get("viewBox")
    assert not re.search(r"(href|src)=\"(?!#)", text), "nothing outside the file"
    assert "<text" not in text and "<image" not in text
    assert not re.search(r"raspberry|\bpi\b", text, re.I)


@pytest.mark.parametrize("name", PROPOSALS)
def test_the_mono_form_uses_one_colour(name):
    text = (DIR / f"{name}-mono.svg").read_text(encoding="utf-8")
    # mask contents (white and black) are not ink
    ink = re.sub(r"<mask.*?</mask>", "", text, flags=re.S)
    assert len(colours(ink)) == 1, colours(ink)


def test_the_proposals_are_shown_side_by_side():
    readme = (DIR / "README.md").read_text(encoding="utf-8")
    for name in PROPOSALS:
        for form in FORMS:
            assert f"{name}-{form}.svg" in readme
