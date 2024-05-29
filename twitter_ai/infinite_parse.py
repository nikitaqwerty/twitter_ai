# infinite_parse.py

import os
import time
import logging
import traceback
import random
from datetime import datetime, timedelta
from utils.db_utils import (
    get_db_connection,
    update_user_tweets_status,
    get_most_mentioned_new_users,
)
from utils.twitter_utils import get_twitter_scraper, choose_account
from utils.common_utils import (
    fetch_tweets_for_users,
    save_tweets_to_db,
    save_users_recommendations_by_ids,
    process_and_insert_users,
)
from utils.config import configure_logging, Config

configure_logging()

USERS_PER_BATCH = 5
PAGES_PER_USER = 1
CYCLE_DELAY = 60  # Base delay for the cycle in seconds
USERS_UPDATE_HOURS_DELAY = 48
COOKIE_UPDATE_INTERVAL = timedelta(hours=24)


def get_users_to_parse(db, hours=48, limit_users=2):
    query = """
        WITH selected_users AS (
            SELECT rest_id, username 
            FROM users
            WHERE (llm_check_score is null or llm_check_score > 5) 
            AND (tweets_parsed = FALSE OR tweets_parsed_last_timestamp < NOW() - INTERVAL '%s HOURS')
            AND status = 'idle'
            AND statuses_count > 20
            ORDER BY 
                CASE WHEN tweets_parsed = FALSE THEN 0 ELSE 1 END DESC,
                llm_check_score DESC NULLS LAST,
                tweets_parsed_last_timestamp ASC NULLS LAST,
                statuses_count DESC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE users
        SET status = 'in_progress'
        FROM selected_users
        WHERE users.rest_id = selected_users.rest_id
        RETURNING users.rest_id, users.username;
    """
    return db.run_query(query, (hours, limit_users))


def reset_status(db, user_ids):
    reset_status_query = """
        UPDATE users
        SET status = 'idle'
        WHERE rest_id IN ({});
    """.format(
        ", ".join(["%s"] * len(user_ids))
    )
    db.run_query(reset_status_query, tuple(user_ids))


def main(account_name):
    last_cookie_update_time = datetime.now()  # Initialize to the current time
    account = choose_account(account_name)
    scraper = get_twitter_scraper(account)

    with get_db_connection() as db:
        while True:
            try:
                current_time = datetime.now()
                # Check if 24 hours have passed since the last cookie update
                if current_time - last_cookie_update_time >= COOKIE_UPDATE_INTERVAL:
                    logging.info("24 hours have passed, updating cookies.")
                    scraper = get_twitter_scraper(account, force_login=False)
                    last_cookie_update_time = current_time

                users_to_parse = get_users_to_parse(
                    db, hours=USERS_UPDATE_HOURS_DELAY, limit_users=USERS_PER_BATCH
                )
                user_ids = [user[0] for user in users_to_parse]

                if user_ids and user_ids[0]:
                    logging.info(f"Processing users: {user_ids}")
                    tweets = fetch_tweets_for_users(
                        scraper, user_ids, limit_pages=PAGES_PER_USER
                    )
                    if tweets:
                        save_tweets_to_db(db, tweets)
                        update_user_tweets_status(db, user_ids)
                    else:
                        reset_status(db, user_ids)

                else:
                    logging.info(
                        f"No users to pull tweets. Adding new recommended users"
                    )
                    user_ids = [
                        user[0]
                        for user in get_most_mentioned_new_users(db, limit_users=200)
                    ]
                    new_users_count = process_and_insert_users(db, scraper, user_ids)
                    logging.info(
                        f"New users inserted by most mentioned algo {new_users_count}"
                    )

                logging.info("Cycle complete. Waiting for the next cycle.")
                random_sleep_time = random.uniform(CYCLE_DELAY * 0.5, CYCLE_DELAY * 1.5)
                time.sleep(random_sleep_time)
            except Exception as e:
                logging.error(f"An error occurred: {e}")
                logging.error(f"{traceback.format_exc()}")
                # Reset status to 'idle' for users that were being processed
                if user_ids:
                    reset_status(db, user_ids)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python infinite_parse.py <account_name>")
        sys.exit(1)
    account_name = sys.argv[1]
    main(account_name)
