#!/usr/bin/env python3
import time
import random
import logging
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from faker import Faker
from utils.config import Config
from utils.dataset_captcha_solver import CaptchaSolver

logging.basicConfig(level=logging.INFO)


class CaptchaCollector:
    def __init__(self, config: dict):
        self.config = config
        self.fake = Faker()
        self.driver = self._init_driver()

    def _init_driver(self) -> uc.Chrome:
        options = ChromeOptions()
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-blink-features=AutomationControlled")
        return uc.Chrome(
            options=options,
            headless=self.config.get("headless", False),
            version_main=132,
        )

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

    def collect_captcha(self):
        try:
            self.driver.get("https://x.com/i/flow/signup?mx=2")
            WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[text()='Create account']")
                )
            ).click()
            self._fill_form()
            time.sleep(1)
            WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
            ).click()
            time.sleep(1)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
                ).click()
                time.sleep(1)
            except Exception:
                logging.info("Second Next button not found, proceeding...")
            captcha_solver = CaptchaSolver(self.driver, Config())
            if not captcha_solver.handle_arkose_iframe_authentication():
                logging.info("Failed to handle Arkose iframe authentication.")
                return None
            captcha_solver.solve_captcha("arkose_vlm")
            logging.info("Captcha handled successfully.")
            return None
        except Exception as e:
            logging.error(f"Captcha collection failed: {e}")
            return None
        finally:
            self.driver.quit()


if __name__ == "__main__":
    base_config = {
        "email_service": "outlook",
        "email_credential": "password123",
        "headless": False,
        "anti_captcha_key": Config.ANTI_CAPTCHA_KEY,
    }
    fake = Faker()
    while True:
        email = f"{fake.user_name()}{random.randint(1000, 9999)}@gmail.com"
        config = {**base_config, "email": email}
        collector = CaptchaCollector(config)
        collector.collect_captcha()
        logging.info("Iteration complete. Restarting in 5 seconds...")
        time.sleep(5)
