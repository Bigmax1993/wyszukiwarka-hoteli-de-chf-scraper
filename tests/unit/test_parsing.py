import pytest


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Pension · Berlin · Open", ("Pension", "Berlin", "Open")),
        ("OnlyCategory", ("OnlyCategory", "", "")),
        ("", ("", "", "")),
    ],
)
def test_parse_card_text(scraper_module, raw, expected):
    assert scraper_module.parse_card_text(raw) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Jetzt geöffnet", "OPEN"),
        ("Still Open now", "OPEN"),
        ("OTWARTE", "OPEN"),
        ("closed", ""),
        ("", ""),
    ],
)
def test_extract_open_status(scraper_module, text, expected):
    assert scraper_module.extract_open_status(text) == expected


def test_detect_amenities_multiple(scraper_module):
    text = "Die Unterkunft bietet Küche, Parkplatz und WLAN."
    assert scraper_module.detect_amenities(text) == "Küche, Parkplatz, WLAN"


def test_detect_amenities_none(scraper_module):
    assert scraper_module.detect_amenities("No useful markers") == ""


def test_search_url_contains_encoded_query_and_country(scraper_module):
    url = scraper_module.search_url("Günstige Pension", "Schweiz", 47.1, 8.5)
    assert "G%C3%BCnstige+Pension+Schweiz" in url
    assert "/@47.1,8.5," in url
