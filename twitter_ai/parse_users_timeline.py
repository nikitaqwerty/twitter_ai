import os
import time
import logging
import traceback
from twitter.scraper import Scraper
from utils.db_utils import (
    get_db_connection,
    insert_tweet,
    update_user_tweets_status,
    create_all_tables,
)
from utils.twitter_utils import get_twitter_scraper

# Initialize colorama
from colorama import init, Fore, Style

init()

# Set up logging for verbosity
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_users_to_parse(db, limit=1):
    query = """
        SELECT rest_id, username FROM users
        WHERE tweets_parsed = FALSE
        LIMIT %s;
    """
    return db.run_query(query, (limit,))


def fetch_tweets_for_users(scraper, user_ids, max_retries=5, backoff_factor=1):
    retries = 0
    while retries < max_retries:
        tweets = scraper.tweets(user_ids, limit=20)
        if tweets and all(isinstance(tweet, dict) for tweet in tweets):
            return tweets
        retries += 1
        wait_time = backoff_factor * (2**retries)
        logging.error(
            f"{Fore.RED}Error fetching tweets for users {user_ids}. Retrying in {wait_time} seconds...{Style.RESET_ALL}"
        )
        time.sleep(wait_time)
    logging.error(
        f"{Fore.RED}Max retries reached for users: {user_ids}. Skipping...{Style.RESET_ALL}"
    )
    return None


def save_tweets_to_db(db, all_pages):
    for page in all_pages:
        if not isinstance(page, list):
            page = [page]
        for tweets in page:
            for instruction in tweets["data"]["user"]["result"]["timeline_v2"][
                "timeline"
            ]["instructions"]:
                if instruction["type"] == "TimelineAddEntries":
                    for entry in instruction["entries"]:
                        if entry["entryId"].startswith("tweet"):
                            try:
                                tweet_results = entry["content"]["itemContent"][
                                    "tweet_results"
                                ]["result"]
                                if "rest_id" in tweet_results:
                                    insert_tweet(db, tweet_results)
                                elif "tweet" in tweet_results:
                                    insert_tweet(db, tweet_results["tweet"])
                                else:
                                    logging.error(
                                        f"{Fore.RED}rest_id not in tweet data: {entry}{Style.RESET_ALL}"
                                    )
                            except KeyError as e:
                                logging.error(
                                    f"{Fore.RED}KeyError: {e} - tweet data: {entry}{Style.RESET_ALL}"
                                )


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
