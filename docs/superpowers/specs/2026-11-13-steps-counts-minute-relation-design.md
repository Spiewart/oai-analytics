# Steps vs activity counts within a minute (walking_steps Q1): design

## Intent

The Northwestern accelerometry group asked how per-minute GT1M step counts relate to per-minute activity counts at 48 and 72 months (their "Q1"). They proposed three plots that go from raw to summarised. The point is to show how the two measures line up before either is collapsed into categories. The plots go to that group in the existing exploratory `report.pdf`.

## Goals

- Plot 1: a hexbin of counts/min (x) against steps/min (y), one panel per wave, with vertical lines at the sedentary/light (100) and light/MV (2020) cutpoints.
- Plot 2: steps/min by count bin, as the median with the 25th–75th percentiles, one panel per wave.
- Plot 3: within each count bin, a 100% stacked bar of the step bands, one panel per wave.

## Non-goals

- No modelling or inference. The plots are descriptive.
- No new sample. Q1 uses exactly the minutes in the `share` step.
- No change to the existing steps, outputs or figures.

## Anti-goals

- No minute- or person-level data in results. The per-minute steps are not public, so only aggregates leave the machine.

## Approaches

1. **A new `walking_steps` step that writes aggregates, plus a section in `report.qmd`. Chosen.** It reuses the sample, ledger and report, it reruns when the group asks for changes, and the new bins are ledger entries.
2. A standalone figure script that saves PNGs. Quicker once, but it sits outside the run/report system and has no ledger entries.

## Decided

### By the user

- **Count bins (plots 2 and 3):** sedentary 0–99, light in four equal-width bins (100–499, 500–999, 1000–1499, 1500–2019), moderate 2020–5998, and vigorous ≥5999 (Troiano 2008).

### By Claude (the user can correct these)

- **Unit:** the wear minute, pooled over participants. This is the group's question: the spread of steps within a count bin.
- **Sample:** the minutes from `share.analysis_minutes()`, under the same ledger entries (`device.*`, `steps.day_rule`, `sample.min_step_days`). The two waves are kept separate.
- **Step bands (plot 3):** the existing `walking.band_edges` (0, 1–19, 20–39, … , 100–119, ≥120), which are exactly the group's bins.
- **Hexbin:**
  - The x-axis is linear and cut off at the 99.9th percentile of wear-minute counts per wave. The figure note gives the number of minutes beyond the cut-off.
  - The y-axis runs from 0 to 200 steps.
  - The fill is the number of minutes on a log scale.
  - The hexagon cells are computed in the step (Python), and the report draws them from the cell centres, so no minute data reach R.

### New ledger entries (`walking_steps/assumptions.toml`)

- `relation.count_bin_edges = [0, 100, 500, 1000, 1500, 2020, 5999]`, with `status = "confirmed"` (the user's choice). The light/MV edge must equal `device.mv_cutpoint`, and the step fails if it does not.
- `relation.hex_x_quantile = 0.999` (assumed).
- `relation.hex_gridsize`, the number of hexagons across the x-axis (assumed; the builder picks a value that reads well).

## Outputs (`$OAI_RESULTS_DIR/walking_steps/<label>/`)

- `relation_hex.csv`: visit, hexagon centre (x, y), number of minutes, plus the per-visit x cut-off and the number of minutes beyond it.
- `relation_bins.csv`: visit, count bin, number of minutes, and the 25th, 50th and 75th percentiles of steps.
- `relation_bands.csv`: visit, count bin, step band, number of minutes and share within the count bin.

## Left to the builder

- Wiring (a new `[[steps]]` entry, or an extension of `share`), with tests in `tests/test_walking_steps.py` on synthetic minutes.
- The exact grid size and figure styling, matching the existing report figures.
- README and manifest updates.
