from twitter.scraper import Scraper
from utils.config import Config  # Import the Config class

import logging

# Set up logging
logging.basicConfig(
    level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_twitter_scraper():
    # Use Config attributes instead of os.getenv
    email = Config.TWITTER_EMAIL
    login = Config.TWITTER_LOGIN
    password = Config.TWITTER_PASSWORD
    return Scraper(email, login, password)


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


# Example usage:
# entries = [...]  # Assuming entries is a list of entries
# users, rest_ids = extract_users_and_ids(entries)
