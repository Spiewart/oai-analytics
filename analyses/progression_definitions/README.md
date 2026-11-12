# progression_definitions

Knee-level progression endpoints from the [crosswalk](../../docs/reference/oai-progression-definition-crosswalk.md): KL ≥ 1 grade, incident ROA, OARSI JSN, FNIH medial minimum-JSW loss ≥ 0.7 mm, AKOA, WOMAC-based and TKR (Outcomes99). Outputs feed `genetics_progression` and future analyses; only per-definition prevalence tables are aggregate outputs.

Status: stub. The KL, JSN and measured-JSW (FNIH 0.7 mm) endpoints and knee-replacement times are built in the shared module `src/oai/derive/knee_outcomes.py` (`progression`, `jsw_change`, `replacement_times`); the former `src/oai/derive/progression.py` stubs are removed.
