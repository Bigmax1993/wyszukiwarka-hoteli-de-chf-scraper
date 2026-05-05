import json


def test_load_cache_missing_file(scraper_module, isolated_paths, logger):
    cache = scraper_module.load_cache(logger)
    assert cache == {"places": {}}


def test_save_then_load_cache(scraper_module, isolated_paths, logger):
    data = {"places": {"u1": {"phone": "1"}}}
    scraper_module.save_cache(data, logger)
    loaded = scraper_module.load_cache(logger)
    assert loaded["places"]["u1"]["phone"] == "1"


def test_load_cache_invalid_json(scraper_module, isolated_paths, logger):
    scraper_module.CACHE_FILE.write_text("{invalid", encoding="utf-8")
    loaded = scraper_module.load_cache(logger)
    assert loaded == {"places": {}}


def test_append_and_load_existing_csv(scraper_module, isolated_paths):
    row = {
        "Query": "q",
        "Nazwa": "n",
        "Ocena": "",
        "Opinie": "",
        "Adres": "",
        "Telefon": "",
        "WWW": "",
        "Cena_AI": "",
        "Waluta": "",
        "Uwagi_AI": "",
        "Udogodnienia_Maps": "",
        "URL": "https://maps.google.com/a",
        "Lat": "1",
        "Lon": "2",
    }
    scraper_module.append_row_to_csv(scraper_module.OUTPUT_FILE, row)
    rows, seen = scraper_module.load_existing_csv(scraper_module.OUTPUT_FILE)
    assert len(rows) == 1
    assert "https://maps.google.com/a" in seen


def test_save_csv_writes_header(scraper_module, isolated_paths):
    scraper_module.save_csv([], scraper_module.OUTPUT_FILE)
    content = scraper_module.OUTPUT_FILE.read_text(encoding="utf-8-sig")
    assert "Query;Nazwa;Ocena" in content


def test_get_place_details_with_cache_hit(scraper_module, logger):
    cache = {
        "places": {
            "u": {
                "phone": "1",
                "website": "w",
                "status": "OPEN",
                "full_address": "a",
                "amenities_maps": "WLAN",
                "ai_details": {"price": 20},
            }
        }
    }
    out = scraper_module.get_place_details_with_cache(driver=None, place_url="u", cache=cache, logger=logger)
    assert out[0] == "1"
    assert out[6] is True


def test_get_place_details_with_cache_miss(monkeypatch, scraper_module, logger):
    cache = {"places": {}}

    def fake_extract(_driver, _url):
        return ("1", "w", "OPEN", "addr", "WLAN")

    monkeypatch.setattr(scraper_module, "extract_details_in_new_tab", fake_extract)
    out = scraper_module.get_place_details_with_cache(driver=object(), place_url="u2", cache=cache, logger=logger)
    assert out[:5] == ("1", "w", "OPEN", "addr", "WLAN")
    assert out[6] is False
    assert cache["places"]["u2"]["website"] == "w"
