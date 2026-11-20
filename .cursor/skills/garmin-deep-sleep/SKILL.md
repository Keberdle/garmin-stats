---
name: garmin-deep-sleep
description: >-
  Continue Garmin Connect deep-sleep precursor analysis in the garmin-stats project —
  fetch daily CSV from Garmin, analyze low/high Deep Sleep nights (P10/P90) and
  D-1..D-3 precursors (calories, steps, stress, sleep). Use when the user mentions
  Garmin stats, deep sleep, sleep anomalies, fetch_garmin_data, analyze_deep_sleep,
  or continues work described in AGENTS.md in this project.
---

# Garmin Deep Sleep precursors

## First step

Read [`AGENTS.md`](../../../AGENTS.md) in the project root (rules, setup, commands). If `AGENT.local.md` exists, it holds the owner's private state; never commit it.

Project path (typical):

`<project folder>`

## When to use

- Update Garmin daily CSV / download missing days
- Analyze nights with extreme Deep Sleep (low and high)
- Re-run charts after new sleep data
- Continue work from a previous session on this project

## Workflow

1. Prefer existing `.venv` in the project.
2. Refresh data, then analyze:

```bash
cd <project folder>
.venv/bin/python fetch_garmin_data.py
.venv/bin/python analyze_deep_sleep.py
```

3. Charts land in `output/`. Report thresholds, low/high tables, mirror section, top nights.

## Hard rules

- Do **not** treat fixed 3600 s Deep Sleep as an extreme by default — use P10/P90 (or CLI overrides).
- Do **not** use `garmin1.py` as the update path; it is a legacy Colab dump (asks for login interactively).
- Login comes from env `GARMIN_EMAIL` / `GARMIN_PASSWORD` or the git-ignored `config.env`; never hardcode credentials.
- Keep code comments in English; talk to the user in Czech (brief, factual).

## Scripts

| Script | Role |
|--------|------|
| `fetch_garmin_data.py` | Incremental fetch into `garmin_data_extended.csv` |
| `analyze_deep_sleep.py` | P10/P90 extremes, D-1..D-3 vs baseline, plots |

Useful CLI:

```bash
.venv/bin/python analyze_deep_sleep.py --percentile 10 --lag-days 3
.venv/bin/python analyze_deep_sleep.py --threshold-minutes-low 30
```

## Metrics in CSV

Active Calories, Total Steps, Distance, heart rates, Average Stress Level, Deep Sleep (s), REM Sleep (s), Measurable Asleep Duration (s).

## Expected analysis framing

- Low nights ≤ P10, high nights ≥ P90 of Deep Sleep in the last `--days` window (default 365)
- Precursor window: days before the extreme night (default D-1..D-3)
- Compare each extreme to baseline (non-extreme nights); show opposite (mirror) patterns
