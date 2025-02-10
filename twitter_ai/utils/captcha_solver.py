import time
import socket
import logging
import os
import tempfile
from typing import Optional
from anticaptchaofficial.funcaptchaproxyless import funcaptchaProxyless
from anticaptchaofficial.funcaptchaproxyon import funcaptchaProxyon


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
            from twitter_ai.llm.llm_api import GroqAPIHandler
        except ImportError as e:
            logging.error("Failed to import GroqAPIHandler: " + str(e))
            return False

        groq_handler = GroqAPIHandler(api_key=self.config.GROQ_API_KEY)
        max_attempts = 5
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            logging.info(f"VLM captcha attempt {attempt}")

            # Take a screenshot of the current iframe and save to a temporary file.
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                screenshot_path = tmp.name
            try:
                self.driver.save_screenshot(screenshot_path)
            except Exception as e:
                logging.error(f"Failed to take screenshot: {e}")
                os.unlink(screenshot_path)
                return False

            prompt = "Is the task in screenshot solved correctly?"
            response = groq_handler.get_vlm_response(prompt, screenshot_path)
            os.unlink(screenshot_path)

            if response is None:
                logging.error("No response from Groq VLM API.")
                return False

            logging.info(f"Groq VLM response: {response}")
            if "yes" in response.lower():
                try:
                    submit_button = self.driver.find_element(
                        By.XPATH, "//button[contains(text(), 'Submit')]"
                    )
                    submit_button.click()
                    logging.info("Clicked 'Submit' button.")
                    return True
                except Exception as e:
                    logging.error(f"Failed to click 'Submit' button: {e}")
                    return False
            else:
                try:
                    next_button = self.driver.find_element(
                        By.XPATH, "//a[aria-label='Navigate to next image')]"
                    )
                    next_button.click()
                    logging.info("Clicked 'Next' button.")
                    time.sleep(3)
                except Exception as e:
                    logging.error(f"Failed to click 'Next' button: {e}")
                    return False

        logging.error("Exceeded maximum attempts for VLM captcha solving.")
        return False
