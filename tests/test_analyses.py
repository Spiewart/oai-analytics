from pathlib import Path

import polars as pl
import pytest

from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive.accel import valid_wear_days
from oai.derive.pase import score_pase
from oai.derive.progression import fnih_jsw_progressor, kl_progression
from oai.manifest import load_analysis

REPO = Path(__file__).resolve().parents[1]
ANALYSES = sorted(p.parent.name for p in (REPO / "analyses").glob("*/analysis.toml"))


def test_expected_analyses_exist():
    assert ANALYSES == [
        "activity_agreement",
        "genetics_progression",
        "lo2022_walking",
        "progression_definitions",
    ]


@pytest.mark.parametrize("name", ANALYSES)
def test_manifest_is_valid(name):
    assert load_analysis(REPO / "analyses" / name).name == name


def test_genetics_exports_an_id_keyed_frame_to_the_enclave():
    a = load_analysis(REPO / "analyses" / "genetics_progression")
    assert a.stages == {"local", "enclave"}
    assert a.export is not None and a.export.columns[0] == "ID"


@pytest.mark.parametrize(
    "call",
    [
        lambda: score_pase(pl.DataFrame(), "V06"),
        lambda: valid_wear_days(pl.LazyFrame()),
        lambda: kl_progression(pl.DataFrame()),
        lambda: fnih_jsw_progressor(pl.DataFrame()),
    ],
)
def test_derive_stubs_point_to_reference_docs(call):
    with pytest.raises(NotImplementedError, match="docs/reference"):
        call()


@pytest.mark.realdata
@pytest.mark.parametrize("name", ANALYSES)
def test_inputs_resolve_against_real_release(name):
    catalog = catalog_for(get_settings().data_dir)
    for spec in load_analysis(REPO / "analyses" / name).inputs:
        assert catalog.resolve_input(spec), spec
