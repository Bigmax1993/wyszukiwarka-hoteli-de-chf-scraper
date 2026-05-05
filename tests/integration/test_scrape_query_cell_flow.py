from selenium.webdriver.common.by import By


class FakeCard:
    def __init__(self, href, text, name):
        self._href = href
        self.text = text
        self._name = name

    def get_attribute(self, key):
        return self._href if key == "href" else ""

    def find_element(self, *_args):
        return type("H3", (), {"text": self._name})()


class FakeDriver:
    def __init__(self, cards):
        self.cards = cards
        self.current_url = "https://google.com/maps"
        self.title = "maps"

    def get(self, _url):
        return None

    def find_element(self, by, _value):
        if by == By.XPATH:
            return object()
        raise RuntimeError("not used")

    def find_elements(self, _by, value):
        if "/maps/place/" in value:
            return self.cards
        if "iframe[contains(@src, 'recaptcha')]" in value:
            return []
        return []

    def execute_script(self, *_args):
        return None


def test_scrape_query_cell_happy_path(monkeypatch, scraper_module, logger):
    cards = [
        FakeCard(
            href="https://google.com/maps/place/abc",
            text="Pension · Berlin · Open · 4,5 (123)",
            name="Test Pension",
        )
    ]
    driver = FakeDriver(cards)
    cache = {"places": {}}

    monkeypatch.setattr(scraper_module.time, "sleep", lambda *_: None)

    class WaitOK:
        def __init__(self, *_args, **_kwargs):
            pass

        def until(self, _cond):
            return True

    monkeypatch.setattr(scraper_module, "WebDriverWait", WaitOK)
    monkeypatch.setattr(scraper_module, "dismiss_consent", lambda *_: None)
    monkeypatch.setattr(scraper_module, "scroll_results_panel", lambda *_: None)
    monkeypatch.setattr(scraper_module, "click_if_exists", lambda *_: False)
    monkeypatch.setattr(
        scraper_module,
        "get_place_details_with_cache",
        lambda *_: ("+491", "https://site", "OPEN", "Street 1", "WLAN", {}, True),
    )
    monkeypatch.setattr(
        scraper_module,
        "get_hotel_details_ai",
        lambda *_: {"price": 30.0, "currency": "EUR", "comment": "ok", "has_kitchen": True, "has_parking": False},
    )

    rows = scraper_module.scrape_query_cell(driver, "Monteurzimmer", "Deutschland", 50.0, 8.0, cache, client=object(), logger=logger)
    assert len(rows) == 1
    assert rows[0]["Nazwa"] == "Test Pension"
    assert rows[0]["Cena_AI"] == 30.0


def test_scrape_query_cell_skips_luxury(monkeypatch, scraper_module, logger):
    cards = [
        FakeCard(
            href="https://google.com/maps/place/lux",
            text="Luxushotel · Berlin · Open · 4,9 (10)",
            name="Luxury",
        )
    ]
    driver = FakeDriver(cards)
    cache = {"places": {}}
    monkeypatch.setattr(scraper_module.time, "sleep", lambda *_: None)

    class WaitOK:
        def __init__(self, *_args, **_kwargs):
            pass

        def until(self, _cond):
            return True

    monkeypatch.setattr(scraper_module, "WebDriverWait", WaitOK)
    monkeypatch.setattr(scraper_module, "dismiss_consent", lambda *_: None)
    monkeypatch.setattr(scraper_module, "scroll_results_panel", lambda *_: None)
    monkeypatch.setattr(scraper_module, "click_if_exists", lambda *_: False)
    rows = scraper_module.scrape_query_cell(driver, "Monteurzimmer", "Deutschland", 50.0, 8.0, cache, client=object(), logger=logger)
    assert rows == []
