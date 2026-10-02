import pytest

from oai.replication import grade, related_for, select_section, summarize

RELATED = {"flow": ["a"], "flow.knees": ["b", "c"], "t2": ["m"]}


def row(table, metric):
    return table.filter(table["metric"] == metric).row(0, named=True)


def test_related_uses_longest_prefix_on_dot_boundaries():
    assert related_for("flow.knees", RELATED) == ["b", "c"]
    assert related_for("flow.age50.persons", RELATED) == ["a"]
    assert related_for("flowx.y", RELATED) == []


@pytest.mark.parametrize(
    "published, ours, verdict",
    [(1808, 1760, "replicated"), (1808, 1700, "drift"), (13, 15, "replicated"), (13, 16, "drift")],
)
def test_count_tolerance(published, ours, verdict):
    assert (
        row(grade({"flow.knees": published}, {"flow.knees": ours}), "flow.knees")["verdict"]
        == verdict
    )


@pytest.mark.parametrize("ours, verdict", [(0, "replicated"), (1, "drift"), (None, "missing")])
def test_exact_count(ours, verdict):
    published = {"m.days": {"count": 0, "tol": 0}}  # the default tolerance would allow 2
    t = grade(published, {} if ours is None else {"m.days": ours})
    assert row(t, "m.days")["verdict"] == verdict
    assert row(t, "m.days")["published"] == "0" and row(t, "m.days")["kind"] == "count"


def test_count_with_an_absolute_tolerance():
    published = {"m.days": {"count": 100, "tol": 5}}
    assert row(grade(published, {"m.days": 105}), "m.days")["verdict"] == "replicated"
    assert row(grade(published, {"m.days": 106}), "m.days")["verdict"] == "drift"
    assert row(grade(published, {"m.days": 94}), "m.days")["verdict"] == "drift"


def test_count_within_a_share_of_another_metric():
    published = {"m.wear": {"count": 0, "tol_share": 0.005, "of": "m.matched"}}
    at_limit = grade(published, {"m.wear": 65, "m.matched": 13040})  # 0.5% of 13,040 is 65.2
    assert row(at_limit, "m.wear")["verdict"] == "replicated"
    assert row(at_limit, "m.wear")["published"] == "0 (within 0.5% of m.matched)"
    assert row(grade(published, {"m.wear": 66, "m.matched": 13040}), "m.wear")["verdict"] == "drift"
    assert row(grade(published, {"m.wear": 1}), "m.wear")["verdict"] == "missing"  # no base


def test_count_table_needs_a_tolerance():
    with pytest.raises(ValueError, match="m.days.*tol"):
        grade({"m.days": {"count": 3}}, {"m.days": 3})


def test_mean_tolerance_and_missing():
    t = grade({"t1.age_mean.all": 63.2, "t1.bmi_mean.all": 29.4}, {"t1.age_mean.all": 63.6})
    assert row(t, "t1.age_mean.all")["verdict"] == "replicated"
    assert row(t, "t1.bmi_mean.all")["verdict"] == "missing"


def test_or_tolerance_and_significance():
    pub = {"t2.x.or_adj": {"or": 0.6, "lo": 0.4, "hi": 0.8, "sig": True}}
    ok = {"t2.x.or_adj": 0.64, "t2.x.or_adj.lo": 0.47, "t2.x.or_adj.hi": 0.86}
    assert row(grade(pub, ok), "t2.x.or_adj")["verdict"] == "replicated"
    not_sig = {"t2.x.or_adj": 0.64, "t2.x.or_adj.lo": 0.40, "t2.x.or_adj.hi": 1.02}
    assert row(grade(pub, not_sig), "t2.x.or_adj")["verdict"] == "drift"
    assert row(grade(pub, {"t2.x.or_adj": 0.6}), "t2.x.or_adj")["verdict"] == "missing"


def test_or_significance_uses_published_flag():
    # "0.8 (0.6-1.0)" was reported as significant: the true upper bound was < 1 before rounding.
    pub = {"t2.j.or_adj": {"or": 0.8, "lo": 0.6, "hi": 1.0, "sig": True}}
    ours = {"t2.j.or_adj": 0.78, "t2.j.or_adj.lo": 0.61, "t2.j.or_adj.hi": 0.99}
    assert row(grade(pub, ours), "t2.j.or_adj")["verdict"] == "replicated"


def test_related_statuses_and_summary():
    t = grade({"flow.knees": 1808}, {"flow.knees": 1700}, RELATED, {"b": "assumed", "c": "open"})
    assert row(t, "flow.knees")["related"] == "b (assumed), c (open)"
    text = summarize(t, section="default", label="default")
    assert "0 replicated · 1 drift · 0 missing" in text
    assert "flow.knees" in text and "b (1)" in text


def test_select_section_matches_equivalent_overrides():
    published = {"related": {}, "default": {}, "missing_as_walkers": {}}
    sets = {
        "missing_as_walkers": {"cohort.impute": "walker"},
        "sens": {"model.corstr": "independence"},
    }
    base = {"cohort.impute": "none", "model.corstr": "exchangeable"}
    assert select_section(published, "missing_as_walkers", base, sets) == "missing_as_walkers"
    assert (
        select_section(published, None, {**base, "cohort.impute": "walker"}, sets)
        == "missing_as_walkers"
    )
    assert (
        select_section(published, "sens", {**base, "model.corstr": "independence"}, sets)
        == "default"
    )
    assert select_section(published, None, base, sets) == "default"
