#!/usr/bin/env python3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import time
import os
import tempfile
from PIL import Image, ImageChops
from typing import Optional
import re
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
                        "task type",
                    ]
                )

        # Initialize LLM API handlers and model names as variables.
        try:
            from llm.llm_api import GroqAPIHandler, g4fAPIHandler

            self.GroqAPIHandler = GroqAPIHandler
            self.g4fAPIHandler = g4fAPIHandler
        except ImportError as e:
            logging.error("Failed to import LLM API handlers: " + str(e))
            self.GroqAPIHandler = None
            self.g4fAPIHandler = None

        self.groq_model = config.get("groq_model", "llama-3.2-11b-vision-preview")
        self.g4f_model = config.get("g4f_model", "gemini-2.0-flash")
        self.groq_right_model = config.get(
            "groq_right_model", "llama-3.2-90b-vision-preview"
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
        task_type,
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
                    task_type,
                ]
            )

    def solve_captcha(self, captcha_type: str = "arkose_vlm") -> Optional[str]:
        if captcha_type == "arkose_vlm":
            solved = self.solve_arkose_captcha_vlm()
            return "vlm_solved" if solved else None
        else:
            raise NotImplementedError(f"Captcha type '{captcha_type}' not supported.")

    def solve_arkose_captcha_vlm(self) -> bool:
        if not self.GroqAPIHandler or not self.g4fAPIHandler:
            logging.error("LLM API handlers are not available.")
            return False

        groq_handler = self.GroqAPIHandler(api_key=self.config.get("GROQ_API_KEY"))
        g4f_handler = self.g4fAPIHandler(model=self.g4f_model)
        max_rounds = 3
        max_attempts = 6

        # Create data directory for saving screenshots
        data_dir = os.path.join(os.getcwd(), "data", "captcha_screenshots")
        os.makedirs(data_dir, exist_ok=True)

        # Initialize task type and prompt variables (set only once on the first round)
        task_type = None
        left_prompt = None
        right_prompt = None

        cycles = 2  # Two cycles of rounds
        for cycle in range(1, cycles + 1):
            logging.info(f"Starting cycle {cycle}")
            for round_num in range(1, max_rounds + 1):
                round_start_time = time.strftime("%Y%m%d_%H%M%S")
                logging.info(f"Starting cycle {cycle} round {round_num}")

                # On the very first round of the first cycle, determine the captcha task type if submit button is clickable.
                if cycle == 1 and round_num == 1 and task_type is None:
                    try:
                        submit_button = self.wait_for_element_to_be_clickable(
                            (By.XPATH, "//button[contains(text(), 'Submit')]"),
                            timeout=5,
                        )
                        html_elem = self.driver.find_element(By.TAG_NAME, "html")
                        with tempfile.NamedTemporaryFile(
                            suffix=".png", delete=False
                        ) as tmp:
                            task_screenshot_path = tmp.name
                        html_elem.screenshot(task_screenshot_path)
                        with Image.open(task_screenshot_path) as img:
                            w, h = img.size
                            task_img = img.crop((0, 0, w, h // 2))
                        task_img.save(task_screenshot_path)
                        task_prompt = (
                            "Determine the captcha task type from the screenshot. "
                            "The possible task types are: 'length', 'quantity', 'sum' or 'seats'. "
                            "'length' is usually a task to get a measurement of an object on scale"
                            "'quantity' is usually a task to count a number of objects (like pins) "
                            "'sum' is a task to add up numbers displayed on objects and compare to a given total. "
                            "'seats' is usually a task to identify a seat label composed of a letter and a 1 or 2 digit number (e.g., 'A-1' or 'B-12'). "
                            "Output only the task type word."
                        )
                        task_response = groq_handler.get_vlm_response(
                            task_prompt,
                            task_screenshot_path,
                            model=self.groq_right_model,
                        )
                        if task_response is None:
                            task_type = "length"
                        else:
                            task_response_lower = task_response.lower()
                            if "quantity" in task_response_lower:
                                task_type = "quantity"
                            elif "seats" in task_response_lower:
                                task_type = "seats"
                            elif "sum" in task_response_lower:
                                task_type = "sum"
                            else:
                                task_type = "length"
                        os.unlink(task_screenshot_path)
                        logging.info(f"Determined captcha task type: {task_type}")
                    except Exception as e:
                        logging.error(f"Failed to determine task type: {e}")
                        task_type = "length"

                    # Define prompts based on determined task type.
                    if task_type == "length":
                        left_prompt = (
                            "What is the number on the picture? Output only the number."
                        )
                        right_prompt = (
                            "Look at the attached image. The image shows a simple measuring scale with numerical markings. "
                            "An object’s edge is aligned with one of these marks. Your task is to identify the numerical value on the scale "
                            "where the object ends and output that measured length as a number (in the same units indicated on the scale). "
                            "Provide the measurement as a round integer number in your answer."
                        )
                    elif task_type == "quantity":
                        left_prompt = "What is the number on the picture? Output only the number representing the count of objects."
                        right_prompt = (
                            "Examine the attached image. The image displays a collection of objects. Your task is to count the number of objects "
                            "and output that number."
                        )
                    elif task_type == "seats":
                        left_prompt = (
                            "What is the combination of a letter and a 1 or 2 digit number displayed on the left image? "
                            "Provide them concatenated with a dash (e.g., 'A-1' or 'A-12')."
                        )
                        right_prompt = (
                            "Look at the attached image. The image shows seats arranged in rows and columns, with each seat labeled by a letter and a 1 or 2 digit number. "
                            "Only one seat is occupied by a person, which is the target seat. "
                            "Identify the label corresponding to the occupied seat and output it exactly as shown (e.g., 'A-1' or 'A-12')."
                        )
                    elif task_type == "sum":
                        left_prompt = "What is the number displayed on the left image? Output only the number."
                        right_prompt = (
                            "Look at the attached image. The image shows several objects, each with a number on it. "
                            "Your task is to extract all numbers from the image, add them up, and output only the total sum as a number."
                        )

                # Capture the base screenshot for this round.
                try:
                    with tempfile.NamedTemporaryFile(
                        suffix=".png", delete=False
                    ) as tmp:
                        screenshot_path = tmp.name
                    iframe_html = self.driver.find_element(By.TAG_NAME, "html")
                    iframe_html.screenshot(screenshot_path)
                    with Image.open(screenshot_path) as img:
                        w, h = img.size
                        cropped = img.crop((0, int(h * 0.1), w, int(h * 0.5)))
                except Exception as e:
                    logging.error(
                        f"Failed to capture or crop screenshot in cycle {cycle} round {round_num}: {e}"
                    )
                    if os.path.exists(screenshot_path):
                        os.unlink(screenshot_path)
                    continue

                # Extract and process the left image (remains constant during the round)
                left_img = cropped.crop((0, 0, cropped.width // 2, cropped.height))
                left_img = remove_white_border(left_img)
                # Save permanent copy of left image
                left_perm_path = os.path.join(
                    data_dir,
                    f"{round_start_time}_cycle{cycle}_round{round_num}_left.jpg",
                )
                left_img.save(left_perm_path)
                with tempfile.NamedTemporaryFile(
                    suffix=".jpg", delete=False
                ) as left_temp:
                    left_path = left_temp.name
                    left_img.save(left_path)

                left_response = groq_handler.get_vlm_response(
                    left_prompt, left_path, model=self.groq_model
                )
                if left_response is None:
                    logging.error(
                        f"No response from Groq VLM API for left query in cycle {cycle} round {round_num}."
                    )
                    left_value = ""
                else:
                    if task_type == "seats":
                        left_match = re.search(r"([A-Za-z]-\d{1,2})", left_response)
                        left_value = left_match.group(1) if left_match else ""
                        if not left_match:
                            logging.error(
                                f"Failed to extract letter and number from left VLM response in cycle {cycle} round {round_num}."
                            )
                    else:
                        left_numbers = re.findall(r"\d+", left_response)
                        left_value = int(left_numbers[-1]) if left_numbers else ""
                        if not left_numbers:
                            logging.error(
                                f"Failed to extract number from left VLM response in cycle {cycle} round {round_num}."
                            )

                # Fixed attempts for the right image.
                for attempt in range(1, max_attempts + 1):
                    logging.info(f"Cycle {cycle} round {round_num} attempt {attempt}")
                    if attempt == 1:
                        right_img = cropped.crop(
                            (cropped.width // 2, 0, cropped.width, cropped.height)
                        )
                    else:
                        right_screenshot_path = None
                        try:
                            with tempfile.NamedTemporaryFile(
                                suffix=".png", delete=False
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
                                f"Failed to capture right screenshot on cycle {cycle} round {round_num} attempt {attempt}: {e}"
                            )
                            if right_screenshot_path and os.path.exists(
                                right_screenshot_path
                            ):
                                os.unlink(right_screenshot_path)
                            continue

                    right_img = remove_white_border(right_img)
                    # Save permanent copy of right image
                    right_perm_path = os.path.join(
                        data_dir,
                        f"{round_start_time}_cycle{cycle}_round{round_num}_attempt{attempt}_right.jpg",
                    )
                    right_img.save(right_perm_path)
                    with tempfile.NamedTemporaryFile(
                        suffix=".jpg", delete=False
                    ) as right_temp:
                        right_path = right_temp.name
                        right_img.save(right_path)

                    right_response = groq_handler.get_vlm_response(
                        right_prompt, right_path, model=self.groq_right_model
                    )
                    os.unlink(right_path)
                    if right_response is None:
                        logging.error(
                            f"No response from Groq VLM API for right query in cycle {cycle} round {round_num} attempt {attempt}."
                        )
                        extracted_right = ""
                    else:
                        if task_type == "seats":
                            right_match = re.search(
                                r"([A-Za-z]-\d{1,2})", right_response
                            )
                            extracted_right = (
                                right_match.group(1) if right_match else ""
                            )
                            if not right_match:
                                logging.error(
                                    f"Failed to extract letter and number from right VLM response in cycle {cycle} round {round_num} attempt {attempt}."
                                )
                        elif task_type == "sum":
                            nums = re.findall(r"\d+", right_response)
                            if nums:
                                extracted_right = sum(map(int, nums))
                            else:
                                extracted_right = ""
                                logging.error(
                                    f"Failed to extract numbers from right VLM response for sum task in cycle {cycle} round {round_num} attempt {attempt}."
                                )
                        else:
                            nums = re.findall(r"\d+", right_response)
                            extracted_right = int(nums[-1]) if nums else ""
                            if not nums:
                                logging.error(
                                    f"Failed to extract number from right VLM response in cycle {cycle} round {round_num} attempt {attempt}."
                                )
                    logging.info(
                        f"Cycle {cycle} round {round_num} attempt {attempt} right response: {right_response} (extracted {extracted_right})"
                    )
                    self.log_run(
                        round_start_time,
                        left_perm_path,
                        right_perm_path,
                        left_value,
                        extracted_right,
                        self.groq_model,
                        self.groq_right_model,
                        "",
                        "",
                        task_type,
                    )
                    # If not the last attempt, click 'Next' to load a new right image.
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
                                f"Failed to click 'Next' button in cycle {cycle} round {round_num} attempt {attempt}: {e}"
                            )
                            break

                # After fixed attempts, click submit unconditionally.
                try:
                    submit_button = self.wait_for_element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Submit')]"),
                        timeout=10,
                    )
                    submit_button.click()
                    time.sleep(5)  # Wait for captcha processing
                except Exception as e:
                    logging.error(
                        f"Failed to click 'Submit' button in cycle {cycle} round {round_num}: {e}"
                    )

                # Cleanup round-specific temporary files.
                if os.path.exists(screenshot_path):
                    os.unlink(screenshot_path)
                if os.path.exists(left_path):
                    os.unlink(left_path)

            # After the first cycle, wait for the "Try again" button and click it.
            if cycle == 1:
                logging.info("Waiting 10 seconds for 'Try again' button...")
                time.sleep(10)
                try:
                    try_again_button = self.wait_for_element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Try again')]"),
                        timeout=10,
                    )
                    try_again_button.click()
                    logging.info("'Try again' button clicked. Starting next cycle.")
                except Exception as e:
                    logging.error(
                        f"Failed to click 'Try again' button after cycle {cycle}: {e}"
                    )
                    return False

        logging.info("Completed both cycles of data collection. Exiting.")
        return True

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
