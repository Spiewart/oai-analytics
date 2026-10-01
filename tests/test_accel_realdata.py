"""oai.derive.accel reproduces the release's accelerometry by-day files (real data)."""

import pytest

from oai.derive.accel import (
    DeviceRules,
    daily_summary,
    person_summary,
    read_minutes,
    release_valid_persons,
    reproduction,
)


@pytest.mark.realdata
@pytest.mark.parametrize("visit", ["06", "08"])
def test_reproduces_release_by_day_files(visit):
    rules = DeviceRules()
    daily = daily_summary(read_minutes(visit), rules)
    rep = reproduction(daily, visit, rules)
    assert rep["matched_days"] == rep["release_days"]
    assert rep["wear_mismatch_days"] <= 0.005 * rep["release_days"]
    assert rep["mv_mismatch_days"] == 0
    assert rep["bout_mismatch_days"] == 0
    ours = person_summary(daily, rules).filter("valid").height
    assert abs(ours - release_valid_persons(visit)) <= 1
