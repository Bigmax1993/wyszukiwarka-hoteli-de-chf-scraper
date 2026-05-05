import csv
import json
import logging
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

from openai import OpenAI
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

try:
    PROJECT_ROOT = Path(__file__).resolve().parent
except NameError:
    PROJECT_ROOT = Path.cwd()

OUTPUT_DIR = PROJECT_ROOT / "Wyniki"
OUTPUT_FILE = OUTPUT_DIR / "germany_switzerland_worker_accommodation.csv"
CACHE_FILE = OUTPUT_DIR / "germany_markets_cache.json"
LOG_FILE = OUTPUT_DIR / "germany_worker_accommodation.log"

SEARCH_QUERIES = [
    "Monteurzimmer",
    "Baumonteurzimmer",
    "Handwerkerunterkunft",
    "Baustellenunterkunft",
    "Günstige Pension",
    "Arbeiterunterkunft",
    "Gästehaus",
]
SEARCH_COUNTRIES = ["Deutschland", "Schweiz"]
LUXURY_KEYWORDS = ("luxushotel", "wellnesshotel", "resort")
AMENITY_KEYWORDS = ["Küche", "Parkplatz", "WLAN", "Waschmaschine", "Einzelbetten"]

CSV_FIELDS = [
    "Query",
    "Region",
    "Nazwa",
    "Ocena",
    "Opinie",
    "Adres",
    "Telefon",
    "WWW",
    "Cena_AI",
    "Waluta",
    "Uwagi_AI",
    "Udogodnienia_Maps",
    "URL",
    "Lat",
    "Lon",
]

LAT_MIN, LAT_MAX = 45.8, 54.9
LON_MIN, LON_MAX = 5.9, 14.9
LAT_STEP = 0.9
LON_STEP = 1.1

MAX_SCROLL_ROUNDS = 25
SCROLL_PAUSE = 1.0
HEADLESS_DEFAULT = True
EXTERNAL_SITE_TIMEOUT = 10
MAPS_RESULTS_TIMEOUT = 120
OPENAI_MODEL = "gpt-4o-mini"
REVERSE_GEO_TIMEOUT = 8


class CaptchaRequired(Exception):
    pass


def setup_logging():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("worker_accommodation_scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


def frange(start, stop, step):
    value = start
    while value <= stop:
        yield round(value, 4)
        value += step


def load_cache(logger):
    if not CACHE_FILE.exists():
        logger.info("Cache JSON nie istnieje, tworzę nowy.")
        return {"places": {}}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            cache = json.load(file)
        cache.setdefault("places", {})
        return cache
    except Exception as exc:
        logger.warning(f"Błąd odczytu cache ({exc}), tworzę nowy.")
        return {"places": {}}


def save_cache(cache, logger):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as file:
            json.dump(cache, file, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error(f"Błąd zapisu cache: {exc}")


def load_existing_csv(path):
    rows, seen_urls = [], set()
    if not path.exists():
        return rows, seen_urls
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file, delimiter=";"):
            rows.append(row)
            if row.get("URL"):
                seen_urls.add(row["URL"])
    return rows, seen_urls


def save_csv(rows, path):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def append_row_to_csv(path, row):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, delimiter=";")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def click_if_exists(driver, by, value):
    try:
        driver.find_element(by, value).click()
        return True
    except Exception:
        return False


def dismiss_consent(driver):
    selectors = [
        (By.XPATH, "//button[contains(., 'Accept all')]"),
        (By.XPATH, "//button[contains(., 'Alle akzeptieren')]"),
        (By.XPATH, "//button[contains(., 'Ich stimme zu')]"),
        (By.XPATH, "//button[contains(., 'I agree')]"),
    ]
    for by, value in selectors:
        if click_if_exists(driver, by, value):
            time.sleep(1)
            break


def search_url(query, country, lat, lon, zoom=10.5):
    combined = f"{query} {country}"
    return f"https://www.google.com/maps/search/{quote_plus(combined)}/@{lat},{lon},{zoom}z"


def build_driver(headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    else:
        options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def is_captcha_page(driver):
    try:
        url = (driver.current_url or "").lower()
        title = (driver.title or "").lower()
    except Exception:
        return False
    if any(part in url for part in ["/sorry/", "recaptcha"]):
        return True
    if any(part in title for part in ["unusual traffic", "recaptcha", "robot check"]):
        return True
    return bool(driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha')]"))


def parse_card_text(raw_text):
    parts = [item.strip() for item in (raw_text or "").split("·") if item.strip()]
    category = parts[0] if len(parts) > 0 else ""
    address = parts[1] if len(parts) > 1 else ""
    status = parts[2] if len(parts) > 2 else ""
    return category, address, status


def extract_open_status(text):
    normalized = " ".join((text or "").split()).lower()
    if any(token in normalized for token in ["otwarte", "geöffnet", "geoeffnet", "open"]):
        return "OPEN"
    return ""


def detect_amenities(maps_text):
    content = (maps_text or "").lower()
    found = [keyword for keyword in AMENITY_KEYWORDS if keyword.lower() in content]
    return ", ".join(found)


def extract_details_in_new_tab(driver, place_url):
    phone, website, status, full_address, amenities_maps = "", "", "", "", ""
    base_tab = driver.current_window_handle
    driver.execute_script("window.open(arguments[0], '_blank');", place_url)
    driver.switch_to.window(driver.window_handles[-1])
    try:
        time.sleep(1.5)
        if is_captcha_page(driver):
            raise CaptchaRequired("CAPTCHA in details view.")
        tel_links = driver.find_elements(By.XPATH, "//a[starts-with(@href,'tel:')]")
        if tel_links:
            phone = (tel_links[0].get_attribute("href") or "").replace("tel:", "").strip()
        for xpath in ["//a[contains(., 'Website')]", "//a[contains(., 'Webseite')]"]:
            links = driver.find_elements(By.XPATH, xpath)
            if links:
                href = links[0].get_attribute("href")
                if href:
                    website = href
                    break
        for element in driver.find_elements(By.XPATH, "//*[@data-item-id='address']"):
            text = (element.text or "").strip()
            if len(text) > 6:
                full_address = " ".join(text.split())
                break
        chunks = driver.find_elements(By.XPATH, "//div[@role='main'] | //body")
        maps_text = " ".join((item.text or "") for item in chunks[:2])
        amenities_maps = detect_amenities(maps_text)
        status = extract_open_status(maps_text)
    except Exception:
        pass
    finally:
        driver.close()
        driver.switch_to.window(base_tab)
    return phone, website, status, full_address, amenities_maps


def get_openai_client(logger):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("Brak OPENAI_API_KEY. Pola AI pozostaną puste.")
        return None
    return OpenAI(api_key=api_key)


def get_hotel_details_ai(driver, website_url, client, logger):
    default = {"price": None, "currency": "", "comment": "", "has_kitchen": False, "has_parking": False}
    if not website_url or not client:
        return default
    try:
        time.sleep(random.uniform(2, 5))
        driver.set_page_load_timeout(EXTERNAL_SITE_TIMEOUT)
        driver.get(website_url)
        body_text = (driver.find_element(By.TAG_NAME, "body").text or "").strip()[:4000]
        if not body_text:
            default["comment"] = "No visible body text"
            return default
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a German accommodation expert. Extract the price per person per night "
                        "(pro Person / pro Nacht) for workers. Return ONLY a JSON object: "
                        "{'price': float, 'currency': string, 'comment': string, 'has_kitchen': boolean, 'has_parking': boolean}. "
                        "If no price is found, price should be null."
                    ),
                },
                {"role": "user", "content": body_text},
            ],
            timeout=EXTERNAL_SITE_TIMEOUT,
        )
        output_text = (response.output_text or "").strip()
        output_text = re.sub(r"^```json|```$", "", output_text).strip()
        parsed = json.loads(output_text)
        return {
            "price": parsed.get("price"),
            "currency": parsed.get("currency", ""),
            "comment": parsed.get("comment", ""),
            "has_kitchen": bool(parsed.get("has_kitchen", False)),
            "has_parking": bool(parsed.get("has_parking", False)),
        }
    except Exception as exc:
        logger.warning(f"AI error for {website_url}: {exc}")
        default["comment"] = f"AI error: {exc}"
        return default


def get_place_details_with_cache(driver, place_url, cache, logger):
    places = cache.setdefault("places", {})
    if place_url in places:
        cached = places[place_url]
        return (
            cached.get("phone", ""),
            cached.get("website", ""),
            cached.get("status", ""),
            cached.get("full_address", ""),
            cached.get("amenities_maps", ""),
            cached.get("ai_details", {}),
            True,
        )
    phone, website, status, full_address, amenities_maps = extract_details_in_new_tab(driver, place_url)
    places[place_url] = {
        "phone": phone,
        "website": website,
        "status": status,
        "full_address": full_address,
        "amenities_maps": amenities_maps,
        "ai_details": {},
    }
    logger.info(f"Dodano do cache: {place_url}")
    return phone, website, status, full_address, amenities_maps, {}, False


def scroll_results_panel(driver):
    try:
        panel = driver.find_element(By.XPATH, "//div[@role='feed']")
    except NoSuchElementException:
        panel = None
    previous_count = 0
    stable_rounds = 0
    for _ in range(MAX_SCROLL_ROUNDS):
        cards = driver.find_elements(By.XPATH, "//a[contains(@href, '/maps/place/')]")
        current_count = len(cards)
        stable_rounds = stable_rounds + 1 if current_count <= previous_count else 0
        previous_count = current_count
        if stable_rounds >= 4:
            break
        if panel is not None:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", panel)
        else:
            driver.execute_script("window.scrollBy(0, 3000);")
        time.sleep(SCROLL_PAUSE)


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_price(value):
    if value is None or value == "":
        return ""
    try:
        return round(float(str(value).replace(",", ".")), 2)
    except Exception:
        return ""


def clean_phone(value):
    value = clean_text(value)
    return re.sub(r"[^\d+ ]", "", value)


def clean_url(value):
    value = clean_text(value)
    if value and not value.lower().startswith(("http://", "https://")):
        return f"https://{value}"
    return value


def clean_row_data(row):
    cleaned = dict(row)
    cleaned["Query"] = clean_text(cleaned.get("Query"))
    cleaned["Region"] = clean_text(cleaned.get("Region"))
    cleaned["Nazwa"] = clean_text(cleaned.get("Nazwa"))
    cleaned["Ocena"] = clean_text(cleaned.get("Ocena"))
    cleaned["Opinie"] = re.sub(r"[^\d]", "", clean_text(cleaned.get("Opinie")))
    cleaned["Adres"] = clean_text(cleaned.get("Adres"))
    cleaned["Telefon"] = clean_phone(cleaned.get("Telefon"))
    cleaned["WWW"] = clean_url(cleaned.get("WWW"))
    cleaned["Cena_AI"] = clean_price(cleaned.get("Cena_AI"))
    cleaned["Waluta"] = clean_text(cleaned.get("Waluta")).upper()
    cleaned["Uwagi_AI"] = clean_text(cleaned.get("Uwagi_AI"))
    cleaned["Udogodnienia_Maps"] = clean_text(cleaned.get("Udogodnienia_Maps"))
    cleaned["URL"] = clean_url(cleaned.get("URL"))
    cleaned["Lat"] = clean_text(cleaned.get("Lat"))
    cleaned["Lon"] = clean_text(cleaned.get("Lon"))
    return cleaned


def final_validate_row(row):
    if not row.get("URL"):
        return False
    if not row.get("Nazwa"):
        return False
    if row.get("Cena_AI") != "" and not isinstance(row["Cena_AI"], (float, int)):
        return False
    try:
        float(row.get("Lat", ""))
        float(row.get("Lon", ""))
    except Exception:
        return False
    return True


def resolve_region(country, lat, lon, cache, logger):
    region_cache = cache.setdefault("regions", {})
    cache_key = f"{country}:{lat}:{lon}"
    if cache_key in region_cache:
        return region_cache[cache_key]

    # Nominatim reverse geocoding: DE -> Bundesland, CH -> Kanton.
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&zoom=8&addressdetails=1"
    try:
        req = Request(url, headers={"User-Agent": "worker-accommodation-scraper/1.0"})
        with urlopen(req, timeout=REVERSE_GEO_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        address = payload.get("address", {})
        region = address.get("state") or address.get("region") or address.get("county") or ""
    except Exception as exc:
        logger.warning(f"Region resolve error ({country}, {lat}, {lon}): {exc}")
        region = ""

    region_cache[cache_key] = region
    return region


def scrape_query_cell(driver, query, country, lat, lon, cache, client, logger):
    driver.get(search_url(query, country, lat, lon))
    time.sleep(3)
    if is_captcha_page(driver):
        raise CaptchaRequired("CAPTCHA after opening search.")
    dismiss_consent(driver)
    try:
        WebDriverWait(driver, MAPS_RESULTS_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/maps/place/')]"))
        )
    except TimeoutException:
        logger.warning(f"Timeout: {query}, {country}, lat={lat}, lon={lon}")
        return []
    for xpath in ["//button[contains(., 'Search this area')]", "//button[contains(., 'In diesem Bereich suchen')]"]:
        if click_if_exists(driver, By.XPATH, xpath):
            time.sleep(2)
            break
    scroll_results_panel(driver)
    cards = driver.find_elements(By.XPATH, "//a[contains(@href, '/maps/place/')]")
    seen_local = set()
    rows = []
    for card in cards:
        href = card.get_attribute("href") or ""
        if not href:
            continue
        place_url = urljoin("https://www.google.com", href)
        if place_url in seen_local:
            continue
        seen_local.add(place_url)
        raw = clean_text(card.text)
        try:
            name = clean_text(card.find_element(By.XPATH, ".//h3").text)
        except Exception:
            name = ""
        category, address, status_list = parse_card_text(raw)
        if any(keyword in category.lower() for keyword in LUXURY_KEYWORDS):
            continue
        rating_match = re.search(r"(\d[.,]\d)", raw)
        reviews_match = re.search(r"\(([\d\s.,]+)\)", raw)
        rating = rating_match.group(1).replace(",", ".") if rating_match else ""
        reviews = reviews_match.group(1).replace(" ", "") if reviews_match else ""
        phone, website, status_detail, full_address, amenities_maps, ai_cached, from_cache = get_place_details_with_cache(
            driver, place_url, cache, logger
        )
        status = status_detail or status_list
        if extract_open_status(status) != "OPEN":
            continue
        cache_entry = cache["places"].setdefault(place_url, {})
        if website and not cache_entry.get("ai_details", {}).get("price"):
            ai_details = get_hotel_details_ai(driver, website, client, logger)
            cache_entry["ai_details"] = ai_details
        else:
            ai_details = ai_cached if from_cache else cache_entry.get("ai_details", {})
        row = {
            "Query": f"{query} ({country})",
            "Region": resolve_region(country, lat, lon, cache, logger),
            "Nazwa": name,
            "Ocena": rating,
            "Opinie": reviews,
            "Adres": full_address or address,
            "Telefon": phone,
            "WWW": website,
            "Cena_AI": ai_details.get("price", "") if isinstance(ai_details, dict) else "",
            "Waluta": ai_details.get("currency", "") if isinstance(ai_details, dict) else "",
            "Uwagi_AI": ai_details.get("comment", "") if isinstance(ai_details, dict) else "",
            "Udogodnienia_Maps": amenities_maps,
            "URL": place_url,
            "Lat": lat,
            "Lon": lon,
        }
        row = clean_row_data(row)
        if final_validate_row(row):
            rows.append(row)
        else:
            logger.info(f"Pominieto rekord po walidacji: {place_url}")
    return rows


def run_scraper(headless_default=HEADLESS_DEFAULT):
    logger = setup_logging()
    logger.info("=== START scraper Monteurzimmer (DE + CH) ===")
    logger.info("OpenAI: %s", "ON" if os.getenv("OPENAI_API_KEY", "").strip() else "OFF")
    driver = build_driver(headless=headless_default)
    client = get_openai_client(logger)
    all_rows, seen_global = load_existing_csv(OUTPUT_FILE)
    cache = load_cache(logger)
    try:
        grid_points = [
            (lat, lon)
            for lat in frange(LAT_MIN, LAT_MAX, LAT_STEP)
            for lon in frange(LON_MIN, LON_MAX, LON_STEP)
        ]
        for idx, (lat, lon) in enumerate(grid_points, start=1):
            logger.info(f"Komorka {idx}/{len(grid_points)} | lat={lat}, lon={lon}")
            for country in SEARCH_COUNTRIES:
                for query in SEARCH_QUERIES:
                    try:
                        rows = scrape_query_cell(driver, query, country, lat, lon, cache, client, logger)
                    except CaptchaRequired:
                        logger.warning(f"CAPTCHA: {query} ({country})")
                        continue
                    except Exception as exc:
                        logger.warning(f"Blad: {query} ({country}) -> {exc}")
                        continue
                    for row in rows:
                        if row["URL"] in seen_global:
                            continue
                        seen_global.add(row["URL"])
                        all_rows.append(row)
                        append_row_to_csv(OUTPUT_FILE, row)
                        save_cache(cache, logger)
                        logger.info(f"Dodano rekord: {row['Nazwa']} | {row['URL']}")
    finally:
        driver.quit()
        save_csv(all_rows, OUTPUT_FILE)
        save_cache(cache, logger)
        logger.info(f"Gotowe. Rekordow: {len(all_rows)}")


if __name__ == "__main__":
    run_scraper(headless_default=HEADLESS_DEFAULT)
