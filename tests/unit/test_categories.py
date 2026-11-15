import pytest

from pipelines.categories import categorise


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("React Developer", "development"),
        ("WordPress Theme Development - Javascript, PHP", "development"),
        ("PowerBI Dashboard Creator", "data_science"),
        ("Machine learning model for churn", "data_science"),
        ("Google Ads Expert", "marketing"),
        ("Facebook advertiser needed to increase sales", "marketing"),
        ("3D Architectural Render", "3d_design"),
        ("Jewelry CAD designer", "3d_design"),
        ("Translation of an English medical form into Spanish", "other"),
        ("Create logo designs", "other"),
    ],
)
def test_categorise(title, expected):
    assert categorise(title) == expected


def test_keywords_match_whole_words_only():
    # "ml" must not match inside "html"; "api" not inside "capital".
    assert categorise("HTML email template") == "development"
    assert categorise("Capital raising deck") == "other"


def test_non_string_is_other():
    assert categorise(None) == "other"
