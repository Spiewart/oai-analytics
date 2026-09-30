# /// script
# requires-python = ">=3.11"
# dependencies = ["pypandoc_binary>=1.13"]
# ///
"""Convert docs/reference/*.docx to GitHub-flavored Markdown next to the originals.

Run with `uv run scripts/docx_to_md.py` (pandoc ships inside pypandoc_binary).
"""

from pathlib import Path

import pypandoc

REFERENCE = Path(__file__).resolve().parents[1] / "docs" / "reference"


def main() -> None:
    for docx in sorted(REFERENCE.glob("*.docx")):
        md = docx.with_suffix(".md")
        pypandoc.convert_file(str(docx), "gfm", outputfile=str(md), extra_args=["--wrap=none"])
        print(f"wrote {md.name}")


if __name__ == "__main__":
    main()
