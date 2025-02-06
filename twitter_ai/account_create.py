import time
import random
import re
from typing import Optional, List, Tuple
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from faker import Faker
from bs4 import BeautifulSoup
import pandas as pd
import requests
from requests_oauthlib import OAuth1
from utils.twitter_utils import PROXY_MANAGER  # Added import
from utils.config import Config
from anticaptchaofficial.funcaptchaproxyless import funcaptchaProxyless
from anticaptchaofficial.funcaptchaproxyon import funcaptchaProxyon


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
            self.current_proxy = self._get_working_proxy()
        self.driver = self._init_driver()

    def _init_driver(self) -> uc.Chrome:
        options = ChromeOptions()
        if self.config["use_proxy"] and self.current_proxy:
            options.add_argument(f"--proxy-server=http://{self.current_proxy}")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-blink-features=AutomationControlled")
        return uc.Chrome(options=options, headless=self.config.get("headless", False))

    def _test_proxy(self, proxy: str) -> bool:
        try:
            proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            response = requests.get("https://x.com", proxies=proxies, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _get_working_proxy(self) -> Optional[str]:
        while True:
            proxy_info = PROXY_MANAGER.get_next_proxy()
            if not proxy_info:
                return None
            proxy = proxy_info[0]
            if self._test_proxy(proxy):
                return proxy
            print(f"Proxy {proxy} failed, trying next...")

    def _solve_arkose_captcha(self) -> Optional[str]:
        if self.config.get("use_proxy") and self.current_proxy:
            solver = funcaptchaProxyon()
            # Parse proxy details
            proxy_parts = self.current_proxy.split("@")
            if len(proxy_parts) == 2:
                auth_part, host_port_part = proxy_parts
                username, password = auth_part.split(":", 1)
            else:
                host_port_part = proxy_parts[0]
                username, password = None, None

            host_port = host_port_part.split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 80

            solver.set_proxy_address(host)
            solver.set_proxy_port(port)
            if username and password:
                solver.set_proxy_login(username)
                solver.set_proxy_password(password)

            user_agent = self.driver.execute_script("return navigator.userAgent;")
            solver.set_user_agent(user_agent)
        else:
            solver = funcaptchaProxyless()

        solver.set_verbose(1)
        solver.set_key(self.config["anti_captcha_key"])
        solver.set_website_url("https://x.com/i/flow/signup")
        solver.set_js_api_domain("client-api.arkoselabs.com")
        solver.set_website_key("2CB16598-CB82-4CF7-B332-5990DB66F3AB")
        solver.set_soft_id(0)

        token = solver.solve_and_return_solution()
        return token if token else None

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

            # First Next click
            WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
            ).click()

            # Second Next click
            WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
            ).click()

            if token := self._solve_arkose_captcha():
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
            print(f"Registration failed: {str(e)}")
            return False

    def _fill_form(self):
        # Fill name
        name = self.fake.name()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "name"))
        ).send_keys(name)

        # Check for phone field and switch to email if needed
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
            pass  # Phone field not present

        # Fill email
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        ).send_keys(self.config["email"])

        # Fill birthdate
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
        pass

    def _handle_gmail(self) -> str:
        pass


if __name__ == "__main__":
    config = {
        "email": "example@temp.com",
        "email_service": "outlook",
        "email_credential": "password123",
        "use_proxy": True,
        "headless": False,
        "anti_captcha_key": Config.ANTI_CAPTCHA_KEY,
    }
    bot = TwitterAccountCreator(config)
    if account := bot.create_account():
        print(f"Account created: {account['email']}")
        print(f"OAuth Token: {account['oauth_token']}")
