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

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_twitter_scraper(force_login=False):
    try:
        if force_login:
            raise Exception("Forced login to refresh cookies.")
        scraper = Scraper(cookies="rndm_world.cookies")
        logging.info("Loaded scraper from cookies.")
    except Exception as e:
        logging.error(f"Failed to load scraper from cookies: {e}")
        # If an error occurs, login using credentials
        email = Config.TWITTER_EMAIL
        login = Config.TWITTER_LOGIN
        password = Config.TWITTER_PASSWORD
        scraper = Scraper(email, login, password)
        scraper.save_cookies()
        logging.info("Logged in and saved scraper cookies.")
    return scraper


def get_twitter_account(force_login=False):
    try:
        if force_login:
            raise Exception("Forced login to refresh cookies.")
        account = Account(cookies="rndm_world.cookies")
        logging.info("Loaded account from cookies.")
    except Exception as e:
        logging.error(f"Failed to load account from cookies: {e}")
        email = Config.TWITTER_EMAIL
        login = Config.TWITTER_LOGIN
        password = Config.TWITTER_PASSWORD
        account = Account(email, login, password)
        account.save_cookies()
        logging.info("Logged in and saved account cookies.")
    return account


def extract_users_and_ids(entries):
    """
    Extracts users and their rest IDs from the given entries, filtering out users with empty rest IDs.

    Parameters:
    entries (list): A list of entries containing user data.

    Returns:
    tuple: A tuple containing two lists - one with user details and one with rest IDs.
    """
    if not isinstance(entries, list):
        entries = [entries]

    users = []
    rest_ids = []

    for entry in entries:
        for item in entry.get("content", {}).get("items", []):
            if "socialContext" not in item.get("item", {}).get("itemContent", {}):
                try:
                    user = item["item"]["itemContent"]["user_results"]["result"]
                    rest_id = user.get("rest_id", "")
                    if rest_id:  # Only append if rest_id is not empty
                        users.append(user)
                        rest_ids.append(rest_id)
                except KeyError as e:
                    logging.error(f"KeyError: {e} - item: {item}")

    return users, rest_ids


if __name__ == "__main__":
    acc = get_twitter_account()
    resp = acc.tweet("omg")
    print(resp)
    # tweet_results = resp['data']['create_tweet']['tweet_results']['result']
    # id = tweet_results['rest_id']
    # print(resp)
