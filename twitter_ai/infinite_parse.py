import os
import time
import logging
import traceback
import random
from twitter.scraper import Scraper
from utils.db_utils import get_db_connection, update_user_tweets_status
from utils.twitter_utils import get_twitter_scraper
from utils.common_utils import (
    fetch_tweets_for_users,
    save_tweets_to_db,
    save_users_recommendations_by_ids,
)

# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

USERS_PER_BATCH = 5
PAGES_PER_USER = 1
CYCLE_DELAY = 60  # Base delay for the cycle in seconds
USERS_UPDATE_HOURS_DELAY = 48


def get_users_to_parse(db, hours=48, limit_users=2):
    query = """
        SELECT rest_id, username 
        FROM users
        WHERE (llm_check_score is null or llm_check_score > 5) and (tweets_parsed = FALSE 
           OR tweets_parsed_last_timestamp < NOW() - INTERVAL '%s HOURS')
        ORDER BY llm_check_score DESC
        LIMIT %s;
    """
    return db.run_query(query, (hours, limit_users))


def get_high_score_users(db, min_score=8, hours=48, limit_users=5):
    query = """
        SELECT rest_id, username
        FROM users
        WHERE llm_check_score > %s 
            AND (recommendations_pulled_last_timestamp > NOW() - INTERVAL '%s HOURS'   
                    OR recommendations_pulled_last_timestamp IS NULL)
        ORDER BY recommendations_pulled_last_timestamp ASC
        LIMIT %s;
    """
    return db.run_query(query, (min_score, hours, limit_users))


def main():
    scraper = get_twitter_scraper()
    with get_db_connection() as db:
        while True:
            try:
                users_to_parse = get_users_to_parse(
                    db, hours=USERS_UPDATE_HOURS_DELAY, limit_users=USERS_PER_BATCH
                )
                user_ids = [user[0] for user in users_to_parse]

                if user_ids[0]:
                    logging.info(f"Processing users: {user_ids}")
                    tweets = fetch_tweets_for_users(
                        scraper, user_ids, limit_pages=PAGES_PER_USER
                    )
                    if tweets:
                        save_tweets_to_db(db, tweets)
                        update_user_tweets_status(db, user_ids)

                else:
                    logging.info(
                        f"No users to pull tweets. Adding new recommended users"
                    )
                    high_score_users = get_high_score_users(db, limit_users=5)
                    if high_score_users:
                        user_ids = [user[0] for user in high_score_users]
                        save_users_recommendations_by_ids(db, scraper, user_ids)

                logging.info("Cycle complete. Waiting for the next cycle.")
                random_sleep_time = random.uniform(CYCLE_DELAY * 0.5, CYCLE_DELAY * 1.5)
                time.sleep(random_sleep_time)
            except Exception as e:
                logging.error(f"An error occurred: {e}")
                logging.error(f"{traceback.format_exc()}")


if __name__ == "__main__":
    main()
