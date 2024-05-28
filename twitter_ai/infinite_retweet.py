import logging
from utils.config import configure_logging
from utils.db_utils import get_db_connection, insert_action
from utils.twitter_utils import get_twitter_account
from datetime import datetime, timedelta
import random
import time

configure_logging()

CYCLE_DELAY = 60 * 45  # Base delay for the cycle in seconds
COOKIE_UPDATE_INTERVAL = timedelta(hours=24)


def fetch_tweets_for_retweet(db):
    query = """
        WITH top_tweets AS (
            SELECT 
                tweets.tweet_id,
                users.rest_id
            FROM tweets
            JOIN users ON tweets.user_id = users.rest_id
            LEFT JOIN actions ON tweets.tweet_id = actions.tweet_id
            WHERE 
                users.llm_check_score > 7
                -- AND users.followers_count < 30000
                -- and users.friends_count > 1000
                AND tweets.created_at > NOW() - INTERVAL '6 HOURS'
                AND tweets.tweet_text !~* '(retweet|reply|comment|giveaway|RT @)'
                AND tweets.lang = 'en'
                AND actions.tweet_id IS NULL
            ORDER BY tweets.views DESC
            LIMIT 10
        )
        SELECT tweet_id, rest_id
        FROM top_tweets
        WHERE rest_id NOT IN (
            SELECT target_user_id 
            FROM actions 
            WHERE action_type = 'retweet'
        )
        ORDER BY random()
        LIMIT 1;
    """
    return db.run_query(query)


def retweet_tweet(account, tweet_id):
    try:
        logging.info(f"Retweeting tweet ID: {tweet_id}")
        resp = account.retweet(tweet_id)
        return resp["data"]["create_retweet"]["retweet_results"]["result"]
    except Exception as e:
        logging.error(f"Error retweeting tweet ID {tweet_id}: {e}")
        return None


def main():
    logging.info("Initializing Twitter account.")
    last_cookie_update_time = (
        datetime.now() - COOKIE_UPDATE_INTERVAL
    )  # Initialize to ensure immediate update on first run
    account = get_twitter_account()

    with get_db_connection() as db:
        while True:
            try:
                current_time = datetime.now()
                # Check if 24 hours have passed since the last cookie update
                if current_time - last_cookie_update_time >= COOKIE_UPDATE_INTERVAL:
                    logging.info("24 hours have passed, updating cookies.")
                    account = get_twitter_account(force_login=False)
                    last_cookie_update_time = current_time

                # Fetch tweets from the database
                logging.info("Fetching tweets from the database for retweeting.")
                tweets = fetch_tweets_for_retweet(db)
                if not tweets:
                    logging.info("No tweets found that match the criteria.")
                    time.sleep(60)  # Wait a bit before retrying
                    continue

                for tweet in tweets:
                    target_tweet_id, target_user_id = tweet
                    retweet_response = retweet_tweet(account, target_tweet_id)
                    random_sleep_time = random.uniform(3, 6)
                    time.sleep(random_sleep_time)

                    account.like(target_tweet_id)
                    random_sleep_time = random.uniform(3, 6)

                    time.sleep(random_sleep_time)
                    # account.follow(target_user_id)
                    if retweet_response:
                        logging.info(
                            f"Successfully retweeted tweet ID: {target_tweet_id}"
                        )
                        insert_action(
                            db,
                            account.id,
                            "retweet",
                            retweet_response["rest_id"],
                            target_tweet_id,
                            target_user_id,
                            None,
                            None,
                            None,
                        )
                        insert_action(
                            db,
                            account.id,
                            "like",
                            None,
                            target_tweet_id,
                            target_user_id,
                            None,
                            None,
                            None,
                        )
                        # insert_action(
                        #     db,
                        #     account.id,
                        #     "follow",
                        #     None,
                        #     None,
                        #     target_user_id,
                        #     None,
                        #     None,
                        #     None,
                        # )

                logging.info("Cycle complete. Waiting for the next cycle.")
                random_sleep_time = random.uniform(CYCLE_DELAY * 0.5, CYCLE_DELAY * 1.5)
                time.sleep(random_sleep_time)

            except Exception as e:
                logging.error(f"An error occurred: {e}", exc_info=True)
                time.sleep(60)  # Sleep for 1 minute before retrying


if __name__ == "__main__":
    main()
