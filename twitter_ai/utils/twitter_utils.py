from twitter.scraper import Scraper
from twitter.account import Account
from twitter.util import init_session
import logging
import sys
import os
from utils.db_utils import get_db_connection

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ProxyManager:
    def __init__(self, db):
        self.db = db

    def get_next_proxy(self):
        query = """
            UPDATE proxies
            SET last_used = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id FROM proxies
                WHERE status = 'good'
                ORDER BY last_used NULLS FIRST
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING address;
        """
        result = self.db.run_query(query)
        return result[0][0] if result else None

    def mark_bad(self, address, error=None):
        query = """
            UPDATE proxies 
            SET status = 'bad', last_checked = CURRENT_TIMESTAMP, error = %s
            WHERE address = %s;
        """
        self.db.run_query(query, (error, address))

    def add_proxies(self, proxies, source):
        query = """
            INSERT INTO proxies (address, source)
            VALUES (%s, %s)
            ON CONFLICT (address) DO NOTHING;
        """
        params = [(proxy, source) for proxy in proxies]
        self.db.run_insert_query(query, params)


PROXY_MANAGER = ProxyManager(get_db_connection())


def get_twitter_scraper(account=None, force_login=False):
    attempt = 0
    while True:
        proxy = PROXY_MANAGER.get_next_proxy()
        if not proxy:
            raise RuntimeError("No proxies available")
        attempt += 1
        session = None
        try:
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
            return scraper

        except Exception as e:
            error_msg = str(e)
            PROXY_MANAGER.mark_bad(proxy, error_msg)
            logging.error(f"Connection attempt {attempt} failed: {error_msg}")
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
