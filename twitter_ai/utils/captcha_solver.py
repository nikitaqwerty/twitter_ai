from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import time
import os
import tempfile
import subprocess
from PIL import Image
from anticaptchaofficial.funcaptchaproxyless import funcaptchaProxyless
from anticaptchaofficial.funcaptchaproxyon import funcaptchaProxyon
from typing import Optional
import re
import socket
from PIL import ImageChops


class CaptchaSolver:
    def __init__(self, driver, config: dict, proxy: Optional[str] = None):
        self.driver = driver
        self.config = config
        self.proxy = proxy

    def solve_captcha(self, captcha_type: str = "arkose") -> Optional[str]:
        if captcha_type == "arkose":
            return self.solve_arkose_captcha()
        elif captcha_type == "arkose_vlm":
            solved = self.solve_arkose_captcha_vlm()
            return "vlm_solved" if solved else None
        else:
            raise NotImplementedError(f"Captcha type '{captcha_type}' not supported.")

    def solve_arkose_captcha(self) -> Optional[str]:
        if self.config.get("use_proxy") and self.proxy:
            solver = funcaptchaProxyon()
            proxy_parts = self.proxy.split("@")
            if len(proxy_parts) == 2:
                auth_part, host_port_part = proxy_parts
                username, password = auth_part.split(":", 1)
                host, port = host_port_part.split(":")
            else:
                host, port = self.proxy.split(":")
                username, password = None, None
            try:
                resolved_host = socket.gethostbyname(host)
            except Exception as e:
                logging.error(f"Failed to resolve proxy host {host}: {e}")
                resolved_host = host
            solver.set_proxy_address(resolved_host)
            solver.set_proxy_port(int(port))
            if username and password:
                solver.set_proxy_login(username)
                solver.set_proxy_password(password)
            solver.set_proxy_type("HTTPS")
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

    def solve_arkose_captcha_vlm(self) -> bool:
        from selenium.webdriver.common.by import By

        try:
            from llm.llm_api import GroqAPIHandler
        except ImportError as e:
            logging.error("Failed to import GroqAPIHandler: " + str(e))
            return False
        groq_handler = GroqAPIHandler(api_key=self.config.GROQ_API_KEY)
        max_attempts = 30
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            logging.info(f"VLM captcha attempt {attempt}")
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                screenshot_path = tmp.name
            try:
                # Capture only the current iframe by taking a screenshot of its root HTML element.
                iframe_html = self.driver.find_element(By.TAG_NAME, "html")
                iframe_html.screenshot(screenshot_path)
                # Crop the screenshot: keep pixels from 10% to 50% of the image height.
                with Image.open(screenshot_path) as img:
                    w, h = img.size
                    cropped = img.crop((0, int(h * 0.1), w, int(h * 0.5)))
            except Exception as e:
                logging.error(f"Failed to take or crop screenshot: {e}")
                os.unlink(screenshot_path)
                return False

            # Split the cropped image into left and right halves
            left_img = cropped.crop((0, 0, cropped.width // 2, cropped.height))
            right_img = cropped.crop(
                (cropped.width // 2, 0, cropped.width, cropped.height)
            )

            # Post processing: Remove white borders from the images
            left_img = remove_white_border(left_img)
            right_img = remove_white_border(right_img)

            # Save left and right images to temporary files
            left_temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            left_path = left_temp.name
            left_img.save(left_path)
            left_temp.close()

            right_temp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            right_path = right_temp.name
            right_img.save(right_path)
            right_temp.close()

            # Optionally, open the images in Preview for debugging
            subprocess.run(["open", "-a", "Preview", left_path])
            subprocess.run(["open", "-a", "Preview", right_path])

            left_prompt = "What is the number on the picture? Output only the nubmer"
            right_prompt = "What is the measured length of the object on the picture? Do not use units, reason and output number in the end"

            left_response = groq_handler.get_vlm_response(
                left_prompt, left_path, model="llama-3.2-11b-vision-preview"
            )
            right_response = groq_handler.get_vlm_response(right_prompt, right_path)

            # Clean up temporary files
            os.unlink(screenshot_path)
            os.unlink(left_path)
            os.unlink(right_path)

            if left_response is None or right_response is None:
                logging.error("No response from Groq VLM API for one of the queries.")
                return False

            logging.info(f"Left response: {left_response}")
            logging.info(f"Right response: {right_response}")

            # Extract last integer number from both responses
            left_numbers = re.findall(r"\d+", left_response)
            right_numbers = re.findall(r"\d+", right_response)
            if not left_numbers or not right_numbers:
                logging.error("Failed to extract numbers from VLM responses.")
                try:
                    next_button = self.wait_for_element_to_be_clickable(
                        (By.XPATH, "//a[@aria-label='Navigate to next image']"),
                        timeout=10,
                    )
                    next_button.click()
                    time.sleep(3)
                except Exception as e:
                    logging.error(f"Failed to click 'Next' button: {e}")
                    return False
                continue

            left_number = int(left_numbers[-1])
            right_number = int(right_numbers[-1])
            logging.info(
                f"Extracted left number: {left_number}, right number: {right_number}"
            )

            if left_number == right_number:
                try:
                    submit_button = self.wait_for_element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Submit')]"), timeout=10
                    )
                    submit_button.click()
                    time.sleep(20)  # Wait for the captcha to process
                    if not self.is_captcha_round_remaining():
                        return True  # No more captcha rounds
                except Exception as e:
                    logging.error(f"Failed to click 'Submit' button: {e}")
                    return False
            else:
                try:
                    next_button = self.wait_for_element_to_be_clickable(
                        (By.XPATH, "//a[@aria-label='Navigate to next image']"),
                        timeout=10,
                    )
                    next_button.click()
                    time.sleep(3)
                except Exception as e:
                    logging.error(f"Failed to click 'Next' button: {e}")
                    return False
        logging.error("Exceeded maximum attempts for VLM captcha solving.")
        return False

    def handle_arkose_iframe_authentication(self) -> bool:
        try:
            time.sleep(3)
            # Switch into the Arkose iframe three times to ensure proper context.
            for _ in range(3):
                WebDriverWait(self.driver, 30).until(
                    EC.frame_to_be_available_and_switch_to_it(
                        (By.CSS_SELECTOR, "iframe[src*='arkoselabs.com']")
                    )
                )
            # Wait for the authentication button to be clickable.
            auth_button = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[contains(., 'Authenticate') or contains(., 'Verify')]",
                    )
                )
            )
            # Use JavaScript click as a fallback.
            self.driver.execute_script("arguments[0].click();", auth_button)
            # Wait for the Submit button to be clickable after authentication.
            _ = self.wait_for_element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Submit')]"), timeout=30
            )
            time.sleep(1)  # Wait for the captcha to process
            return True
        except Exception as e:
            logging.error(f"Failed to handle Arkose authentication: {str(e)}")
            return False

    def wait_for_element_to_be_clickable(self, locator, timeout=30):
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )

    def is_captcha_round_remaining(self):
        try:
            self.driver.find_element(By.XPATH, "//button[contains(text(), 'Submit')]")
            return True
        except:
            return False


def remove_white_border(image):
    bg = Image.new(image.mode, image.size, image.getpixel((0, 0)))
    diff = ImageChops.difference(image, bg)
    bbox = diff.getbbox()
    return image.crop(bbox) if bbox else image
