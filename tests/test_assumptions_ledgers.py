"""Every committed ASSUMPTIONS.md must match what `oai assumptions NAME --write` produces."""

from pathlib import Path

import pytest

from oai.assumptions import LEDGER_FILE, load_assumptions, render_ledger

REPO = Path(__file__).resolve().parents[1]
WITH_ASSUMPTIONS = sorted(p.parent for p in (REPO / "analyses").glob("*/assumptions.toml"))


@pytest.mark.parametrize("root", WITH_ASSUMPTIONS, ids=lambda p: p.name)
def test_ledger_is_in_sync(root):
    ledger = root / LEDGER_FILE
    assert ledger.is_file(), f"run `oai assumptions {root.name} --write`"
    assert ledger.read_text() == render_ledger(root.name, load_assumptions(root)), (
        f"{ledger} is stale: run `oai assumptions {root.name} --write`"
    )
