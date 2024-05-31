import logging
import sys
from utils.config import configure_logging, Config
from utils.db_utils import get_db_connection, insert_action
from utils.twitter_utils import get_twitter_account, choose_account
from datetime import datetime, timedelta
import random
import time


configure_logging()

CYCLE_DELAY = 60 * 30  # Base delay for the cycle in seconds
COOKIE_UPDATE_INTERVAL = timedelta(hours=24)


def fetch_account_to_follow(db):
    query = """
        WITH target_accounts AS (
            SELECT
                users.rest_id,
                users.followers_count,
                users.friends_count
            FROM users
            LEFT JOIN actions ON users.rest_id = actions.target_user_id AND actions.action_type = 'follow'
            JOIN tweets ON users.rest_id = tweets.user_id
            WHERE actions.target_user_id IS NULL
                AND users.followers_count > 100
                AND users.friends_count > 100
                AND users.friends_count / users.followers_count > 0.8
                AND users.llm_check_score > 5
                AND tweets.created_at > NOW() - INTERVAL '48 HOURS'
            GROUP BY users.rest_id, users.followers_count, users.friends_count
            ORDER BY users.friends_count desc
            LIMIT 1
        )
        SELECT rest_id
        FROM target_accounts;
    """
    return db.run_query(query)


def fetch_account_to_unfollow(db, account_id):
    query = """
        SELECT target_user_id
        FROM actions
        WHERE action_account_id = %s
          AND action_type = 'follow'
          AND created_at + INTERVAL '7 DAYS' < NOW()
          AND target_user_id NOT IN (
              SELECT target_user_id
              FROM actions
              WHERE action_account_id = %s
                AND action_type = 'unfollow'
          )
        ORDER BY created_at ASC
        LIMIT 1;
    """
    return db.run_query(query, (str(account_id), str(account_id)))


def follow_account(account, user_id):
    try:
        logging.info(f"Following user ID: {user_id}")
        resp = account.follow(user_id)
        return resp
    except Exception as e:
        logging.error(f"Error following user ID {user_id}: {e}")
        return None


def unfollow_account(account, user_id):
    try:
        logging.info(f"Unfollowing user ID: {user_id}")
        resp = account.unfollow(user_id)
        return resp
    except Exception as e:
        logging.error(f"Error unfollowing user ID {user_id}: {e}")
        return None


def main(account_name):
    time.sleep(random.uniform(0, 10))
    logging.info("Initializing Twitter account.")
    last_cookie_update_time = datetime.now()  # Initialize to the current time

    account = choose_account(account_name)
    twitter_account = get_twitter_account(account)

    with get_db_connection() as db:
        while True:
            try:
                current_time = datetime.now()
                # Check if 24 hours have passed since the last cookie update
                if current_time - last_cookie_update_time >= COOKIE_UPDATE_INTERVAL:
                    logging.info("24 hours have passed, updating cookies.")
                    twitter_account = get_twitter_account(account, force_login=False)
                    last_cookie_update_time = current_time

                # Follow a new account
                logging.info("Fetching account to follow.")
                follow_accounts = fetch_account_to_follow(db)
                if follow_accounts:
                    target_user_id = follow_accounts[0][0]
                    follow_response = follow_account(twitter_account, target_user_id)
                    if follow_response:
                        logging.info(f"Successfully followed user ID: {target_user_id}")
                        insert_action(
                            db,
                            twitter_account.id,
                            "follow",
                            None,
                            None,
                            target_user_id,
                            None,
                            None,
                            None,
                        )

                # Unfollow an old account
                logging.info("Fetching account to unfollow.")
                time.sleep(10)
                unfollow_accounts = fetch_account_to_unfollow(db, twitter_account.id)
                if unfollow_accounts:
                    unfollow_user_id = unfollow_accounts[0][0]
                    unfollow_response = unfollow_account(
                        twitter_account, unfollow_user_id
                    )
                    if unfollow_response:
                        logging.info(
                            f"Successfully unfollowed user ID: {unfollow_user_id}"
                        )
                        insert_action(
                            db,
                            twitter_account.id,
                            "unfollow",
                            None,
                            None,
                            unfollow_user_id,
                            None,
                            None,
                            None,
                        )
                else:
                    logging.info("No accounts to unfollow")
                logging.info("Cycle complete. Waiting for the next cycle.")
                random_sleep_time = random.uniform(CYCLE_DELAY * 0.5, CYCLE_DELAY * 1.5)
                time.sleep(random_sleep_time)

            except Exception as e:
                logging.error(f"An error occurred: {e}", exc_info=True)
                time.sleep(60)  # Sleep for 1 minute before retrying


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python infinite_follow.py <account_name>")
        sys.exit(1)
    account_name = sys.argv[1]
    main(account_name)
