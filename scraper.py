import csv
import queue
import json
import logging
import os
import re
import threading
import time
import asyncio
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from selenium.common.exceptions import NoSuchElementException, TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except Exception:
    class TimeoutException(Exception):
        pass

    class NoSuchElementException(Exception):
        pass

    class By:
        XPATH = "xpath"
        TAG_NAME = "tag_name"

    class EC:
        @staticmethod
        def presence_of_element_located(_locator):
            return True

    class WebDriverWait:
        def __init__(self, *_args, **_kwargs):
            pass

        def until(self, _condition):
            return True

try:
    PROJECT_ROOT = Path(__file__).resolve().parent
except NameError:
    PROJECT_ROOT = Path.cwd()

OUTPUT_DIR = Path(r"C:\Users\kanbu\Documents\Wyszukiwarka hoteli (DE,CHF)\Wyniki")
OUTPUT_FILE = Path(r"C:\Users\kanbu\Documents\Wyszukiwarka hoteli (DE,CHF)\Wyniki\germany_switzerland_worker_accommodation.csv")
CACHE_FILE = Path(r"C:\Users\kanbu\Documents\Wyszukiwarka hoteli (DE,CHF)\Wyniki\germany_markets_cache.json")
LOG_FILE = Path(r"C:\Users\kanbu\Documents\Wyszukiwarka hoteli (DE,CHF)\Wyniki\germany_worker_accommodation.log")

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
PORTAL_SOURCES = [
    "https://www.booking.com",
    "https://www.kleinanzeigen.de",
    "https://www.immobilienscout24.de",
    "https://www.immowelt.de",
    "https://www.wg-gesucht.de",
    "https://www.monteurzimmer.de",
    "https://www.immobilien.de",
    "https://www.immonet.de",
    "https://www.meinestadt.de",
    "https://www.hometogo.de",
    "https://www.holidaycheck.de",
    "https://www.trivago.de",
]

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
REVERSE_GEO_TIMEOUT = 8
PLAYWRIGHT_TIMEOUT_MS = 25000
MAX_RESULTS_PER_PORTAL_QUERY = 30


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
        if hasattr(driver, "find_element"):
            driver.find_element(by, value).click()
        else:
            driver.locator(value).first.click(timeout=2000)
        return True
    except Exception:
        return False


def dismiss_consent(driver):
    selectors = [
        "button:has-text('Accept all')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Ich stimme zu')",
        "button:has-text('I agree')",
        "[id*='consent'] button",
        "[class*='consent'] button",
    ]
    for selector in selectors:
        try:
            locator = driver.locator(selector).first
            if locator.count():
                locator.click(timeout=1500)
                time.sleep(0.5)
                return
        except Exception:
            continue


def search_url(query, country, lat, lon, zoom=10.5):
    combined = f"{query} {country}"
    return f"https://www.google.com/maps/search/{quote_plus(combined)}/@{lat},{lon},{zoom}z"


def build_driver(headless=True):
    # On Windows, Playwright sync API requires a Proactor event loop policy
    # to spawn subprocesses (Node driver). Some Jupyter setups force Selector,
    # which causes NotImplementedError in asyncio subprocess transport.
    if os.name == "nt" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        policy = asyncio.get_event_loop_policy()
        if not isinstance(policy, asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    return {"playwright": playwright, "browser": browser, "context": context, "page": page}


def is_captcha_page(driver):
    try:
        if hasattr(driver, "current_url"):
            url = (driver.current_url or "").lower()
            title = (driver.title or "").lower()
            iframe_count = len(driver.find_elements(None, "//iframe[contains(@src, 'recaptcha')]"))
        else:
            url = (driver.url or "").lower()
            title = (driver.title() or "").lower()
            iframe_count = driver.locator("iframe[src*='recaptcha']").count()
    except Exception:
        return False
    if any(part in url for part in ["/sorry/", "recaptcha"]):
        return True
    if any(part in title for part in ["unusual traffic", "recaptcha", "robot check"]):
        return True
    return iframe_count > 0


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
    logger.info("OpenAI integration disabled. AI fields will stay empty.")
    return None


def get_hotel_details_ai(driver, website_url, client, logger):
    default = {"price": None, "currency": "", "comment": "", "has_kitchen": False, "has_parking": False}
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


def scroll_results_panel(page):
    if hasattr(page, "find_elements"):
        previous_count = 0
        stable_rounds = 0
        for _ in range(MAX_SCROLL_ROUNDS):
            cards = page.find_elements(By.XPATH, "//a[contains(@href, '/maps/place/')]")
            current_count = len(cards)
            stable_rounds = stable_rounds + 1 if current_count <= previous_count else 0
            previous_count = current_count
            if stable_rounds >= 4:
                break
            page.execute_script("window.scrollBy(0, 3000);")
            time.sleep(SCROLL_PAUSE)
        return

    previous_len = 0
    stable_rounds = 0
    for _ in range(MAX_SCROLL_ROUNDS):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(int(SCROLL_PAUSE * 1000))
        html = page.content().lower()
        current_len = html.count("<a ")
        stable_rounds = stable_rounds + 1 if current_len <= previous_len else 0
        previous_len = current_len
        if stable_rounds >= 4:
            break


def _extract_listing_candidates_from_html(html, base_url):
    rows = []
    seen = set()
    link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    text_strip = re.compile(r"<[^>]+>")
    for href, anchor_html in link_pattern.findall(html):
        href = href.strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        visible = clean_text(text_strip.sub(" ", anchor_html))
        if len(visible) < 3:
            continue
        lowered = visible.lower()
        if not any(
            token in lowered
            for token in (
                "zimmer",
                "wohnung",
                "unterkunft",
                "apartment",
                "ferien",
                "room",
                "rent",
                "miete",
                "guest",
                "pension",
            )
        ):
            continue
        if any(token in lowered for token in LUXURY_KEYWORDS):
            continue
        seen.add(full_url)
        rows.append((visible[:120], full_url))
        if len(rows) >= MAX_RESULTS_PER_PORTAL_QUERY:
            break
    return rows


def scrape_portal_query(page, portal_url, query, country, cache, client, logger):
    q = quote_plus(f"{query} {country}")
    target_url = f"{portal_url}/search?query={q}"
    rows = []
    try:
        page.goto(target_url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
    except PlaywrightTimeoutError:
        logger.warning(f"Timeout: {portal_url} | {query} ({country})")
        return rows
    except Exception as exc:
        logger.warning(f"Portal open error ({portal_url}): {exc}")
        return rows

    dismiss_consent(page)
    scroll_results_panel(page)
    html = page.content()
    candidates = _extract_listing_candidates_from_html(html, portal_url)

    for name, place_url in candidates:
        cache_entry = cache.setdefault("places", {}).setdefault(place_url, {})
        ai_details = cache_entry.get("ai_details", {})
        if not ai_details:
            ai_details = get_hotel_details_ai({"page": page}, place_url, client, logger)
            cache_entry["ai_details"] = ai_details

        parsed = urlparse(place_url)
        row = {
            "Query": f"{query} ({country})",
            "Region": "",
            "Nazwa": name,
            "Ocena": "",
            "Opinie": "",
            "Adres": parsed.netloc,
            "Telefon": "",
            "WWW": place_url,
            "Cena_AI": ai_details.get("price", "") if isinstance(ai_details, dict) else "",
            "Waluta": ai_details.get("currency", "") if isinstance(ai_details, dict) else "",
            "Uwagi_AI": ai_details.get("comment", "") if isinstance(ai_details, dict) else "",
            "Udogodnienia_Maps": "",
            "URL": place_url,
            "Lat": "0.0",
            "Lon": "0.0",
        }
        row = clean_row_data(row)
        if final_validate_row(row):
            rows.append(row)
    return rows


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


def _run_scraper_internal(headless_default=HEADLESS_DEFAULT):
    logger = setup_logging()
    logger.info("=== START scraper portalowy (Playwright, bez publicznego API) ===")
    logger.info("OpenAI: OFF (removed)")
    driver = build_driver(headless=headless_default)
    client = get_openai_client(logger)
    all_rows, seen_global = load_existing_csv(OUTPUT_FILE)
    cache = load_cache(logger)
    try:
        if isinstance(driver, dict):
            page = driver["page"]
            total_tasks = len(PORTAL_SOURCES) * len(SEARCH_COUNTRIES) * len(SEARCH_QUERIES)
            task_idx = 0
            for portal_url in PORTAL_SOURCES:
                for country in SEARCH_COUNTRIES:
                    for query in SEARCH_QUERIES:
                        task_idx += 1
                        logger.info(f"Zadanie {task_idx}/{total_tasks} | {portal_url} | {query} ({country})")
                        try:
                            rows = scrape_portal_query(page, portal_url, query, country, cache, client, logger)
                        except CaptchaRequired:
                            logger.warning(f"CAPTCHA: {portal_url} | {query} ({country})")
                            continue
                        except Exception as exc:
                            logger.warning(f"Blad: {portal_url} | {query} ({country}) -> {exc}")
                            continue
                        for row in rows:
                            if row["URL"] in seen_global:
                                continue
                            seen_global.add(row["URL"])
                            all_rows.append(row)
                            append_row_to_csv(OUTPUT_FILE, row)
                            save_cache(cache, logger)
                            logger.info(f"Dodano rekord: {row['Nazwa']} | {row['URL']}")
        else:
            grid_points = [(lat, lon) for lat in frange(LAT_MIN, LAT_MAX, LAT_STEP) for lon in frange(LON_MIN, LON_MAX, LON_STEP)]
            for lat, lon in grid_points:
                for country in SEARCH_COUNTRIES:
                    for query in SEARCH_QUERIES:
                        try:
                            rows = scrape_query_cell(driver, query, country, lat, lon, cache, client, logger)
                        except Exception:
                            continue
                        for row in rows:
                            if row["URL"] in seen_global:
                                continue
                            seen_global.add(row["URL"])
                            all_rows.append(row)
                            append_row_to_csv(OUTPUT_FILE, row)
                            save_cache(cache, logger)
    finally:
        if isinstance(driver, dict):
            driver["context"].close()
            driver["browser"].close()
            driver["playwright"].stop()
        elif hasattr(driver, "quit"):
            driver.quit()
        save_csv(all_rows, OUTPUT_FILE)
        save_cache(cache, logger)
        logger.info(f"Gotowe. Rekordow: {len(all_rows)}")


def run_scraper(headless_default=HEADLESS_DEFAULT):
    try:
        asyncio.get_running_loop()
        in_running_loop = True
    except RuntimeError:
        in_running_loop = False

    if not in_running_loop:
        return _run_scraper_internal(headless_default=headless_default)

    # Jupyter zwykle ma aktywna petle event loop, a Playwright Sync API tego nie wspiera.
    # Uruchamiamy scraper w osobnym watku, gdzie nie ma aktywnej petli.
    result_queue = queue.Queue()

    def _worker():
        try:
            _run_scraper_internal(headless_default=headless_default)
            result_queue.put((True, None))
        except Exception as exc:
            result_queue.put((False, exc))

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()
    worker.join()
    success, payload = result_queue.get()
    if not success:
        raise payload


if __name__ == "__main__":
    run_scraper(headless_default=HEADLESS_DEFAULT)
