import pytest

from app.genealogy.kinship import blood_label, spouse_label


@pytest.mark.parametrize(
    ("d_from", "d_to", "sex", "expected"),
    [
        (0, 1, "M", "fils"),
        (0, 1, "F", "fille"),
        (0, 2, "F", "petite-fille"),
        (0, 3, "M", "arrière-petit-fils"),
        (1, 0, "M", "père"),
        (1, 0, "F", "mère"),
        (2, 0, "M", "grand-père"),
        (3, 0, "F", "arrière-grand-mère"),
        (1, 1, "M", "frère"),
        (1, 1, "F", "sœur"),
        (1, 2, "M", "neveu"),
        (1, 2, "F", "nièce"),
        (2, 1, "M", "oncle"),
        (2, 1, "F", "tante"),
        (3, 1, "M", "grand-oncle"),
        (2, 2, "M", "cousin germain"),
        (2, 2, "F", "cousine germaine"),
        (3, 3, "M", "cousin au 2e degré"),
        (4, 4, "F", "cousine au 3e degré"),
    ],
)
def test_blood_labels(d_from, d_to, sex, expected):
    assert blood_label(d_from, d_to, sex) == expected


def test_half_sibling():
    assert blood_label(1, 1, "F", half=True) == "demi-sœur"


def test_shifted_cousin():
    label = blood_label(2, 3, "M")
    assert label.startswith("cousin germain")
    assert "1 génération" in label


def test_far_ancestor():
    assert blood_label(6, 0, "M") == "ancêtre à la 6e génération"
    assert blood_label(0, 5, "F") == "descendante à la 5e génération"


def test_spouse():
    assert spouse_label("F") == "épouse"
    assert spouse_label("M") == "époux"
