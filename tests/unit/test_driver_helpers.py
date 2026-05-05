from selenium.webdriver.common.by import By


class Clickable:
    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class ClickDriver:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.el = Clickable()

    def find_element(self, *_args):
        if self.should_fail:
            raise RuntimeError("missing")
        return self.el


def test_click_if_exists_true(scraper_module):
    driver = ClickDriver(should_fail=False)
    assert scraper_module.click_if_exists(driver, By.XPATH, "//x") is True
    assert driver.el.clicked is True


def test_click_if_exists_false(scraper_module):
    driver = ClickDriver(should_fail=True)
    assert scraper_module.click_if_exists(driver, By.XPATH, "//x") is False


def test_is_captcha_page_by_url(scraper_module):
    class D:
        current_url = "https://google.com/sorry/index"
        title = "ok"

        def find_elements(self, *_args):
            return []

    assert scraper_module.is_captcha_page(D()) is True


def test_is_captcha_page_by_title(scraper_module):
    class D:
        current_url = "https://google.com"
        title = "Unusual Traffic detected"

        def find_elements(self, *_args):
            return []

    assert scraper_module.is_captcha_page(D()) is True


def test_is_captcha_page_by_iframe(scraper_module):
    class D:
        current_url = "https://google.com"
        title = "ok"

        def find_elements(self, *_args):
            return [object()]

    assert scraper_module.is_captcha_page(D()) is True


def test_is_captcha_page_false(scraper_module):
    class D:
        current_url = "https://google.com"
        title = "ok"

        def find_elements(self, *_args):
            return []

    assert scraper_module.is_captcha_page(D()) is False
