def test_run_scraper_deduplicates_and_persists(monkeypatch, scraper_module, isolated_paths, logger):
    class FakeDriver:
        def quit(self):
            return None

    monkeypatch.setattr(scraper_module, "setup_logging", lambda: logger)
    monkeypatch.setattr(scraper_module, "build_driver", lambda **_kwargs: FakeDriver())
    monkeypatch.setattr(scraper_module, "get_openai_client", lambda _logger: object())
    monkeypatch.setattr(scraper_module, "load_cache", lambda _logger: {"places": {}})
    monkeypatch.setattr(scraper_module, "save_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scraper_module, "SEARCH_COUNTRIES", ["Deutschland"])
    monkeypatch.setattr(scraper_module, "SEARCH_QUERIES", ["Monteurzimmer"])
    monkeypatch.setattr(scraper_module, "frange", lambda start, stop, step: [50.0])
    monkeypatch.setattr(scraper_module, "load_existing_csv", lambda _path: ([], set()))

    row = {
        "Query": "Monteurzimmer (Deutschland)",
        "Nazwa": "A",
        "Ocena": "",
        "Opinie": "",
        "Adres": "",
        "Telefon": "",
        "WWW": "",
        "Cena_AI": "",
        "Waluta": "",
        "Uwagi_AI": "",
        "Udogodnienia_Maps": "",
        "URL": "https://maps.google.com/x",
        "Lat": "50.0",
        "Lon": "8.0",
    }
    monkeypatch.setattr(scraper_module, "scrape_query_cell", lambda *_args, **_kwargs: [row, row])

    appended = []
    monkeypatch.setattr(scraper_module, "append_row_to_csv", lambda _path, r: appended.append(r["URL"]))
    monkeypatch.setattr(scraper_module, "save_csv", lambda rows, _path: rows)

    scraper_module.run_scraper(headless_default=True)
    assert appended == ["https://maps.google.com/x"]


def test_run_scraper_handles_query_exception(monkeypatch, scraper_module, isolated_paths, logger):
    class FakeDriver:
        def quit(self):
            return None

    monkeypatch.setattr(scraper_module, "setup_logging", lambda: logger)
    monkeypatch.setattr(scraper_module, "build_driver", lambda **_kwargs: FakeDriver())
    monkeypatch.setattr(scraper_module, "get_openai_client", lambda _logger: object())
    monkeypatch.setattr(scraper_module, "load_cache", lambda _logger: {"places": {}})
    monkeypatch.setattr(scraper_module, "save_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scraper_module, "SEARCH_COUNTRIES", ["Deutschland"])
    monkeypatch.setattr(scraper_module, "SEARCH_QUERIES", ["Monteurzimmer"])
    monkeypatch.setattr(scraper_module, "frange", lambda start, stop, step: [50.0])
    monkeypatch.setattr(scraper_module, "load_existing_csv", lambda _path: ([], set()))

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(scraper_module, "scrape_query_cell", boom)
    monkeypatch.setattr(scraper_module, "append_row_to_csv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scraper_module, "save_csv", lambda *_args, **_kwargs: None)

    scraper_module.run_scraper(headless_default=True)
