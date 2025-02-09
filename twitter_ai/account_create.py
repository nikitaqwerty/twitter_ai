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
from utils.twitter_utils import PROXY_MANAGER  # Added import
from utils.config import Config
from anticaptchaofficial.funcaptchaproxyless import funcaptchaProxyless
from anticaptchaofficial.funcaptchaproxyon import funcaptchaProxyon
import logging
import string
import os
import tempfile

# Configure logging
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
            self.current_proxy = self._get_working_proxy()
            logging.info(f"Using proxy: {self.current_proxy}")
        self.driver = self._init_driver()

    def _init_driver(self) -> uc.Chrome:
        try:
            options = ChromeOptions()
            if self.config["use_proxy"] and self.current_proxy:
                proxy_parts = self.current_proxy.split("@")
                if len(proxy_parts) == 2:
                    auth_part, host_port_part = proxy_parts
                    username, password = auth_part.split(":", 1)
                    host, port = host_port_part.split(":")
                    extension_dir = self._create_proxy_auth_extension(
                        proxy_host=host,
                        proxy_port=port,
                        proxy_username=username,
                        proxy_password=password,
                        scheme="http",
                    )
                    options.add_argument(f"--load-extension={extension_dir}")
                else:
                    options.add_argument(f"--proxy-server=http://{self.current_proxy}")
            options.add_argument("--disable-dev-shm-usage")
            # If using a proxy with authentication (handled via an extension), avoid incognito mode,
            # because extensions are disabled in incognito by default.
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

    def _create_proxy_auth_extension(
        self, proxy_host, proxy_port, proxy_username, proxy_password, scheme="https"
    ) -> str:
        """
        Creates an unpacked Chrome extension to handle proxy authentication.
        Returns the path to the created extension directory.
        """
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version": "22.0.0"
        }
        """
        background_js = string.Template(
            """
            var config = {
                mode: "fixed_servers",
                rules: {
                    singleProxy: {
                        scheme: "${scheme}",
                        host: "${host}",
                        port: parseInt(${port})
                    },
                    bypassList: ["localhost"]
                }
            };
            chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
            function callbackFn(details) {
                return {
                    authCredentials: {
                        username: "${username}",
                        password: "${password}"
                    }
                };
            }
            chrome.webRequest.onAuthRequired.addListener(
                callbackFn,
                {urls: ["<all_urls>"]},
                ['blocking']
            );
            """
        ).substitute(
            scheme=scheme,
            host=proxy_host,
            port=proxy_port,
            username=proxy_username,
            password=proxy_password,
        )
        extension_dir = tempfile.mkdtemp(prefix="proxy_auth_ext_")
        with open(os.path.join(extension_dir, "manifest.json"), "w") as f:
            f.write(manifest_json)
        with open(os.path.join(extension_dir, "background.js"), "w") as f:
            f.write(background_js)
        return extension_dir

    def _test_proxy(self, proxy: str) -> bool:
        try:
            proxy_parts = proxy.split("@")
            if len(proxy_parts) == 2:
                auth_part, host_port_part = proxy_parts
                username, password = auth_part.split(":", 1)
                proxies = {
                    "http": f"http://{username}:{password}@{host_port_part}",
                    "https": f"http://{username}:{password}@{host_port_part}",
                }
            else:
                proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            response = requests.get("https://x.com", proxies=proxies, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _get_working_proxy(self) -> Optional[str]:
        while True:
            proxy_info = PROXY_MANAGER.get_next_proxy(
                source="smartproxy-residential-rotating"
            )
            if not proxy_info:
                return None
            proxy = proxy_info[0]
            if self._test_proxy(proxy):
                logging.info(f"Found working proxy: {proxy}")
                return proxy
            logging.warning(f"Proxy {proxy} failed, trying next...")

    def _solve_arkose_captcha(self) -> Optional[str]:
        if self.config.get("use_proxy") and self.current_proxy:
            solver = funcaptchaProxyon()
            proxy_parts = self.current_proxy.split("@")
            if len(proxy_parts) == 2:
                auth_part, host_port_part = proxy_parts
                username, password = auth_part.split(":", 1)
                host, port = host_port_part.split(":")
            else:
                host, port = proxy_parts[0].split(":")
                username, password = None, None
            solver.set_proxy_address(host)
            solver.set_proxy_port(int(port))
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
            pass  # Phone field not present
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
            proxies=(
                {"https": f"http://{self.current_proxy}"}
                if self.current_proxy
                else None
            ),
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
            proxies=(
                {"https": f"http://{self.current_proxy}"}
                if self.current_proxy
                else None
            ),
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
        "use_proxy": True,
        "headless": False,
        "anti_captcha_key": Config.ANTI_CAPTCHA_KEY,
    }
    bot = TwitterAccountCreator(config)
    if account := bot.create_account():
        logging.info(f"Account created: {account['email']}")
        logging.info(f"OAuth Token: {account['oauth_token']}")
