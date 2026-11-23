# AGENTS.md — garmin-stats

Instructions for an AI agent (Claude Code, Cursor, Codex …) helping a user with this project. Talk to the user in their language; the user may not be a programmer. Code comments in English.

## Purpose

Download the user's daily Garmin Connect data into a local CSV and find what precedes nights with extremely low or high Deep Sleep (activity, calories, stress, heart rate, sleep length on D-1 … D-3).

## Hard rules

1. **Credentials:** the login lives only in `config.env` (git-ignored) or in env `GARMIN_EMAIL` / `GARMIN_PASSWORD`. Never print, log, commit or paste it into chat; never hardcode it. Ask the user to fill `config.env` themselves; do not ask them to send you the password.
2. **Health data stays local:** `garmin_data_extended.csv`, `output/` and any notes with the user's numbers are personal health data. Never commit them, upload them, or send them to external services. `.gitignore` already covers `*.csv`, `*.png`, `*.pdf`, `output/`, `config.env`, `AGENT.local.md`.
3. **Not medical advice:** present results as correlations in the user's own data, never as diagnosis or causation.
4. Use `fetch_garmin_data.py` for data updates. `garmin1.py` is a legacy Colab export kept for reference only.

## Setup (do it with the user)

1. Check Python ≥ 3.10.
2. Create the venv and install deps: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (Windows: `py -m venv .venv`, then `.venv\Scripts\pip install -r requirements.txt`).
3. `cp config.env.example config.env`, then let the user fill in their Garmin e-mail and password.
4. Verify `config.env` is ignored: `git check-ignore config.env` must print the path.

## Commands

| Goal | Command |
|---|---|
| Fetch missing days (first run: last 1365 days, ~0.3 s per day + API time) | `.venv/bin/python fetch_garmin_data.py` |
| Re-fetch last N days | `.venv/bin/python fetch_garmin_data.py --days 30` |
| Slower requests after HTTP 429 | `.venv/bin/python fetch_garmin_data.py --delay 1` |
| Analysis (last 365 days, P10/P90, D-1..D-3) | `.venv/bin/python analyze_deep_sleep.py` |
| Other window / thresholds | `--days 180`, `--percentile 15`, `--lag-days 2`, `--threshold-minutes-low 30`, `--threshold-minutes-high 90` |
| Treat nights with 0 s of Deep Sleep as missing (default: counted as low) | `--ignore-zero-deep` |

## Data

CSV columns: `Date`, `Active Calories`, `Total Steps`, `Distance`, `Min Heart Rate`, `Max Heart Rate`, `Resting Heart Rate`, `Average Stress Level`, `Deep Sleep` (s), `REM Sleep` (s), `Measurable Asleep Duration` (s). Last night's sleep often appears in Garmin only the next day.

## Analysis method (keep it unless the user asks otherwise)

- Extremes are data-driven: low ≤ P10, high ≥ P90 of Deep Sleep in the analysed window. Do not use a fixed 1 h threshold by default; typical values differ a lot between people.
- Precursor window D-1 … D-3 compared with baseline nights (between P10 and P90); Mann-Whitney U, significance p < 0.05; plus a mirror comparison of low vs high.
- Charts in `output/`: `timeline_extremes.png`, `heatmap_low.png`, `heatmap_high.png`, `heatmap_mirror.png`, `boxplot_low.png`, `boxplot_high.png`.

## Reporting to the user

Report the date range and number of days, the low/high thresholds in minutes and the median, counts of low/high/baseline nights, then only significant precursors (metric, day, difference in %), and the mirror patterns. Keep it short and plain.

## Troubleshooting

- `Missing Garmin login`: `config.env` missing or empty.
- `Garmin login failed`: wrong password or two-factor login; the user should sign in on connect.garmin.com and retry. Upgrading the library (`.venv/bin/pip install -U garminconnect`) helps when Garmin changes its login.
- `TooManyRequests`: wait, then rerun with `--delay 1`.

## Personal notes

If `AGENT.local.md` exists, it holds the owner's own state and findings. Read it, but never commit or share it.
