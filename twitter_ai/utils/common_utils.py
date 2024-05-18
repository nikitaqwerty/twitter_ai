import logging
from utils.db_utils import insert_tweet
from colorama import init, Fore, Style


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


def fetch_tweets_for_users(
    scraper, user_ids, limit_pages=1, max_retries=5, backoff_factor=1
):
    retries = 0
    while retries < max_retries:
        tweets = scraper.tweets(user_ids, limit=20 * limit_pages)
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
