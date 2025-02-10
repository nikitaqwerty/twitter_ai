import time
import socket
import logging
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
