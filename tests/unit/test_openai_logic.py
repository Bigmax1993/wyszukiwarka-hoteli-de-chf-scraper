def test_get_openai_client_always_disabled(scraper_module, logger):
    assert scraper_module.get_openai_client(logger) is None


def test_get_hotel_details_ai_always_returns_default(scraper_module, logger):
    out = scraper_module.get_hotel_details_ai(driver=object(), website_url="https://x", client=None, logger=logger)
    assert out["price"] is None
    assert out["currency"] == ""
    assert out["comment"] == ""
