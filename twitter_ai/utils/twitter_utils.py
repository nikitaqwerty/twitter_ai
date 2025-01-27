from twitter.scraper import Scraper
from twitter.account import Account
from twitter.util import init_session
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.last_refresh = datetime(1970, 1, 1)
        self.current_index = 0
        self.refresh_interval = timedelta(minutes=5)
        self.bad_proxies = set()
        self.proxy_lock = False

    def refresh_proxies(self):
        if self.proxy_lock:
            return
        self.proxy_lock = True

        try:
            sources = [
                (
                    "https://www.sslproxies.org/",
                    lambda soup: next(
                        (
                            t
                            for t in soup.find_all("table")
                            if "IP Address"
                            in [th.get_text(strip=True) for th in t.find_all("th")]
                            and "Port"
                            in [th.get_text(strip=True) for th in t.find_all("th")]
                        ),
                        None,
                    ),
                ),
                (
                    "https://free-proxy-list.net/",
                    lambda soup: soup.find("div", {"class": "table-responsive"}),
                ),
            ]

            new_proxies = []
            for url, table_finder in sources:
                try:
                    response = requests.get(url, timeout=15)
                    soup = BeautifulSoup(response.text, "html.parser")
                    table = table_finder(soup)

                    if table:
                        rows = table.tbody.find_all("tr") if table.tbody else []
                        for row in rows:
                            cells = row.find_all("td")
                            if len(cells) >= 2:
                                ip = cells[0].text.strip()
                                port = cells[1].text.strip()
                                proxy = f"{ip}:{port}"
                                if proxy not in self.bad_proxies:
                                    new_proxies.append(proxy)
                    else:
                        logging.warning(f"No valid table found at {url}")

                except Exception as e:
                    logging.error(f"Failed to scrape {url}: {str(e)}")

            if new_proxies:
                self.proxies = list(set(new_proxies))
                self.last_refresh = datetime.now()
                logging.info(f"Refreshed proxies: {len(self.proxies)} available")
            else:
                logging.warning("No new proxies found, keeping existing list")

        finally:
            self.proxy_lock = False

    def get_next_proxy(self):
        if datetime.now() - self.last_refresh > self.refresh_interval:
            self.refresh_proxies()

        while True:
            if not self.proxies:
                raise RuntimeError("No proxies available")

            self.current_index = (self.current_index + 1) % len(self.proxies)
            proxy = self.proxies[self.current_index]

            if proxy in self.bad_proxies:
                continue

            return proxy  # Removed proxy validation check


PROXY_MANAGER = ProxyManager()


def get_twitter_scraper(account=None, force_login=False):
    attempt = 0
    while True:
        proxy = None  # Initialize here first
        session = None
        try:
            proxy = PROXY_MANAGER.get_next_proxy()
            session = init_session(proxy=proxy)
            session.verify = False  # Disable SSL verification
            session.proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}",
            }
            session.timeout = 10

            if account:
                if force_login or not os.path.exists(f"{account['login']}.cookies"):
                    scraper = Scraper(
                        account["email"],
                        account["login"],
                        account["password"],
                        session=session,
                    )
                    scraper.save_cookies()
                else:
                    scraper = Scraper(
                        cookies=f"{account['login']}.cookies", session=session
                    )
            else:
                scraper = Scraper(session=session)

            logging.info(f"Successfully connected via proxy: {proxy}")
            return scraper

        except Exception as e:
            logging.error(f"Connection attempt {attempt+1} failed: {str(e)}")
            if proxy:  # Now safely referenced
                PROXY_MANAGER.bad_proxies.add(proxy)
            if session:
                session.close()
            # if attempt == 2:
            #     raise RuntimeError(
            #         "Failed to establish proxy connection after 3 attempts"
            #     )


def get_twitter_account(account):
    for attempt in range(3):
        proxy = None
        try:
            proxy = PROXY_MANAGER.get_next_proxy()
            session = init_session()
            session.proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}",
            }

            account = Account(
                account["email"], account["login"], account["password"], session=session
            )
            account.save_cookies()
            logging.info(f"Authenticated account via proxy: {proxy}")
            return account
        except Exception as e:
            logging.error(f"Account auth attempt {attempt+1} failed: {str(e)}")
            if proxy:
                PROXY_MANAGER.bad_proxies.add(proxy)
            if attempt == 2:
                raise RuntimeError(
                    "Account authentication failed after 3 proxy attempts"
                )


def choose_account(account_name):
    accounts = Config.get_twitter_accounts()
    account = next((acc for acc in accounts if acc["login"] == account_name), None)
    if not account:
        logging.error(f"Account {account_name} not found in config")
        raise ValueError("Invalid account name")
    return account


if __name__ == "__main__":
    scraper = get_twitter_scraper()
