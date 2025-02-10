from twitter.scraper import Scraper
from twitter.account import Account
import logging
import sys
import os
from httpx import Client
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_db_connection
from utils.config import Config
from utils.proxy_utils import PROXY_MANAGER

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_twitter_scraper(account=None, force_login=False):
    attempt = 0
    while True:
        proxy_info = PROXY_MANAGER.get_next_proxy()
        if not proxy_info:
            time.sleep(10)
            raise RuntimeError("No proxies available")

        proxy, guest_token = proxy_info
        attempt += 1
        session = None
        proxies = {
            "http://": f"http://{proxy}",
            "https://": f"http://{proxy}",
        }
        try:
            session = Client(
                headers={
                    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "x-guest-token": guest_token,
                },
                proxies=proxies,
                verify=False,
                timeout=10,
            )

            if account:
                if force_login or not os.path.exists(f"{account['login']}.cookies"):
                    scraper = Scraper(
                        account["email"],
                        account["login"],
                        account["password"],
                        session=session,
                        proxies=proxies,
                    )
                    scraper.save_cookies()
                else:
                    scraper = Scraper(
                        cookies=f"{account['login']}.cookies",
                        session=session,
                        proxies=proxies,
                    )
            else:
                scraper = Scraper(session=session, proxies=proxies)

            logging.info(f"Connected via proxy: {proxy}")
            return scraper

        except Exception as e:
            PROXY_MANAGER.mark_bad(proxy, str(e))
            logging.error(f"Attempt {attempt} failed: {str(e)}")
            if session:
                session.close()


def get_twitter_account(account):
    for attempt in range(3):
        proxy = None
        try:
            proxy = PROXY_MANAGER.get_next_proxy()
            session = init_session()  # Assuming init_session is defined elsewhere
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
            error_msg = str(e)
            logging.error(f"Account auth attempt {attempt+1} failed: {error_msg}")
            if proxy:
                PROXY_MANAGER.mark_bad(proxy, error_msg)
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
