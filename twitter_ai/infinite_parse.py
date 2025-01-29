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
    process_and_insert_users,
)
from utils.config import configure_logging, Config

configure_logging()

USERS_PER_BATCH = 100
PAGES_PER_USER = 1
CYCLE_DELAY = 0  # Base delay for the cycle in seconds
COOKIE_UPDATE_INTERVAL = timedelta(hours=24)


def get_users_to_parse(db, limit_users=2):
    query = """
        WITH recent_tweets AS (
            SELECT
                user_id,
                MIN(created_at) AS min_created_at,
                MAX(created_at) AS max_created_at,
                COUNT(*) AS tweet_count
            FROM (
                SELECT
                    user_id,
                    created_at,
                    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
                FROM tweets
            ) AS subquery
            WHERE rn <= 20
            GROUP BY user_id
        ),
        user_intervals AS (
            SELECT
                users.rest_id,
                users.username,
                users.tweets_parsed,
                users.llm_check_score,
                users.tweets_parsed_last_timestamp,
                users.statuses_count,
                users.status,
                min_created_at,
                greatest(max_created_at,tweets_parsed_last_timestamp) AS max_created_at,
                tweet_count,
                CASE
                    WHEN tweet_count < 5 THEN 150000  -- Default interval in seconds for users with less than 5 tweets
                    ELSE GREATEST(LEAST(EXTRACT(EPOCH FROM (greatest(max_created_at,tweets_parsed_last_timestamp) - min_created_at)) / tweet_count, (60 * 24 * 60 * 60)::numeric),
                      (1100)::numeric)
                END AS tweet_interval
            FROM users
            LEFT JOIN recent_tweets ON users.rest_id = recent_tweets.user_id
        ),
        selected_users AS (
            SELECT
                *
            FROM user_intervals
            WHERE (llm_check_score IS NULL OR llm_check_score > 4)
            AND (tweets_parsed = FALSE OR tweets_parsed_last_timestamp < NOW() - INTERVAL '1 second' * tweet_interval * 20)
            AND status = 'idle'
            AND statuses_count > 20
            ORDER BY 
                CASE WHEN tweets_parsed = FALSE THEN 0 ELSE 1 END DESC,
                tweet_interval asc nulls LAST,
                llm_check_score DESC NULLS LAST
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE users
        SET status = 'in_progress'
        FROM selected_users
        WHERE users.rest_id = selected_users.rest_id
        RETURNING users.rest_id, users.username;
    """
    return db.run_query(query, (limit_users,))


def reset_status(db, user_ids):
    if not user_ids:
        return
    reset_status_query = """
        UPDATE users
        SET status = 'idle'
        WHERE rest_id IN ({});
    """.format(
        ", ".join(["%s"] * len(user_ids))
    )
    db.run_query(reset_status_query, tuple(user_ids))


def main(account_name=None):
    last_cookie_update_time = datetime.now()
    account = choose_account(account_name) if account_name else None

    with get_db_connection() as db:
        while True:
            user_ids = []  # Initialize here to prevent UnboundLocalError
            try:
                current_time = datetime.now()
                if (
                    account
                    and current_time - last_cookie_update_time >= COOKIE_UPDATE_INTERVAL
                ):
                    logging.info("24 hours have passed, updating cookies.")
                    scraper = get_twitter_scraper(account, force_login=False)
                    last_cookie_update_time = current_time

                scraper = get_twitter_scraper(account)

                users_to_parse = get_users_to_parse(db, limit_users=USERS_PER_BATCH)
                user_ids = [user[0] for user in users_to_parse]

                if user_ids:
                    logging.info(f"Processing users: {user_ids}")
                    tweets = fetch_tweets_for_users(
                        scraper,
                        user_ids,
                        limit_pages=PAGES_PER_USER,
                        max_retries=1,
                        backoff_factor=0,
                    )
                    if tweets:
                        inserted_tweets_count = save_tweets_to_db(db, tweets)
                        if inserted_tweets_count > 0:
                            update_user_tweets_status(db, user_ids)
                        else:
                            reset_status(db, user_ids)
                    else:
                        reset_status(db, user_ids)
                else:
                    logging.info(
                        "No users to pull tweets. Adding new recommended users"
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
                if user_ids:  # Only reset if we have IDs
                    reset_status(db, user_ids)
                # Add short recovery delay
                time.sleep(1)


if __name__ == "__main__":
    import sys

    # if len(sys.argv) < 2:
    #     print("Usage: python infinite_parse.py [<account_name>]")
    #     sys.exit(1)
    account_name = sys.argv[1] if len(sys.argv) > 1 else None
    main(account_name)
