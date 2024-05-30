from twitter.scraper import Scraper
from twitter.account import Account

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


def get_twitter_scraper(account, force_login=False):
    try:
        if force_login:
            raise Exception("Forced login to refresh cookies.")
        scraper = Scraper(cookies=f"{account['login']}.cookies")
        logging.info("Loaded scraper from cookies.")
    except Exception as e:
        logging.error(f"Failed to load scraper from cookies: {e}")
        scraper = Scraper(account["email"], account["login"], account["password"])
        scraper.save_cookies()
        logging.info("Logged in and saved scraper cookies.")
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
    scraper = get_twitter_scraper(choose_account("986sol"))
    tweets = scraper.tweets_details(
        [1795999224145772674, 1795973191325585733], limit=40
    )
    print(tweets)
