"""The gold labels are what every eval number rests on, so the rules get direct tests."""

from pipelines.build_world import Persona, coverage, fair_price_band, gold_evidence, label_for

STATS = {"groups": {
    "data_science": {"fixed": {"total_paid": {"p25": 50, "p75": 400}},
                     "hourly": {"hourly_rate": {"p25": 25, "p75": 60}}},
    "all": {"fixed": {"total_paid": {"p25": 40, "p75": 350}},
            "hourly": {"hourly_rate": {"p25": 12, "p75": 45}}},
}}

PERSONA = Persona(
    id="data_analyst", categories=["data_science"],
    true_skills={"SQL", "Microsoft Power BI", "Data Analysis", "Microsoft Excel"},
    listed_skills=["SQL"], rate_floor_hourly=18, min_fixed_budget=80,
    projects=[
        {"id": "p1", "year": 2025, "skills": ["Microsoft Power BI", "SQL"], "implied": []},
        {"id": "p2", "year": 2023, "skills": ["Microsoft Excel"], "implied": []},
        {"id": "p3", "year": 2024, "skills": ["Tableau"], "implied": ["SQL"]},
    ],
)


def job(**kw):
    base = {"job_id": "j1", "category": "data_science", "payment_type": "fixed",
            "budget_min": 500.0, "budget_max": 500.0}
    return {**base, **kw}


def test_coverage_ignores_generic_tags():
    assert coverage(["SQL", "English", "Smartphone"], PERSONA) == 1.0
    assert coverage(["SQL", "Tableau"], PERSONA) == 0.5
    assert coverage(["English"], PERSONA) == 0.0


def test_label_reason_order():
    skills = ["SQL", "Microsoft Power BI"]
    assert label_for(job(), skills, PERSONA, {"stratum": "fit"}, STATS)["bid"] is True
    scam = label_for(job(), skills, PERSONA, {"scam": True, "dup_of": "x", "stratum": "s"}, STATS)
    assert scam["skip_reason"] == "scam"  # scam beats duplicate
    assert label_for(job(), skills, PERSONA, {"dup_of": "j0", "stratum": "d"}, STATS)["skip_reason"] == "duplicate"
    assert label_for(job(category="marketing"), skills, PERSONA, {"stratum": "o"}, STATS)["skip_reason"] == "out_of_category"
    assert label_for(job(), ["Figma", "Blender"], PERSONA, {"stratum": "l"}, STATS)["skip_reason"] == "low_skill_coverage"
    cheap = job(budget_min=20.0, budget_max=20.0)
    assert label_for(cheap, skills, PERSONA, {"stratum": "f"}, STATS)["skip_reason"] == "budget_below_floor"


def test_unknown_budget_does_not_block_a_bid():
    lab = label_for(job(budget_min=None, budget_max=None), ["SQL"], PERSONA, {"stratum": "f"}, STATS)
    assert lab["bid"] is True


def test_fair_price_band():
    assert fair_price_band(job(), STATS) == {"min": 375.0, "max": 525.0, "unit": "usd_total",
                                             "basis": "client budget"}
    hourly = job(payment_type="hourly", budget_min=10.0, budget_max=80.0)
    assert fair_price_band(hourly, STATS)[("min")] == 25 and fair_price_band(hourly, STATS)["max"] == 60
    none = job(budget_min=None, budget_max=None)
    assert fair_price_band(none, STATS)["basis"] == "market p25-p75"


def test_gold_evidence_ranks_by_overlap_then_recency():
    # p1 covers both skills; p3 covers SQL via an implied skill; p2 covers neither.
    assert gold_evidence(["SQL", "Microsoft Power BI"], PERSONA) == ["p1", "p3"]


def test_missing_must_have_skips_even_with_good_coverage():
    skills = ["SQL", "Microsoft Power BI"]
    must = [{"skill": "Scrapy", "implied": False}]
    lab = label_for(job(), skills, PERSONA, {"stratum": "f"}, STATS, must_have=must)
    assert lab["skip_reason"] == "missing_must_have"
    half = [{"skill": "SQL", "implied": False}, {"skill": "Scrapy", "implied": True}]
    assert label_for(job(), skills, PERSONA, {"stratum": "f"}, STATS, must_have=half)["bid"] is True
