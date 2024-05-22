import logging
from colorama import init, Fore, Style
import time

# common_utils.py

from utils.twitter_utils import extract_users_and_ids
from utils.db_utils import (
    insert_tweet,
    insert_users_bulk,
    insert_user_recommendations,
    update_user_recommendations_status,
)


def process_and_insert_users(db, scraper, user_ids):
    # Fetch user data from Twitter API
    users_data = scraper.users_by_ids(user_ids)

    if not users_data:
        print("No user data fetched from Twitter.")
        return 0

    # Extract user data
    users = []
    for user_data in users_data[0]["data"]["users"]:
        try:
            entries = user_data["result"]
            users.append(entries)
        except KeyError as e:
            print(f"KeyError while extracting users: {e}")
            continue

    if not users:
        print("No valid user data extracted.")
        return 0

    # Insert user data into the database
    insert_users_query, users_params = insert_users_bulk(users)
    inserted_users = db.run_batch_query(insert_users_query, users_params)

    # Return the number of inserted users
    return inserted_users


def save_users_recommendations_by_ids(db, scraper, user_ids):
    recommended_users = scraper.recommended_users(user_ids)
    new_users_count = 0

    for user_chunk, user_id in zip(recommended_users, user_ids):
        entries = user_chunk["data"]["connect_tab_timeline"]["timeline"][
            "instructions"
        ][2]["entries"]
        users, rest_ids = extract_users_and_ids(entries)

        insert_users_query, users_params = insert_users_bulk(users)
        inserted_users = db.run_batch_query(insert_users_query, users_params)

        if inserted_users:
            new_users_count += len(inserted_users)

        insert_recommendations_query, recommendations_params = (
            insert_user_recommendations(user_id, rest_ids)
        )
        db.run_batch_query(insert_recommendations_query, recommendations_params)

        update_status_query, status_params = update_user_recommendations_status(user_id)
        db.run_query(update_status_query, status_params)

    return new_users_count


def save_tweets_to_db(db, all_pages):
    for page in all_pages:
        if not isinstance(page, list):
            page = [page]
        for tweets in page:
            try:
                timeline_v2 = tweets["data"]["user"]["result"]["timeline_v2"]
            except KeyError as e:
                logging.error(
                    f"{Fore.RED}KeyError: {e} - 'timeline_v2' data is missing{Style.RESET_ALL}"
                )
                continue

            try:
                instructions = timeline_v2["timeline"]["instructions"]
            except KeyError as e:
                logging.error(
                    f"{Fore.RED}KeyError: {e} - 'instructions' data is missing{Style.RESET_ALL}"
                )
                continue

            for instruction in instructions:
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
                            except Exception as e:
                                logging.error(
                                    f"{Fore.RED}Unexpected error: {e} - tweet data: {entry}{Style.RESET_ALL}"
                                )


def fetch_tweets_for_users(
    scraper, user_ids, limit_pages=1, max_retries=8, backoff_factor=16
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
