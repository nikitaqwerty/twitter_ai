from collections import deque
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
        self.proxies = deque()
        self.last_refresh = datetime(1970, 1, 1)
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

            # Merge new proxies with existing list
            existing_set = set(self.proxies)
            added = 0
            for proxy in new_proxies:
                if proxy not in existing_set:
                    self.proxies.append(proxy)
                    added += 1

            if added > 0:
                self.last_refresh = datetime.now()
                logging.info(f"Added {added} new proxies. Total: {len(self.proxies)}")
            else:
                logging.info("No new proxies found in this refresh")

        finally:
            self.proxy_lock = False

    def get_next_proxy(self):
        if datetime.now() - self.last_refresh > self.refresh_interval:
            self.refresh_proxies()

        while True:
            if not self.proxies:
                raise RuntimeError("No proxies available")

            proxy = self.proxies.popleft()

            if proxy in self.bad_proxies:
                continue

            return proxy

    def requeue_proxy(self, proxy):
        """Re-add working proxy to end of queue"""
        self.proxies.append(proxy)


PROXY_MANAGER = ProxyManager()


def get_twitter_scraper(account=None, force_login=False):
    attempt = 0
    while True:
        attempt += 1
        proxy = None
        session = None
        try:
            proxy = PROXY_MANAGER.get_next_proxy()
            session = init_session(proxy=proxy)
            session.verify = False
            session.proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}",
            }
            session.timeout = 5

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
            PROXY_MANAGER.requeue_proxy(proxy)
            return scraper

        except Exception as e:
            logging.error(f"Connection attempt {attempt} failed: {str(e)}")
            if proxy:
                PROXY_MANAGER.bad_proxies.add(proxy)
            if session:
                session.close()


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
            PROXY_MANAGER.requeue_proxy(proxy)
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
