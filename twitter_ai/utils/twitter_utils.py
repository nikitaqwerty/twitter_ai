from twitter.scraper import Scraper
from utils.config import Config  # Import the Config class


def get_twitter_scraper():
    # Use Config attributes instead of os.getenv
    email = Config.TWITTER_EMAIL
    login = Config.TWITTER_LOGIN
    password = Config.TWITTER_PASSWORD
    return Scraper(email, login, password)


def extract_rest_ids(entries):
    if not isinstance(entries, list):
        entries = [entries]

        # entries[0]['data']['connect_tab_timeline']['timeline']['instructions'][2]['entries'][2]['content']['items'][0]
    return [
        item["item"]["itemContent"]["user_results"]["result"]["rest_id"]
        for entry in entries
        for item in entry["content"]["items"]
        if "socialContext" not in item["item"]["itemContent"]
    ]


def extract_users(entries):
    if not isinstance(entries, list):
        entries = [entries]
    return [
        item["item"]["itemContent"]["user_results"]["result"]
        for entry in entries
        for item in entry["content"]["items"]
        if "socialContext" not in item["item"]["itemContent"]
    ]
