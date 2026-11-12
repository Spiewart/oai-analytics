"""oai.derive.devices is the person-wave device code walking_steps uses (moved, unchanged)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyses" / "walking_steps"))

import devices  # noqa: E402

from oai.derive import devices as shared  # noqa: E402


def test_shared_module_is_walking_steps_module():
    for name in ("person_wave", "device_rules", "step_bouts_daily", "step_bout_measures"):
        assert getattr(shared, name) is getattr(devices, name), name
    assert shared.DEVICE_KEYS == devices.DEVICE_KEYS
    assert shared.COUNT_MEASURES == devices.COUNT_MEASURES
