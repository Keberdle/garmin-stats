# AGENT.md — Garmin stats / Deep Sleep analýza

Stav projektu pro pokračování v jiné Cursor session. Skill: `.cursor/skills/garmin-deep-sleep/SKILL.md`.

## Cíl projektu

Analyzovat denní data z Garmin hodinek a hledat **předchůdce** (D-1 až D-3) nocí s extrémně **nízkým** i **vysokým** Deep Sleep (aktivity, kalorie, stres, délka spánku, kroky, …).

## Klíčová rozhodnutí

- Práh **není** pevných 3600 s (1 h) — u VK je medián ~62–64 min, 3600 s je běžné.
- Extrémní noci = **data-driven percentily**: Low = P10, High = P90 (symetricky).
- Okno předchůdců: **D-1, D-2, D-3**.
- Porovnání: low/high vs baseline (normální noci P10–P90) + zrcadlové srovnání low vs high.
- Statistiky: průměr, %, Mann-Whitney U, významnost p < 0.05.

## Soubory

| Soubor | Účel |
|--------|------|
| `garmin_data_extended.csv` | Denní data (Date + metriky). Aktualizovat přes `fetch_garmin_data.py`. |
| `fetch_garmin_data.py` | Stáhne chybějící dny z Garmin Connect a sloučí do CSV. |
| `analyze_deep_sleep.py` | Analýza low/high Deep Sleep + grafy do `output/`. |
| `garmin1.py` | Historický Colab export — **neměnit** jako hlavní workflow. Přihlašovací údaje se zadávají ručně (input/getpass). |
| `requirements.txt` | pandas, matplotlib, scipy, garminconnect |
| `.venv/` | Lokální venv (už vytvořený) |
| `output/` | PNG grafy z analýzy |

## CSV sloupce

`Date`, `Active Calories`, `Total Steps`, `Distance`, `Min Heart Rate`, `Max Heart Rate`, `Resting Heart Rate`, `Average Stress Level`, `Deep Sleep` (s), `REM Sleep` (s), `Measurable Asleep Duration` (s)

## Standardní workflow

```bash
cd <složka projektu>
.venv/bin/python fetch_garmin_data.py
.venv/bin/python analyze_deep_sleep.py
```

Volitelné parametry analýzy:

```bash
.venv/bin/python analyze_deep_sleep.py --percentile 10 --lag-days 3
.venv/bin/python analyze_deep_sleep.py --threshold-minutes-low 30 --threshold-minutes-high 90
```

Fetch přihlášení: env `GARMIN_EMAIL` / `GARMIN_PASSWORD`, jinak lokální `config.env` (vzor `config.env.example`, soubor je v `.gitignore`).

## Aktuální stav dat (poslední běh)

- CSV: ~1996 řádků, rozsah **2020-12-16 .. 2026-06-03**
- Analýza bere **posledních 365 dní** od max data v CSV
- Poslední běh (čerstvá data): Low ≤ ~42 min, High ≥ ~89 min, medián ~64 min
- Spánek za „dnes“ často chybí do dalšího dne (Garmin sync)

## Hlavní zjištění (rok do 2026-06-03)

- Před **LOW**: D-1 delší celkový spánek (+6 %, sig.), D-2 méně kroků (−17 %, sig.), mírně vyšší stres
- Před **HIGH**: mírně nižší kalorie/vzdálenost, D-2 více kroků (+11 %)
- **Zrcadlo**: kroky D-2 opačně (před low méně, před high více); stres D-1 podobně opačně

## Grafy v `output/`

- `timeline_extremes.png` — Deep Sleep timeline, low červeně, high zeleně
- `heatmap_low.png` / `heatmap_high.png` — diff % vs baseline
- `heatmap_mirror.png` — low vs high vedle sebe
- `boxplot_low.png` / `boxplot_high.png` — baseline vs D-1/D-2/D-3

## Co dál (otevřené)

1. Po novém low/high spánku: `fetch` + `analyze` znovu.
2. Hesla přesunout z kódu do env / `.env` (necommitovat).
3. Případně rozšířit metriky (např. body battery, sleep score), pokud Garmin API vrací.
4. `garmin1.py` nepoužívat pro update — jen `fetch_garmin_data.py`.

## Komunikace s VK

- Česky, stručně, bez omáčky
- Komentáře v kódu anglicky
