# crepitus_activity

Crepitus and device-measured activity at 48 and 72 months, in both directions.

**Direction A:** do crepitus at a visit, or its change between visits, predict GT1M steps/day and MV and light minutes/day, or their change from 48 to 72 months?

**Direction B:** do activity at 48 months, and its change to 72 months, predict:
- KOOS S2 crepitus at 72 and 96 months;
- new exam crepitus at 120 months?

- **Spec:** [docs/superpowers/specs/2026-11-12-crepitus-activity-design.md](../../docs/superpowers/specs/2026-11-12-crepitus-activity-design.md)
- **Plan:** [docs/superpowers/plans/2026-11-12-crepitus-activity.md](../../docs/superpowers/plans/2026-11-12-crepitus-activity.md)
- **Assumptions:** [ASSUMPTIONS.md](ASSUMPTIONS.md)

The per-minute steps come from Northwestern (`OAI_STEPS_DIR`, never in the repo). Their terms: Jing is a co-author on publications that use them, and the PARR group offers input.

```bash
uv run oai run crepitus_activity
```

## Results

Not yet run.
