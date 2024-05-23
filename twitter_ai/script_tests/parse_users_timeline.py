import os
import time
import logging
import traceback
from twitter.scraper import Scraper
from utils.db_utils import (
    get_db_connection,
    insert_tweets,
    update_user_tweets_status,
)
from utils.twitter_utils import get_twitter_scraper
from utils.common_utils import save_tweets_to_db, fetch_tweets_for_users

# Initialize colorama
from colorama import init, Fore, Style

init()

# Set up logging for verbosity
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_users_to_parse(db, limit=5):
    query = """
        SELECT rest_id, username FROM users
        WHERE tweets_parsed = FALSE
        LIMIT %s;
    """
    return db.run_query(query, (limit,))


def main():
    scraper = get_twitter_scraper()
    with get_db_connection() as db:
        try:
            while True:
                users_to_parse = get_users_to_parse(db)
                if not users_to_parse:
                    logging.info("No users found to parse. Waiting for the next cycle.")
                    time.sleep(60)
                    continue

                user_ids = [user[0] for user in users_to_parse]
                logging.info(f"Processing users: {user_ids}")

                tweets = fetch_tweets_for_users(scraper, user_ids)
                if tweets is None:
                    logging.error(
                        f"{Fore.RED}Failed to fetch tweets for users: {user_ids}. Skipping these users.{Style.RESET_ALL}"
                    )
                    continue

                save_tweets_to_db(db, tweets)
                update_user_tweets_status(db, user_ids)

                logging.info("Cycle complete. Waiting for the next cycle.")
                time.sleep(60)

        except Exception as e:
            logging.error(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")
            logging.error(f"{Fore.RED}{traceback.format_exc()}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
