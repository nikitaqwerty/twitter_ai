import time
import random
from typing import Optional
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from faker import Faker
import requests
from requests_oauthlib import OAuth1
from utils.config import Config
import logging
from utils.captcha_solver import CaptchaSolver
from utils.proxy_utils import (
    get_working_proxy,
    apply_proxy_to_chrome_options,
    build_requests_proxies,
)

logging.basicConfig(level=logging.INFO)


class TwitterAccountCreator:
    TWITTER_AUTH_URL = "https://api.twitter.com/oauth/access_token"
    OAUTH = OAuth1(
        "3nVuSoBZnx6U4vzUxf5w", "Bcs59EFbbsdF6Sl9Ng71smgStWEGwXXKSjYvPVt7qys"
    )
    DEFAULT_PASSWORD = "BOTwownow24368"

    def __init__(self, config: dict):
        self.config = config
        self.fake = Faker()
        self.account_details = {}
        self.current_proxy = None
        if config.get("use_proxy"):
            self.current_proxy = get_working_proxy("smartproxy-residential-rotating")
            logging.info(f"Using proxy: {self.current_proxy}")
        self.driver = self._init_driver()

    def _init_driver(self) -> uc.Chrome:
        try:
            options = ChromeOptions()
            if self.config.get("use_proxy") and self.current_proxy:
                apply_proxy_to_chrome_options(
                    options, self.current_proxy, scheme="http"
                )
            options.add_argument("--disable-dev-shm-usage")
            if not (
                self.config.get("use_proxy")
                and self.current_proxy
                and "@" in self.current_proxy
            ):
                options.add_argument("--incognito")
            options.add_argument("--disable-blink-features=AutomationControlled")
            return uc.Chrome(
                options=options,
                headless=self.config.get("headless", False),
                version_main=132,
            )
        except Exception as e:
            logging.error(f"Failed to initialize ChromeDriver: {str(e)}")
            raise

    def _fill_birthdate(self):
        Select(self.driver.find_element(By.ID, "SELECTOR_1")).select_by_value(
            str(random.randint(1, 12))
        )
        Select(self.driver.find_element(By.ID, "SELECTOR_2")).select_by_value(
            str(random.randint(1, 28))
        )
        Select(self.driver.find_element(By.ID, "SELECTOR_3")).select_by_visible_text(
            "1999"
        )

    def _get_verification_code(self) -> Optional[str]:
        email_client = EmailClient(
            service=self.config["email_service"],
            email=self.config["email"],
            credential=self.config["email_credential"],
        )
        return email_client.get_verification_code()

    def _register_account(self) -> bool:
        try:
            self.driver.get("https://x.com/i/flow/signup?mx=2")
            WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[text()='Create account']")
                )
            ).click()
            self._fill_form()
            time.sleep(5)
            # First Next click
            WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
            ).click()
            time.sleep(5)
            # Second Next click (if available)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
                ).click()
                time.sleep(5)
            except Exception:
                logging.info("Second Next button not found, proceeding...")

            # Handle Arkose iframe authentication
            try:
                time.sleep(3)
                # Wait for iframe and switch using CSS selector
                WebDriverWait(self.driver, 30).until(
                    EC.frame_to_be_available_and_switch_to_it(
                        (By.CSS_SELECTOR, "iframe[src*='arkoselabs.com']")
                    )
                )
                WebDriverWait(self.driver, 30).until(
                    EC.frame_to_be_available_and_switch_to_it(
                        (By.CSS_SELECTOR, "iframe[src*='arkoselabs.com']")
                    )
                )
                WebDriverWait(self.driver, 30).until(
                    EC.frame_to_be_available_and_switch_to_it(
                        (By.CSS_SELECTOR, "iframe[src*='arkoselabs.com']")
                    )
                )
                # Wait for button using multiple possible identifiers
                auth_button = WebDriverWait(self.driver, 30).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(., 'Authenticate') or contains(., 'Verify')]",
                        )
                    )
                )

                # Use JavaScript click as fallback
                self.driver.execute_script("arguments[0].click();", auth_button)
                self.driver.switch_to.default_content()
                time.sleep(15)
            except Exception as e:
                logging.error(f"Failed to handle Arkose authentication: {str(e)}")
                return False

            captcha_solver = CaptchaSolver(self.driver, self.config, self.current_proxy)
            if token := captcha_solver.solve_captcha("arkose"):
                self.driver.execute_script(
                    f'document.querySelector("input[name=\\"fc-token\\"]").value = "{token}";'
                )
                time.sleep(2)
                WebDriverWait(self.driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
                ).click()
            else:
                return False
            if code := self._get_verification_code():
                self._enter_verification_code(code)
                return self._set_password()
            return False
        except Exception as e:
            logging.error(f"Registration failed: {str(e)}")
            return False

    def _fill_form(self):
        name = self.fake.name()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "name"))
        ).send_keys(name)
        try:
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.NAME, "phone_number"))
            )
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[contains(text(), 'email instead')]")
                )
            ).click()
        except Exception:
            pass
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        ).send_keys(self.config["email"])
        self._fill_birthdate()

    def _set_password(self) -> bool:
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            ).send_keys(self.DEFAULT_PASSWORD)
            self.driver.find_element(
                By.XPATH, "//div[@role='button'][contains(.,'Next')]"
            ).click()
            return True
        except:
            return False

    def _enter_verification_code(self, code: str):
        code_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "verfication_code"))
        )
        code_input.send_keys(code)
        self.driver.find_element(By.XPATH, "//span[text()='Next']").click()

    def create_account(self) -> Optional[dict]:
        if self._register_account():
            self.account_details = self._get_account_tokens()
            return self.account_details
        return None

    def _get_account_tokens(self) -> dict:
        guest_token = self._get_guest_token()
        response = requests.post(
            "https://api.twitter.com/auth/1/xauth_password.json",
            headers={"X-Guest-Token": guest_token},
            data={
                "x_auth_identifier": self.config["email"],
                "x_auth_password": self.DEFAULT_PASSWORD,
                "send_error_codes": "true",
            },
            proxies=build_requests_proxies(self.current_proxy),
        )
        if "oauth_token" in response.json():
            tokens = response.json()
            return {
                "oauth_token": tokens["oauth_token"],
                "oauth_secret": tokens["oauth_token_secret"],
                "email": self.config["email"],
                "proxy": self.current_proxy,
            }
        return {}

    def _get_guest_token(self) -> str:
        response = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers={
                "Authorization": "Bearer XzAwAAAAAAMHCxpeSDG1gLNLghVe8d74hl6k4%3DRUMF4xAQLsbeBhTSRrCiQpJtxoGWeyHrDb5te2jpGskWDFW82F"
            },
            proxies=build_requests_proxies(self.current_proxy),
        )
        return response.json()["guest_token"]


class EmailClient:
    def __init__(self, service: str, email: str, credential: str):
        self.service = service
        self.email = email
        self.credential = credential

    def get_verification_code(self) -> Optional[str]:
        handler = getattr(self, f"_handle_{self.service}", None)
        return handler() if handler else None

    def _handle_outlook(self) -> str:
        pass

    def _handle_gmail(self) -> str:
        pass


if __name__ == "__main__":
    config = {
        "email": "mistorsidor@outlook.com",
        "email_service": "outlook",
        "email_credential": "password123",
        "use_proxy": False,
        "headless": False,
        "anti_captcha_key": Config.ANTI_CAPTCHA_KEY,
    }
    bot = TwitterAccountCreator(config)
    if account := bot.create_account():
        logging.info(f"Account created: {account['email']}")
        logging.info(f"OAuth Token: {account['oauth_token']}")
