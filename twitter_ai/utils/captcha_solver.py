from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import time
import os
import tempfile
import subprocess
from PIL import Image, ImageChops
from anticaptchaofficial.funcaptchaproxyless import funcaptchaProxyless
from anticaptchaofficial.funcaptchaproxyon import funcaptchaProxyon
from typing import Optional
import re
import socket
import csv


class CaptchaSolver:
    def __init__(self, driver, config: dict, proxy: Optional[str] = None):
        self.driver = driver
        self.config = config
        self.proxy = proxy

        # Initialize CSV logging in the root of the data folder.
        self.csv_log_path = os.path.join(os.getcwd(), "data", "runs.csv")
        os.makedirs(os.path.dirname(self.csv_log_path), exist_ok=True)
        if not os.path.exists(self.csv_log_path):
            with open(self.csv_log_path, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        "run timestamp",
                        "filename left",
                        "filename right",
                        "vlm output extracted number left",
                        "vlm output extracted number right",
                        "vlm left model name",
                        "vlm right model name",
                        "left ground truth",
                        "right ground truth",
                    ]
                )

    def log_run(
        self,
        run_timestamp,
        filename_left,
        filename_right,
        left_extracted,
        right_extracted,
        left_model,
        right_model,
        left_ground_truth,
        right_ground_truth,
    ):
        with open(self.csv_log_path, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    run_timestamp,
                    filename_left,
                    filename_right,
                    left_extracted,
                    right_extracted,
                    left_model,
                    right_model,
                    left_ground_truth,
                    right_ground_truth,
                ]
            )

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
        try:
            from llm.llm_api import GroqAPIHandler, g4fAPIHandler
        except ImportError as e:
            logging.error("Failed to import API handlers: " + str(e))
            return False

        groq_handler = GroqAPIHandler(api_key=self.config.GROQ_API_KEY)
        g4f_handler = g4fAPIHandler(model="gemini-2.0-flash")
        max_rounds = 3
        max_attempts = 10

        # Create data directory for saving screenshots
        data_dir = os.path.join(os.getcwd(), "data", "captcha_screenshots")
        os.makedirs(data_dir, exist_ok=True)

        for round_num in range(1, max_rounds + 1):
            round_start_time = time.strftime("%Y%m%d_%H%M%S")
            logging.info(f"Starting captcha round {round_num}")
            # Capture the base screenshot for this round.
            try:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    screenshot_path = tmp.name
                iframe_html = self.driver.find_element(By.TAG_NAME, "html")
                iframe_html.screenshot(screenshot_path)
                with Image.open(screenshot_path) as img:
                    w, h = img.size
                    cropped = img.crop((0, int(h * 0.1), w, int(h * 0.5)))
            except Exception as e:
                logging.error(
                    f"Failed to capture or crop screenshot in round {round_num}: {e}"
                )
                if os.path.exists(screenshot_path):
                    os.unlink(screenshot_path)
                continue  # Proceed to next round

            # Extract and process the left image (remains constant during the round)
            left_img = cropped.crop((0, 0, cropped.width // 2, cropped.height))
            left_img = remove_white_border(left_img)
            # Save permanent copy of left image
            left_perm_path = os.path.join(
                data_dir, f"{round_start_time}_round{round_num}_left.jpg"
            )
            left_img.save(left_perm_path)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as left_temp:
                left_path = left_temp.name
                left_img.save(left_path)
            subprocess.run(["open", "-a", "Preview", left_path])

            left_prompt = "What is the number on the picture? Output only the nubmer"
            left_response = groq_handler.get_vlm_response(
                left_prompt, left_path, model="llama-3.2-11b-vision-preview"
            )
            if left_response is None:
                logging.error(
                    f"No response from Groq VLM API for left query in round {round_num}."
                )
                os.unlink(screenshot_path)
                os.unlink(left_path)
                continue  # Try next round
            left_numbers = re.findall(r"\d+", left_response)
            if not left_numbers:
                logging.error(
                    f"Failed to extract number from left VLM response in round {round_num}."
                )
                os.unlink(screenshot_path)
                os.unlink(left_path)
                continue  # Try next round
            left_number = int(left_numbers[-1])
            logging.info(
                f"Round {round_num} left response: {left_response} (extracted {left_number})"
            )

            # Attempt loop within the current round.
            for attempt in range(1, max_attempts + 1):
                logging.info(f"Round {round_num} attempt {attempt}")
                if attempt == 1:
                    # Use the existing screenshot's right part for the first attempt.
                    right_img = cropped.crop(
                        (cropped.width // 2, 0, cropped.width, cropped.height)
                    )
                else:
                    right_screenshot_path = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            suffix=".jpg", delete=False
                        ) as tmp:
                            right_screenshot_path = tmp.name
                        iframe_html = self.driver.find_element(By.TAG_NAME, "html")
                        iframe_html.screenshot(right_screenshot_path)
                        with Image.open(right_screenshot_path) as img:
                            w, h = img.size
                            cropped_attempt = img.crop(
                                (0, int(h * 0.1), w, int(h * 0.5))
                            )
                        right_img = cropped_attempt.crop(
                            (
                                cropped_attempt.width // 2,
                                0,
                                cropped_attempt.width,
                                cropped_attempt.height,
                            )
                        )
                        os.unlink(right_screenshot_path)
                    except Exception as e:
                        logging.error(
                            f"Failed to capture right screenshot on round {round_num} attempt {attempt}: {e}"
                        )
                        if right_screenshot_path and os.path.exists(
                            right_screenshot_path
                        ):
                            os.unlink(right_screenshot_path)
                        continue  # Try next attempt

                right_img = remove_white_border(right_img)
                # Save permanent copy of right image
                right_perm_path = os.path.join(
                    data_dir,
                    f"{round_start_time}_round{round_num}_attempt{attempt}_right.jpg",
                )
                right_img.save(right_perm_path)
                with tempfile.NamedTemporaryFile(
                    suffix=".jpg", delete=False
                ) as right_temp:
                    right_path = right_temp.name
                    right_img.save(right_path)
                subprocess.run(["open", "-a", "Preview", right_path])

                right_prompt = (
                    "Look at the attached image. The image shows a simple measuring scale with numerical markings."
                    "An object’s edge is aligned with one of these marks."
                    "Your task is to identify the numerical value on the scale where the object ends and output that measured length as a number (in the same units indicated on the scale). Provide the measurement round integer number in your answer."
                )
                right_response = g4f_handler.get_vlm_response(right_prompt, right_path)
                os.unlink(right_path)
                extracted_right = ""
                if right_response is not None:
                    nums = re.findall(r"\d+", right_response)
                    if nums:
                        extracted_right = int(nums[-1])
                # Log this attempt's run data to CSV.
                self.log_run(
                    round_start_time,
                    left_perm_path,
                    right_perm_path,
                    left_number,
                    extracted_right,
                    "llama-3.2-11b-vision-preview",
                    "gemini-2.0-flash",
                    "",
                    "",
                )
                if right_response is None:
                    logging.error(
                        f"No response from g4f VLM API for right query in round {round_num} attempt {attempt}."
                    )
                    if attempt < max_attempts:
                        try:
                            next_button = self.wait_for_element_to_be_clickable(
                                (By.XPATH, "//a[@aria-label='Navigate to next image']"),
                                timeout=10,
                            )
                            next_button.click()
                            time.sleep(3)
                        except Exception as e:
                            logging.error(
                                f"Failed to click 'Next' button in round {round_num} attempt {attempt}: {e}"
                            )
                            break
                        continue
                    else:
                        break

                if extracted_right == "":
                    logging.error(
                        f"Failed to extract number from right VLM response in round {round_num} attempt {attempt}."
                    )
                    if attempt < max_attempts:
                        try:
                            next_button = self.wait_for_element_to_be_clickable(
                                (By.XPATH, "//a[@aria-label='Navigate to next image']"),
                                timeout=10,
                            )
                            next_button.click()
                            time.sleep(3)
                        except Exception as e:
                            logging.error(
                                f"Failed to click 'Next' button in round {round_num} attempt {attempt}: {e}"
                            )
                            break
                        continue
                    else:
                        break

                logging.info(
                    f"Round {round_num} attempt {attempt} right response: {right_response} (extracted {extracted_right})"
                )
                if left_number == extracted_right:
                    try:
                        submit_button = self.wait_for_element_to_be_clickable(
                            (By.XPATH, "//button[contains(text(), 'Submit')]"),
                            timeout=10,
                        )
                        submit_button.click()
                        time.sleep(5)  # Wait for captcha processing
                        os.unlink(screenshot_path)
                        os.unlink(left_path)
                        if not self.is_captcha_round_remaining():
                            return True  # Captcha solved
                        else:
                            logging.info(
                                f"Captcha round {round_num} solved, but further rounds remain."
                            )
                            break  # Proceed to next round
                    except Exception as e:
                        logging.error(
                            f"Failed to click 'Submit' button in round {round_num} attempt {attempt}: {e}"
                        )
                        os.unlink(screenshot_path)
                        os.unlink(left_path)
                        break
                else:
                    if attempt < max_attempts:
                        try:
                            next_button = self.wait_for_element_to_be_clickable(
                                (By.XPATH, "//a[@aria-label='Navigate to next image']"),
                                timeout=10,
                            )
                            next_button.click()
                            time.sleep(3)
                        except Exception as e:
                            logging.error(
                                f"Failed to click 'Next' button in round {round_num} attempt {attempt}: {e}"
                            )
                            break
                    else:
                        logging.error(
                            f"Exceeded maximum attempts for round {round_num}."
                        )
            # Cleanup round-specific temporary files.
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
            if os.path.exists(left_path):
                os.unlink(left_path)
        logging.error("Exceeded maximum captcha rounds.")
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
