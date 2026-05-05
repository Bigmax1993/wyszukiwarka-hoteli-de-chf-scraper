import pytest


@pytest.mark.parametrize(
    "value,expected",
    [
        ("  hello   world ", "hello world"),
        ("", ""),
        (None, ""),
        ("a\tb\nc", "a b c"),
    ],
)
def test_clean_text(scraper_module, value, expected):
    assert scraper_module.clean_text(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12.345", 12.35),
        ("12,345", 12.35),
        ("foo", ""),
        ("", ""),
        (None, ""),
        (5, 5.0),
    ],
)
def test_clean_price(scraper_module, value, expected):
    assert scraper_module.clean_price(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("+49 (123) 45-67", "+49 123 4567"),
        ("abc", ""),
        (" 0041 79 123 45 67 ", "0041 79 123 45 67"),
    ],
)
def test_clean_phone(scraper_module, value, expected):
    assert scraper_module.clean_phone(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("example.com", "https://example.com"),
        ("https://example.com", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_url(scraper_module, value, expected):
    assert scraper_module.clean_url(value) == expected


def test_clean_row_data_full(scraper_module):
    row = {
        "Query": "  Monteurzimmer (Deutschland) ",
        "Nazwa": "  Hotel \n X ",
        "Ocena": " 4,6 ",
        "Opinie": " (1 234) ",
        "Adres": "  Hauptstrasse 1  ",
        "Telefon": " +49 (123) 45-67 ",
        "WWW": "example.com",
        "Cena_AI": "31,9",
        "Waluta": " eur ",
        "Uwagi_AI": "  tanio ",
        "Udogodnienia_Maps": " Küche, WLAN ",
        "URL": "maps.google.com/place/1",
        "Lat": " 50.1 ",
        "Lon": " 8.6 ",
    }
    cleaned = scraper_module.clean_row_data(row)
    assert cleaned["Opinie"] == "1234"
    assert cleaned["Telefon"] == "+49 123 4567"
    assert cleaned["WWW"] == "https://example.com"
    assert cleaned["Cena_AI"] == 31.9
    assert cleaned["Waluta"] == "EUR"
    assert cleaned["URL"] == "https://maps.google.com/place/1"
