# steps_oa

GT1M steps at 48 and 72 months and incident and progressive knee OA, in both directions.

**Direction A:** do steps/day at 48 months, and their change to 72 months, predict incident or progressing knee OA (radiographic, symptomatic, knee replacement, measured joint space width) to 96 months?

**Direction B:** does incident or progressing knee OA predict steps at 72 months or their change? This also checks the forward result for reverse causation: knees already worsening could make people walk less.

Knee OA outcomes come from the shared module `src/oai/derive/knee_outcomes.py`.

- **Spec:** [docs/superpowers/specs/2026-11-12-steps-oa-design.md](../../docs/superpowers/specs/2026-11-12-steps-oa-design.md)
- **Module spec:** [docs/superpowers/specs/2026-11-12-knee-outcomes-module-design.md](../../docs/superpowers/specs/2026-11-12-knee-outcomes-module-design.md)
- **Plan:** [docs/superpowers/plans/2026-11-12-steps-oa.md](../../docs/superpowers/plans/2026-11-12-steps-oa.md)
- **Assumptions:** [ASSUMPTIONS.md](ASSUMPTIONS.md)

The per-minute steps come from Northwestern (`OAI_STEPS_DIR`, never in the repo). Their terms: Jing (Northwestern analyst) is a co-author on publications that use them, and the PARR group offers scientific input.

```bash
uv run oai run steps_oa
```

## Results

None yet: the frames and models are not built (`build_frame.py` and `models.R` are placeholders).
