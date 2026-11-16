"""Step `compare`: grade device reproduction and sample sizes against expected.toml."""

from pathlib import Path

from wv import without_ungradable_device_rows

from oai.assumptions import current, load_assumptions
from oai.replication import compare_step

A = current()
defaults = {key: item.value for key, item in load_assumptions(Path.cwd()).items.items()}
skipped: dict[str, list[str]] = {}


def gradable(rows):
    """The section's rows without device.* rows a changed device rule makes ungradable."""
    kept, skipped["changed"], skipped["omitted"] = without_ungradable_device_rows(
        rows, A.values, defaults
    )
    return kept


compare_step("expected.toml", rows=gradable)
if skipped["omitted"]:
    print(
        f"\nNot graded: {len(skipped['omitted'])} device.* rows ({', '.join(skipped['omitted'])}), "
        f"because this run changes the device rules {', '.join(skipped['changed'])}; they are the "
        "release's own counts"
    )
