# Dokumentacja projektu - Wyszukiwarka hoteli (DE, CHF)

## 1. Cel projektu

Projekt sluzy do automatycznego wyszukiwania obiektow noclegowych dla pracownikow
(np. `Monteurzimmer`, `Handwerkerunterkunft`) na obszarze Niemiec i Szwajcarii
na podstawie wynikow Google Maps.

Skrypt:
- przechodzi po siatce wspolrzednych (lat/lon),
- odpytuje Google Maps dla wielu fraz i krajow,
- zbiera dane kontaktowe i adresowe,
- probuje wyciagnac informacje cenowe ze strony WWW obiektu przy pomocy OpenAI,
- zapisuje wyniki do CSV oraz utrzymuje cache JSON.

## 2. Zakres i logika dzialania

Glowne wejscia:
- Frazy wyszukiwania: `SEARCH_QUERIES` w `scraper.py`
- Kraje: `SEARCH_COUNTRIES = ["Deutschland", "Schweiz"]`
- Siatka geograficzna: zakres i krok (`LAT_MIN`, `LAT_MAX`, `LON_MIN`, `LON_MAX`, `LAT_STEP`, `LON_STEP`)

Glowne filtry:
- Odrzucane sa obiekty luksusowe po slowach kluczowych (`LUXURY_KEYWORDS`).
- Przechodza tylko rekordy rozpoznane jako otwarte (`extract_open_status` -> `OPEN`).
- Rekord przechodzi finalna walidacje (`final_validate_row`): URL, nazwa i poprawne wspolrzedne.

Wznowienie pracy:
- Skrypt moze wznowic dzialanie na podstawie istniejacego CSV i cache (`load_existing_csv`, `load_cache`).
- URL-e juz przetworzone nie sa duplikowane.

## 3. Architektura komponentow

Pliki:
- `scraper.py` - glowny skrypt, logika scrapowania, cache, AI i zapis danych
- `tests/` - testy jednostkowe i integracyjne
- `requirements.txt` - zaleznosci
- `Wyniki/` - artefakty uruchomienia (ignorowane przez Git)

Najwazniejsze funkcje:
- `run_scraper()` - petla glowna po siatce i zapytaniach
- `scrape_query_cell()` - przetworzenie jednej komorki geograficznej i jednej frazy
- `extract_details_in_new_tab()` - pobieranie szczegolow obiektu z karty miejsca
- `get_hotel_details_ai()` - analiza strony WWW obiektu przez model OpenAI
- `resolve_region()` - reverse geocoding (Nominatim)
- `clean_row_data()` + `final_validate_row()` - czyszczenie i walidacja danych wyjsciowych

## 4. Wymagania

- Python 3.10+ (zalecane)
- Google Chrome
- Polaczenie internetowe
- Zmienne srodowiskowe:
  - `OPENAI_API_KEY` (opcjonalnie, dla pol `Cena_AI`, `Waluta`, `Uwagi_AI`)

Uwaga:
- Jesli brak `OPENAI_API_KEY`, scraper nadal dziala, ale pola AI beda puste.

## 5. Instalacja

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 6. Uruchomienie

Standardowo:

```bash
python scraper.py
```

W kodzie domyslnie ustawione jest:
- `HEADLESS_DEFAULT = True`

To oznacza uruchomienie przegladarki w trybie bez GUI.

## 7. Wyjscie i pliki wynikowe

Skrypt zapisuje dane do folderu `Wyniki/`:
- `germany_switzerland_worker_accommodation.csv`
- `germany_markets_cache.json`
- `germany_worker_accommodation.log`

Wazne:
- Folder `Wyniki/` jest w `.gitignore`.
- CSV jest zapisywany inkrementalnie (`append_row_to_csv`) oraz finalnie nadpisywany pelna lista (`save_csv`).

## 8. Format CSV

Pola (`CSV_FIELDS`):
- Query
- Region
- Nazwa
- Ocena
- Opinie
- Adres
- Telefon
- WWW
- Cena_AI
- Waluta
- Uwagi_AI
- Udogodnienia_Maps
- URL
- Lat
- Lon

Separator CSV:
- `;` (srednik)

Kodowanie:
- UTF-8 z BOM (`utf-8-sig`)

## 9. Testy

Uruchom wszystkie testy:

```bash
python -m pytest -q
```

Testy obejmuja m.in.:
- parsery i czyszczenie danych,
- logike cache i CSV,
- helpery Selenium,
- scenariusze przeplywu integracyjnego.

## 10. Ograniczenia i ryzyka

- Google Maps moze zwrocic CAPTCHA lub ograniczyc ruch.
- Zmiany w HTML Google Maps moga wymusic aktualizacje selektorow XPath.
- Analiza cen ze stron WWW jest heurystyczna i zalezy od tresci strony.
- Reverse geocoding przez Nominatim moze byc czasowo niedostepny lub wolny.

## 11. Rozwoj projektu (propozycje)

- Dodanie retry/backoff dla newralgicznych krokow sieciowych.
- Dodatkowe metryki jakosc danych (np. confidence score AI).
- Eksport do formatu XLSX i/lub SQLite.
- Wydzielenie konfiguracji do pliku `.env` lub `config.yaml`.
- Rozszerzenie testow integracyjnych o mocki odpowiedzi Nominatim/OpenAI.

## 12. Szybka diagnostyka

Najczestsze problemy:
- Brak wynikow:
  - sprawdz log `Wyniki/germany_worker_accommodation.log`
  - sprawdz, czy Google Maps nie wymusza CAPTCHA
- Brak danych AI:
  - ustaw `OPENAI_API_KEY`
- Bledy Selenium:
  - zaktualizuj Chrome
  - ponownie zainstaluj zaleznosci z `requirements.txt`
