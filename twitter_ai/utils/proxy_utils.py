from pathlib import Path
import logging
import tempfile
import os
import string
import requests
from utils.db_utils import get_db_connection

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ProxyManager:
    def __init__(self):
        self._init_proxies_from_csv()

    def _init_proxies_from_csv(self):
        csv_path = Path("proxies.csv")
        if csv_path.exists():
            with open(csv_path, "r") as f:
                proxies = []
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split(":")
                        if len(parts) == 4:
                            domain, port, user, password = parts
                            proxy = f"{user}:{password}@{domain}:{port}"
                            proxies.append(proxy)
                if proxies:
                    self.add_proxies(proxies, "smartproxy-residential-rotating")

    def get_next_proxy(self, source=None):
        with get_db_connection() as db:
            source_condition = "AND source = %s" if source else ""
            query = f"""
                UPDATE proxies
                SET last_used = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM proxies
                    WHERE status = 'good' 
                    {source_condition}
                    ORDER BY last_used NULLS FIRST
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING address, x_guest_token;
            """
            params = [source] if source else []
            result = db.run_query(query, params) if params else db.run_query(query)
            return result[0] if result else None

    def mark_bad(self, address, error=None):
        with get_db_connection() as db:
            query = """
                UPDATE proxies 
                SET status = 'bad', 
                    last_checked = CURRENT_TIMESTAMP, 
                    error = %s,
                    attempts = attempts + 1
                WHERE address = %s;
            """
            db.run_query(query, (error, address))

    def add_proxies(self, proxies, source):
        with get_db_connection() as db:
            query = """
                INSERT INTO proxies (address, source)
                VALUES (%s, %s)
                ON CONFLICT (address) DO NOTHING;
            """
            params = [(proxy, source) for proxy in proxies]
            db.run_insert_query(query, params)

    def update_proxy_token(self, address, token):
        with get_db_connection() as db:
            query = """
                UPDATE proxies
                SET x_guest_token = %s, 
                    status = 'good', 
                    last_checked = CURRENT_TIMESTAMP,
                    attempts = 0
                WHERE address = %s;
            """
            db.run_query(query, (token, address))


PROXY_MANAGER = ProxyManager()


def test_proxy(proxy: str) -> bool:
    try:
        if "@" in proxy:
            auth_part, host_port = proxy.split("@", 1)
            username, password = auth_part.split(":", 1)
            proxies = {
                "http": f"http://{username}:{password}@{host_port}",
                "https": f"http://{username}:{password}@{host_port}",
            }
        else:
            proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        response = requests.get(
            "https://api.x.com/1.1/hashflags.json", proxies=proxies, timeout=1
        )
        elapsed = response.elapsed.total_seconds()
        if response.status_code == 200 and elapsed < 1:
            return True
        else:
            logging.warning(
                f"Proxy {proxy} responded in {elapsed:.2f}s which is too slow."
            )
            return False
    except Exception:
        return False


def get_working_proxy(source="smartproxy-residential-rotating") -> str:
    while True:
        proxy_info = PROXY_MANAGER.get_next_proxy(source)
        if not proxy_info:
            return None
        proxy = proxy_info[0]
        if test_proxy(proxy):
            logging.info(f"Found working proxy: {proxy}")
            return proxy
        logging.warning(f"Proxy {proxy} failed, trying next...")


def create_proxy_auth_extension(
    proxy_host: str,
    proxy_port: str,
    proxy_username: str,
    proxy_password: str,
    scheme="http",
) -> str:
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
        "webRequestBlocking",
        "<all_urls>"
    ],
    "background": {
        "scripts": ["background.js"],
        "persistent": true
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
    ["blocking"]
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


def apply_proxy_to_chrome_options(options, proxy: str, scheme="http"):
    if "@" in proxy:
        auth_part, host_port = proxy.split("@", 1)
        username, password = auth_part.split(":", 1)
        host, port = host_port.split(":", 1)
        extension_dir = create_proxy_auth_extension(
            host, port, username, password, scheme
        )
        options.add_argument(f"--load-extension={extension_dir}")
        options.add_argument(f"--disable-extensions-except={extension_dir}")
    else:
        options.add_argument(f"--proxy-server={scheme}://{proxy}")


def build_requests_proxies(proxy: str):
    if proxy:
        return {"https": f"http://{proxy}"}
    return None
