# Wyszukiwarka hoteli pracowniczych (DE, CH)

Pythonowy scraper Google Maps (Selenium), ktory zbiera dane o noclegach pracowniczych
w Niemczech i Szwajcarii (np. `Monteurzimmer`, `Handwerkerunterkunft`) i zapisuje je do CSV.

## Co robi projekt

- przeszukuje Google Maps po zestawie fraz i siatce wspolrzednych,
- pobiera szczegoly obiektow (adres, telefon, www),
- filtruje rekordy (np. odrzuca luksusowe obiekty),
- zapisuje tylko obiekty rozpoznane jako otwarte,
- opcjonalnie uzupelnia dane AI o cene/walute/uwagi na bazie strony WWW obiektu.

## Wymagania

- Python 3.10+
- Google Chrome
- `pip install -r requirements.txt`
- opcjonalnie: `OPENAI_API_KEY` (dla pol AI)

## Szybki start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scraper.py
```

## Zmienne srodowiskowe

- `OPENAI_API_KEY` - opcjonalny klucz OpenAI

PowerShell:

```powershell
$env:OPENAI_API_KEY="twoj_klucz"
```

CMD:

```cmd
set OPENAI_API_KEY=twoj_klucz
```

## Wyniki

Pliki wynikowe trafiaja do `Wyniki/`:

- `germany_switzerland_worker_accommodation.csv`
- `germany_markets_cache.json`
- `germany_worker_accommodation.log`

Folder `Wyniki/` jest ignorowany przez Git.

## Testy

```bash
python -m pytest -q
```

## Pelna dokumentacja

Szczegolowa dokumentacja projektu znajduje sie w pliku:

- `DOKUMENTACJA.md`
