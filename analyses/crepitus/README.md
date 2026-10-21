# Crepitus in the OAI

Sample sizes and event counts for every crepitus measure in the OAI, by visit and by enrollment cohort, to size a comprehensive analysis of crepitus and knee OA outcomes. Read `LITERATURE.md` first: it records what is already published and where the gaps are.

## Measures

| Name | Variables | Visits |
|---|---|---|
| `exam_crepitus` | `V##RKPFCRE`, `V##LKPFCRE` | V00, V01, V03, V05, V06, V12 |
| `exam_grind_pain` | `V##RKPGDPN`, `V##LKPGDPN` | V00, V01, V03, V05, V06 |
| `koos_s2` | `V##KSXRKN2`, `V##KSXLKN2` | V00 to V12 |

## Run

```bash
oai run crepitus                       # default
oai run crepitus --variant s2_any      # KOOS S2 exposed at any frequency
```

Outputs go to `$OAI_RESULTS_DIR/crepitus/<label>/`:

| File | Contents |
|---|---|
| `SAMPLE_SIZES.md` | The tables below in one readable file |
| `availability.csv` | Persons and knees with a non-missing value, and with crepitus present, per measure, visit and cohort. Visits that do not carry a measure appear with `collected = False` |
| `s2_distribution.csv` | KOOS S2 response counts (knees) per visit and cohort |
| `paired_exam_s2.csv` | Knees with both the exam item and S2 at one visit, as a 2 x 2 |
| `retention.csv` | Persons with a measure at baseline and at one or more later visits |
| `at_risk_events.csv` | Per outcome, cohort and baseline measure: knees at risk, knees ascertained, exposed and unexposed knees, and events in each |

## Cohorts

`cohort` is Enrollees `V00COHORT`: Progression (1,390), Incidence (3,284), Non-exposed control (122), plus an `All` row. These are the OAI's enrollment subcohorts, fixed at baseline. They are not outcome definitions. The outcomes below are knee-level and are reported within each cohort.

## Outcomes in `at_risk_events.csv`

| Outcome | At risk | Event |
|---|---|---|
| `incident_roa` | Native knee, baseline KL 0 or 1 | Follow-up KL of 2 or more at V01 to the horizon visit |
| `incident_soa` | Native knee without baseline symptomatic OA, with KL and frequent pain recorded | KL of 2 or more with frequent pain at the same follow-up visit (Lo 2018) |
| `kl_progression` | Native knee, baseline KL in the risk set (2 to 3 by default) | Follow-up KL at least one grade higher |
| `tkr_all` | Native knee at baseline | Counted knee replacement during follow-up |
| `tkr_roa` | As above, with baseline KL of 2 or more | As above |

Every choice here is in `assumptions.toml` (`ASSUMPTIONS.md` is the generated ledger). A knee enters an exposure's rows only if it has a baseline value of that measure and is ascertained for the outcome. `persons_at_risk` counts distinct participants; every other count is knees, and a person can contribute both knees.

## Reading the counts

- `persons` is a participant with at least one non-missing knee; `knees` is knee-visits with a value. Neither is an analytic n until an outcome's ascertainment rules are applied. `at_risk_events.csv` does that.
- The exam item was collected at fewer visits, and in the Non-exposed control cohort at baseline for only 31 of 122 people.
- Phone contacts V02 and V04 carry KOOS S2 for the Progression cohort only. V12 exams reached 1,801 people, mostly from the Incidence cohort.
- A check against the literature: right knees with no baseline symptomatic OA, a baseline S2 value and an outcome visit number 3,545. Lo 2018 reports 3,495 participants. The difference is not explained; the paper's exclusions were not read in full.

## Tests

`tests/test_crepitus.py` runs on synthetic knees. The counts above need the real release.
