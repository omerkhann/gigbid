from pipelines.parsing import (
    clean_text,
    mask_pii,
    normalise_for_dedup,
    parse_duration,
    parse_hours_ago,
    parse_money,
    parse_money_range,
    stable_id,
)


def test_parse_money():
    assert parse_money("$2,500 ") == 2500.0
    assert parse_money("$15.00 ") == 15.0
    assert parse_money("0") is None  # 60k dataset uses "0" for "no rate"
    assert parse_money(None) is None
    assert parse_money(float("nan")) is None


def test_parse_money_range():
    assert parse_money_range("$15.00-$30.00") == (15.0, 30.0)
    assert parse_money_range("$30-$15") == (15.0, 30.0)
    assert parse_money_range("$20") == (20.0, 20.0)
    assert parse_money_range(None) == (None, None)


def test_parse_hours_ago():
    assert parse_hours_ago("3 days ago") == 72.0
    assert parse_hours_ago("1 hour ago") == 1.0
    assert parse_hours_ago("30 minutes ago") == 0.5
    assert parse_hours_ago("yesterday") is None


def test_parse_duration():
    assert parse_duration("1 to 3 months, Less than 30 hrs/week") == (
        "1 to 3 months", "Less than 30 hrs/week")
    assert parse_duration(None) == (None, None)


def test_mask_pii_masks_contacts_but_not_word_counts():
    text = "Email me at jo.doe+work@mail.co.uk or call +1 (555) 123-4567."
    assert mask_pii(text) == "Email me at [EMAIL] or call [PHONE]."
    assert mask_pii("Write 1000 - 2000 words") == "Write 1000 - 2000 words"
    assert mask_pii("Budget 2023-2024") == "Budget 2023-2024"


def test_mask_pii_leaves_ids_inside_urls():
    url = "see https://arxiv.org/pdf/2301.123456789.pdf and call 0300 1234567"
    assert mask_pii(url) == "see https://arxiv.org/pdf/2301.123456789.pdf and call [PHONE]"


def test_clean_text():
    assert clean_text("Fish &amp; chips   now\n\n\n\nok") == "Fish & chips now\n\nok"
    assert clean_text(None) == ""


def test_dedup_normalisation_and_ids():
    assert normalise_for_dedup("Need a LOGO!!") == normalise_for_dedup("need a logo")
    assert stable_id("job", "u1") == stable_id("job", "u1") != stable_id("job", "u2")
