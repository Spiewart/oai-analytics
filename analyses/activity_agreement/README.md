# activity_agreement

Agreement between OAI self-reported activity (PASE; 96-month walking-for-exercise item) and the 48-month ActiGraph accelerometer substudy. Plan: [`docs/reference/oai-activity-agreement-analysis-plan.md`](../../docs/reference/oai-activity-agreement-analysis-plan.md) §1–9.

| Step | Stage | Does |
|---|---|---|
| `frame` (`build_frame.py`) | local | Samples A–C; device endpoints (90-min non-wear, ≥10 h valid day); PASE total + walking subscore |
| `agreement` (`agreement.R`) | local | Spearman + deattenuation, Bland–Altman, κ, ROC cutpoint, bias regression |

Status: stub.
