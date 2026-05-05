import pytest


def valid_row():
    return {
        "Query": "Monteurzimmer (Deutschland)",
        "Nazwa": "Test Hotel",
        "Ocena": "4.3",
        "Opinie": "123",
        "Adres": "Main 1",
        "Telefon": "+49123",
        "WWW": "https://example.com",
        "Cena_AI": 25.0,
        "Waluta": "EUR",
        "Uwagi_AI": "",
        "Udogodnienia_Maps": "WLAN",
        "URL": "https://maps.google.com/x",
        "Lat": "50.0",
        "Lon": "8.0",
    }


def test_final_validate_row_ok(scraper_module):
    assert scraper_module.final_validate_row(valid_row()) is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("URL", ""),
        ("Nazwa", ""),
        ("Lat", "abc"),
        ("Lon", "abc"),
    ],
)
def test_final_validate_row_rejects_required(scraper_module, field, value):
    row = valid_row()
    row[field] = value
    assert scraper_module.final_validate_row(row) is False


def test_final_validate_row_rejects_non_numeric_price(scraper_module):
    row = valid_row()
    row["Cena_AI"] = "32.5"
    assert scraper_module.final_validate_row(row) is False


def test_final_validate_row_allows_empty_price(scraper_module):
    row = valid_row()
    row["Cena_AI"] = ""
    assert scraper_module.final_validate_row(row) is True
