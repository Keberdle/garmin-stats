# garmin-stats

Stáhne denní data z tvých hodinek Garmin (přes Garmin Connect) do tabulky CSV a zjistí, co předchází nocím, kdy máš **nejméně** a **nejvíc hlubokého spánku**: kroky, kalorie, stres, tep a délku spánku v 1–3 dnech předtím.

Data zůstávají jen u tebe v počítači. Do gitu se neukládá ani tabulka, ani grafy, ani přihlašovací údaje.

## Co potřebuješ

- Hodinky Garmin, které měří spánek, a účet Garmin Connect (e-mail a heslo).
- Python 3.10 nebo novější. Ověříš příkazem `python3 --version` (na Windows `py --version`).
- Asi 10 minut na nastavení. První stažení dat trvá podle počtu dní 15–30 minut.

## Návod krok za krokem

### 1. Stáhni projekt

```bash
git clone https://github.com/Keberdle/garmin-stats.git
cd garmin-stats
```

Bez gitu: na GitHubu klikni na **Code → Download ZIP** a rozbal ho.

### 2. Připrav prostředí Pythonu

Linux a macOS:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 3. Zadej přihlášení ke Garmin Connect

Zkopíruj vzor a vyplň svůj e-mail a heslo:

```bash
cp config.env.example config.env
```

```
GARMIN_EMAIL=tvuj@email.cz
GARMIN_PASSWORD=tvoje-heslo
```

Soubor `config.env` je v `.gitignore`, takže se nikdy nenahraje na GitHub. Nikomu ho neposílej. Místo souboru můžeš nastavit proměnné prostředí `GARMIN_EMAIL` a `GARMIN_PASSWORD`.

### 4. Stáhni data

```bash
.venv/bin/python fetch_garmin_data.py
```

(Na Windows `.venv\Scripts\python fetch_garmin_data.py`, stejně i u dalších příkazů.)

- Poprvé stáhne zhruba poslední 3,7 roku (1 365 dní) do `garmin_data_extended.csv`.
- Příště doplní jen chybějící dny.
- `--days 30` stáhne znovu posledních 30 dní, například když se data v Garminu dodatečně změnila.

### 5. Spusť rozbor

```bash
.venv/bin/python analyze_deep_sleep.py
```

Výsledek vypíše do terminálu a grafy uloží do složky `output/`.

## Jak číst výsledek

- **Low a High noci:** 10 % nocí s nejkratším a 10 % s nejdelším hlubokým spánkem za posledních 365 dní. Hranice se počítá z tvých dat, ne z obecné normy.
- **D-1, D-2, D-3:** den, dva a tři dny před takovou nocí.
- **Diff %:** o kolik se ten den lišil od běžných nocí (baseline). **Sig** znamená, že rozdíl je statisticky významný (p < 0,05).
- **Mirror:** porovnání, co dělá opak před krátkými a dlouhými nocemi.
- **Grafy:** `timeline_extremes.png` (časová osa), `heatmap_*.png` (rozdíly v %), `boxplot_*.png` (rozložení hodnot).

Je to hledání souvislostí, ne lékařská diagnóza. Souvislost neznamená, že jedno způsobuje druhé.

### Užitečné volby

```bash
.venv/bin/python analyze_deep_sleep.py --percentile 15        # širší výběr: 15 % nejkratších a nejdelších nocí
.venv/bin/python analyze_deep_sleep.py --days 180 --lag-days 2
.venv/bin/python analyze_deep_sleep.py --threshold-minutes-low 30 --threshold-minutes-high 90
```

## Když něco nejde

| Hláška | Co s tím |
|---|---|
| `Missing Garmin login` | Chybí `config.env` nebo je prázdný. Viz krok 3. |
| `Garmin login failed` | Špatné heslo, nebo máš zapnuté dvoufázové ověření. Zkus se přihlásit na connect.garmin.com a spusť znovu. |
| `TooManyRequests` (429) | Garmin dočasně omezil dotazy. Počkej hodinu, nebo zvyš prodlevu: `--delay 1`. |
| Chybí spánek za poslední noc | Garmin ho zpracuje se zpožděním. Spusť stahování znovu další den. |

Používá neoficiální knihovnu [garminconnect](https://github.com/cyberjunky/python-garminconnect). Když Garmin změní přihlašování, je potřeba ji aktualizovat: `.venv/bin/pip install -U garminconnect`.

## Pro AI agenta

Pokud projekt předáváš agentovi (Claude Code, Cursor, Codex…), ať si nejdřív přečte `AGENTS.md`.
