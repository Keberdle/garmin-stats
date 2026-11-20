# garmin-stats

Stáhne denní souhrny z Garmin Connect (kroky, kalorie, tep, stres, spánek) do CSV a hledá, co předchází nocím s nejkratším a nejdelším hlubokým spánkem.

## Instalace

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.env.example config.env   # vyplň e-mail a heslo ke Garmin Connect
```

`config.env` je v `.gitignore` a do gitu se nedostane. Místo něj jdou použít proměnné prostředí `GARMIN_EMAIL` a `GARMIN_PASSWORD`.

## Použití

```bash
.venv/bin/python fetch_garmin_data.py     # stáhne nové dny do garmin_data_extended.csv
.venv/bin/python analyze_deep_sleep.py    # rozbor hlubokého spánku, grafy do output/
.venv/bin/python analyze_deep_sleep.py --percentile 10 --lag-days 3
```

Podrobnosti pro agenta (Cursor, Claude Code) jsou v `AGENT.md`. `garmin1.py` je starý export z Google Colabu, jen pro inspiraci.

Používá neoficiální knihovnu [garminconnect](https://github.com/cyberjunky/python-garminconnect); Garmin může přihlášení kdykoli změnit.
