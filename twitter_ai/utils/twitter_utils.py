# twitter_utils.py

from twitter.scraper import Scraper
from twitter.account import Account
from twitter.util import init_session

try:
    from utils.config import Config
except:
    import sys
    import os

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.config import Config

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
# twitter_utils.py additions
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


# Update in twitter_utils.py
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.last_refresh = datetime(1970, 1, 1)
        self.current_index = 0
        self.refresh_interval = timedelta(minutes=5)
        self.fallback_proxies = [
            "45.61.187.67:4007",
            "193.122.71.60:3128",
            "45.61.187.3:4010",
            "45.61.188.8:4026",
        ]

    # twitter_utils.py (ProxyManager refresh_proxies method update)
    def refresh_proxies(self):
        try:
            # Primary source parsing fix
            response = requests.get("https://www.sslproxies.org/", timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            # Find table with IP/Port headers
            table = None
            for t in soup.find_all("table"):
                headers = [th.get_text(strip=True) for th in t.find_all("th")]
                if "IP Address" in headers and "Port" in headers:
                    table = t
                    break

            if not table:
                raise ValueError("Proxy table not found in HTML")

            rows = table.tbody.find_all("tr")[:20] if table.tbody else []
            new_proxies = [
                f"{row.find_all('td')[0].text}:{row.find_all('td')[1].text}"
                for row in rows
                if len(row.find_all("td")) >= 2
            ]

            if not new_proxies:
                raise ValueError("No proxies parsed from primary source")

            self.proxies = new_proxies
            self.last_refresh = datetime.now()
            logging.info(f"Refreshed proxy list, got {len(self.proxies)} proxies")

        except Exception as e:
            # Maintain existing fallback logic
            logging.error(f"Primary proxy refresh failed: {str(e)}")
            try:
                response = requests.get("https://free-proxy-list.net/", timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                # Rest of fallback logic remains unchanged...
                table = soup.find("div", {"class": "table-responsive"})

                proxies = []
                for row in table.find_all("tr")[1:21]:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        proxies.append(f"{cells[0].text}:{cells[1].text}")

                if proxies:
                    self.proxies = proxies
                    self.last_refresh = datetime.now()
                    logging.info(f"Used secondary source, got {len(proxies)} proxies")
                else:
                    raise ValueError("No proxies from secondary source")

            except Exception as fallback_e:
                logging.error(f"Secondary proxy refresh failed: {str(fallback_e)}")
                # Use hardcoded fallbacks if all else fails
                self.proxies = self.fallback_proxies
                logging.warning("Using fallback proxy list")

    def get_next_proxy(self):
        if datetime.now() - self.last_refresh > self.refresh_interval:
            self.refresh_proxies()

        if not self.proxies:
            return None

        for _ in range(len(self.proxies)):
            self.current_index = (self.current_index + 1) % len(self.proxies)
            proxy = self.proxies[self.current_index]
            if self.check_proxy(proxy):
                return proxy
        return None

    def check_proxy(self, proxy):
        try:
            test_url = "https://httpbin.org/ip"
            session = requests.Session()
            session.proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            response = session.get(test_url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False


PROXY_MANAGER = ProxyManager()


# Updated get_twitter_scraper in twitter_utils.py
def get_twitter_scraper(account=None, force_login=False):
    proxy = PROXY_MANAGER.get_next_proxy()
    try:
        session = init_session()
        if proxy:
            session.proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}",
            }
            logging.info(f"Using proxy: {proxy}")

        if account and force_login:
            raise Exception("Forced login to refresh cookies.")

        if account:
            scraper = Scraper(cookies=f"{account['login']}.cookies", session=session)
            logging.info("Loaded scraper from cookies")
        else:
            scraper = Scraper(session=session)
            logging.info("Initialized guest session")

    except Exception as e:
        logging.error(f"Failed to load scraper: {e}")
        if account:
            scraper = Scraper(
                account["email"], account["login"], account["password"], session=session
            )
            scraper.save_cookies()
        else:
            scraper = Scraper(session=session)

    return scraper


def get_twitter_account(account, force_login=False):
    try:
        if force_login:
            raise Exception("Forced login to refresh cookies.")
        twitter_account = Account(cookies=f"{account['login']}.cookies")
        logging.info("Loaded account from cookies.")
    except Exception as e:
        logging.error(f"Failed to load account from cookies: {e}")
        twitter_account = Account(
            account["email"], account["login"], account["password"]
        )
        twitter_account.save_cookies()
        logging.info("Logged in and saved account cookies.")
    return twitter_account


def choose_account(account_name):
    accounts = Config.get_twitter_accounts()
    account = next((acc for acc in accounts if acc["login"] == account_name), None)
    if not account:
        logging.error(f"Account with name {account_name} not found.")
        return None
    return account


if __name__ == "__main__":
    scraper = get_twitter_scraper(choose_account(""), force_login=True)
    # tweets = scraper.tweets_details(
    #     [1795999224145772674, 1795973191325585733], limit=40
    # )
    # print(tweets)
