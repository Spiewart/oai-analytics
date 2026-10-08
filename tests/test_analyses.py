from pathlib import Path

import polars as pl
import pytest

from oai.catalog import catalog_for
from oai.config import get_settings
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
        "walking_validation",
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


def test_walking_validation_abstract_renders_after_the_brief_whose_figure_it_reuses():
    documents = load_analysis(REPO / "analyses" / "walking_validation").report.documents
    assert documents.index("abstract.qmd") > documents.index("brief.qmd")


def test_walking_validation_clinical_renders_after_the_documents_whose_figures_it_reuses():
    # clinical.qmd shows figures/brief_fig1.png (brief.qmd) and figures/tipping.png (report.qmd)
    documents = load_analysis(REPO / "analyses" / "walking_validation").report.documents
    assert documents.index("clinical.qmd") > documents.index("brief.qmd")
    assert documents.index("clinical.qmd") > documents.index("report.qmd")
