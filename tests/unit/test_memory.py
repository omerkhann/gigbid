from langgraph.store.memory import InMemoryStore

from agent.memory.store import edit_patterns, forget, record_edit, record_outcome, style_rules

ORIG = ("I am a passionate developer with years of experience. Your store needs a faster checkout. "
        "I rebuilt checkout for a fitness brand and conversion rose 34%. Best regards")
EDIT = "Your store needs a faster checkout. I rebuilt checkout for a fitness brand and conversion rose 34%."


def test_edit_patterns():
    p = edit_patterns(ORIG, EDIT)
    assert {"cut_first_sentence", "shortened", "removed_sign_off", "never_say:passionate"} <= p


def test_promotion_needs_three_consistent_edits():
    store = InMemoryStore()
    assert record_edit(store, "u1", ORIG, EDIT, "p1") == []
    assert record_edit(store, "u1", ORIG, EDIT, "p2") == []
    promoted = record_edit(store, "u1", ORIG, EDIT, "p3")
    assert "cut_first_sentence" in promoted and "never_say:passionate" in promoted
    assert any("passionate" in r for r in style_rules(store, "u1"))
    assert style_rules(store, "u2") == []                       # per user


def test_contradictory_edits_do_not_promote():
    store = InMemoryStore()
    short, long = "Short text here.", "Short text here. " * 10
    for i in range(3):
        record_edit(store, "u1", long, short, f"s{i}")       # shortened x3
        record_edit(store, "u1", short, long, f"l{i}")       # lengthened x3
    rules = style_rules(store, "u1")
    assert not any("shorter" in r or "more detail" in r for r in rules)
    for i in range(3, 7):                    # 7 vs 3: a now-clear habit (3 < 7/2) does promote
        record_edit(store, "u1", long, short, f"s{i}")
    assert any("shorter" in r for r in style_rules(store, "u1"))


def test_forget_removes_rule():
    store = InMemoryStore()
    for i in range(3):
        record_edit(store, "u1", ORIG, EDIT, f"p{i}")
    forget(store, "u1", "style", "never_say:passionate")
    assert not any("passionate" in r for r in style_rules(store, "u1"))


def test_outcome_memory_only_records_final_statuses_of_our_proposals():
    store = InMemoryStore()
    assert record_outcome(store, "u1", "data_science", "replied", True)
    assert not record_outcome(store, "u1", "data_science", "submitted", True)   # not final
    assert not record_outcome(store, "u1", "data_science", "hired", False)      # not ours
    assert store.get(("outcome", "u1"), "data_science").value["replied"] == 1
