"""exam_crepitus_soa cohort step on the Lo 2018 synthetic release."""

import sys
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive import incident_soa

ANALYSES = Path(__file__).resolve().parents[1] / "analyses"
ANALYSIS = ANALYSES / "exam_crepitus_soa"
sys.path.insert(0, str(ANALYSIS))
sys.path.insert(0, str(ANALYSES / "lo2018_crepitus"))

import exam_soa  # noqa: E402
import lo2018  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "oai_lo2018"
KEYS = {
    "flow.all.persons",
    "flow.arthroplasty.excluded",
    "flow.no_baseline_kl.excluded",
    "flow.baseline_soa.excluded",
    "flow.no_outcome.excluded",
    "flow.persons",
    "obs.potential",
    "obs.missing_outcome",
    "obs.missing_crepitus",
    "obs.n",
    "obs.cases",
    "obs.cases.p1",
    "obs.cases.p2",
    "obs.cases.p3",
    "obs.cases.p4",
    "d.obs.yes",
    "d.obs.no",
    "d.base.yes",
    "d.base.no",
    "d.age_mean",
    "d.bmi_mean",
    "d.male",
}


@pytest.fixture(autouse=True)
def lo2018_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(FIXTURE))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def resolved(variant=None):
    return load_assumptions(ANALYSIS).resolve("exam_crepitus_soa", variant, {})


def run(A):
    soa = incident_soa.soa_status(A)
    cohort = incident_soa.build_cohort(A, soa)
    crep = incident_soa.crepitus_frame(A)
    require = exam_soa.require_for(A)
    frame, counts = incident_soa.periods(A, cohort, soa, crep, require=require)
    persons = incident_soa.four_year(cohort, soa, crep, require=require)
    return cohort, frame, counts, persons, soa, crep


def test_require_for():
    assert exam_soa.require_for(resolved()) == ("exam_crepitus",)
    assert exam_soa.require_for(resolved("require_s2")) == ("exam_crepitus", "koos_s2")


def test_exposure_metrics_keys():
    cohort, frame, counts, persons, *_ = run(resolved())
    values = dict(exam_soa.exposure_metrics(cohort, frame, counts, persons).iter_rows())
    assert set(values) == KEYS
    assert values["d.base.yes"] + values["d.base.no"] == persons.height
    assert values["d.obs.yes"] + values["d.obs.no"] == values["obs.n"] == frame.height


def test_flow_is_lo2018s():
    A = resolved()
    cohort, frame, counts, persons, soa, crep = run(A)
    ours = dict(exam_soa.exposure_metrics(cohort, frame, counts, persons).iter_rows())
    s2_frame, s2_counts = incident_soa.periods(A, cohort, soa, crep)
    theirs = dict(
        lo2018.cohort_metrics(
            cohort, s2_frame, s2_counts, incident_soa.four_year(cohort, soa, crep)
        ).iter_rows()
    )
    for key in (k for k in KEYS if k.startswith("flow.")):
        assert ours[key] == theirs[key], key
    assert isinstance(frame, pl.DataFrame)
