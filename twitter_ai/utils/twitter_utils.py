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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ProxyManager:
    def __init__(self):
        pass  # No longer stores a database connection

    def get_next_proxy(self):
        with get_db_connection() as db:
            query = """
                UPDATE proxies
                SET last_used = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM proxies
                    WHERE status = 'good' AND x_guest_token IS NOT NULL
                    ORDER BY last_used NULLS FIRST
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING address, x_guest_token;
            """
            result = db.run_query(query)
            return result[0] if result else None

    def mark_bad(self, address, error=None):
        with get_db_connection() as db:
            query = """
                UPDATE proxies 
                SET status = 'bad', 
                    last_checked = CURRENT_TIMESTAMP, 
                    error = %s,
                    attempts = attempts + 1  -- Increment on failure
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
                    attempts = 0  -- Reset attempts on success
                WHERE address = %s;
            """
            db.run_query(query, (token, address))


PROXY_MANAGER = ProxyManager()


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

        try:
            session = Client(
                headers={
                    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "x-guest-token": guest_token,
                },
                proxies={
                    "http://": f"http://{proxy}",
                    "https://": f"http://{proxy}",
                },
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
                    )
                    scraper.save_cookies()
                else:
                    scraper = Scraper(
                        cookies=f"{account['login']}.cookies", session=session
                    )
            else:
                scraper = Scraper(session=session)

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
