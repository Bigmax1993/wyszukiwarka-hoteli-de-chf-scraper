# Wyszukiwarka noclegow pracowniczych (DE, CH)

Pythonowy scraper oparty o Playwright, ktory zbiera oferty noclegow/pokoi/mieszkan
z wielu portali niemieckich i zapisuje je do CSV.

## Co robi projekt

- przeszukuje wiele portali po zestawie fraz i krajow,
- pobiera oferty bez publicznego API (automatyzacja przegladarki),
- filtruje rekordy (np. odrzuca luksusowe obiekty),
- zapisuje wyniki do CSV i cache JSON.

## Wymagania

- Python 3.10+
- Chromium (instalowany przez Playwright)
- `pip install -r requirements.txt`
- `playwright install chromium`

## Szybki start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python scraper.py
```

## Zrodla (portale)

Skrypt domyslnie przeszukuje m.in.:

- `booking.com`
- `kleinanzeigen.de`
- `immobilienscout24.de`
- `immowelt.de`
- `wg-gesucht.de`
- `monteurzimmer.de`
- `immobilien.de`
- `immonet.de`
- `meinestadt.de`
- `hometogo.de`
- `holidaycheck.de`
- `trivago.de`

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
