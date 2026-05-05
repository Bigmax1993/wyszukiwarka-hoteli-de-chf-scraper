class DummyBody:
    def __init__(self, text):
        self.text = text


class DummyDriver:
    def __init__(self, body_text="body text"):
        self.body_text = body_text
        self.loaded_url = None
        self.timeout = None

    def set_page_load_timeout(self, timeout):
        self.timeout = timeout

    def get(self, url):
        self.loaded_url = url

    def find_element(self, *_args, **_kwargs):
        return DummyBody(self.body_text)


class DummyResponses:
    def __init__(self, output_text):
        self._output_text = output_text

    def create(self, **_kwargs):
        return type("Resp", (), {"output_text": self._output_text})()


class DummyClient:
    def __init__(self, output_text):
        self.responses = DummyResponses(output_text)


def test_get_openai_client_without_key(monkeypatch, scraper_module, logger):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert scraper_module.get_openai_client(logger) is None


def test_get_openai_client_with_key(monkeypatch, scraper_module, logger):
    monkeypatch.setenv("OPENAI_API_KEY", "abc")
    client = scraper_module.get_openai_client(logger)
    assert client is not None


def test_get_hotel_details_ai_returns_default_when_missing_client(scraper_module, logger):
    out = scraper_module.get_hotel_details_ai(driver=DummyDriver(), website_url="https://x", client=None, logger=logger)
    assert out["price"] is None


def test_get_hotel_details_ai_parses_valid_json(monkeypatch, scraper_module, logger):
    monkeypatch.setattr(scraper_module.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(scraper_module.time, "sleep", lambda *_: None)
    payload = '{"price": 39.9, "currency": "EUR", "comment": "ok", "has_kitchen": true, "has_parking": false}'
    client = DummyClient(payload)
    out = scraper_module.get_hotel_details_ai(DummyDriver("hello"), "https://site", client, logger)
    assert out["price"] == 39.9
    assert out["currency"] == "EUR"
    assert out["has_kitchen"] is True


def test_get_hotel_details_ai_handles_invalid_json(monkeypatch, scraper_module, logger):
    monkeypatch.setattr(scraper_module.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(scraper_module.time, "sleep", lambda *_: None)
    out = scraper_module.get_hotel_details_ai(DummyDriver("hello"), "https://site", DummyClient("not-json"), logger)
    assert out["price"] is None
    assert "AI error" in out["comment"]


def test_get_hotel_details_ai_no_body_text(monkeypatch, scraper_module, logger):
    monkeypatch.setattr(scraper_module.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(scraper_module.time, "sleep", lambda *_: None)
    out = scraper_module.get_hotel_details_ai(DummyDriver(""), "https://site", DummyClient("{}"), logger)
    assert out["comment"] == "No visible body text"
