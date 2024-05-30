import logging
from colorama import Fore, Style
import time
import re

# common_utils.py

from utils.db_utils import (
    insert_tweets,
    insert_users,
    insert_user_recommendations,
    update_user_recommendations_status,
)


def process_and_insert_users(db, scraper, user_ids):
    # Fetch user data from Twitter API
    if not isinstance(user_ids, list):
        user_ids = [user_ids]
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
    inserted_users = insert_users(db, users)

    # Return the number of inserted users
    return inserted_users


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


def save_users_recommendations_by_ids(db, scraper, user_ids):
    recommended_users = scraper.recommended_users(user_ids)
    new_users_count = 0

    for user_chunk, user_id in zip(recommended_users, user_ids):
        entries = user_chunk["data"]["connect_tab_timeline"]["timeline"][
            "instructions"
        ][2]["entries"]
        users, rest_ids = extract_users_and_ids(entries)

        inserted_users = insert_users(db, users)

        if inserted_users:
            new_users_count += len(inserted_users)

        inserted_recommendations_count = insert_user_recommendations(
            db, user_id, rest_ids
        )

        update_user_recommendations_status(db, user_id)

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
                                    insert_tweets(db, tweet_results)
                                elif "tweet" in tweet_results:
                                    insert_tweets(db, tweet_results["tweet"])
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
            # Check if the tweets contain error messages indicating rate limit exceeded
            if any(
                "errors" in tweet
                and any(error["code"] == 88 for error in tweet["errors"])
                for tweet in tweets
            ):
                tweets = None
        if tweets:
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


def remove_https_links(input_str):
    """
    This function takes an input string and removes all substrings that are https:// links.

    Args:
    input_str (str): The input string containing https:// links.

    Returns:
    str: The input string with all https:// links removed.
    """
    # Regex pattern to match https:// links
    pattern = r"https:\/\/\S+"

    # Substitute all https:// links with an empty string
    result = re.sub(pattern, "", input_str)

    return result
