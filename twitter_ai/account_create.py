import time
import random
import re
from typing import Optional, List, Tuple
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from faker import Faker
from bs4 import BeautifulSoup
import pandas as pd
import requests
from requests_oauthlib import OAuth1


class TwitterAccountCreator:
    TWITTER_AUTH_URL = "https://api.twitter.com/oauth/access_token"
    OAUTH = OAuth1(
        "3nVuSoBZnx6U4vzUxf5w", "Bcs59EFbbsdF6Sl9Ng71smgStWEGwXXKSjYvPVt7qys"
    )
    DEFAULT_PASSWORD = "BOTwownow24368"

    def __init__(self, config: dict):
        self.config = config
        self.driver = self._init_driver()
        self.fake = Faker()
        self.account_details = {}
        self.current_proxy = (
            random.choice(config["proxy_list"]) if config["proxy_list"] else None
        )

    def _init_driver(self) -> uc.Chrome:
        options = ChromeOptions()

        if self.config["use_proxy"] and self.current_proxy:
            options.add_argument(f"--proxy-server=http://{self.current_proxy}")

        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-blink-features=AutomationControlled")

        return uc.Chrome(options=options, headless=self.config.get("headless", False))

    def _handle_captcha(self) -> bool:
        try:
            self.driver.switch_to.frame(self.driver.find_element(By.TAG_NAME, "iframe"))
            challenge_text = self.driver.find_element(By.XPATH, "//h2").text
            challenge_type = re.search(
                r"Select all (.*?) images", challenge_text
            ).group(1)

            for i in range(1, 7):
                element = self.driver.find_element(By.XPATH, f"//li[{i}]/a")
                element.screenshot(f"captcha_{i}.png")
                if self._detect_captcha_type(f"captcha_{i}.png") == challenge_type:
                    element.click()
                    time.sleep(2)
                    return True
            return False
        except Exception as e:
            print(f"Captcha handling failed: {str(e)}")
            return False

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
            WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[text()='Create account']")
                )
            ).click()

            self._fill_form()
            self._handle_captcha()

            if code := self._get_verification_code():
                self._enter_verification_code(code)
                return self._set_password()
            return False
        except Exception as e:
            print(f"Registration failed: {str(e)}")
            return False

    def _fill_form(self):
        fields = {
            "name": self.fake.name(),
            "email": self.config["email"],
            "password": self.DEFAULT_PASSWORD,
        }

        for field, value in fields.items():
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, field))
            )
            element.send_keys(value)

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
            proxies={"https": self.current_proxy} if self.current_proxy else None,
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
                "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAAFXzAwAAAAAAMHCxpeSDG1gLNLghVe8d74hl6k4%3DRUMF4xAQLsbeBhTSRrCiQpJtxoGWeyHrDb5te2jpGskWDFW82F"
            },
            proxies={"https": self.current_proxy} if self.current_proxy else None,
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
        # Implement Outlook email checking
        pass

    def _handle_gmail(self) -> str:
        # Implement Gmail email checking
        pass


# Example usage
if __name__ == "__main__":
    config = {
        "email": "example@temp.com",
        "email_service": "outlook",
        "email_credential": "password123",
        "proxy_list": ["ip:port1", "ip:port2"],
        "use_proxy": False,
        "headless": False,
    }

    bot = TwitterAccountCreator(config)
    if account := bot.create_account():
        print(f"Account created: {account['email']}")
        print(f"OAuth Token: {account['oauth_token']}")
