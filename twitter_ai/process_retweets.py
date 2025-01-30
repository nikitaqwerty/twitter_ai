import time
import logging
from db.database import Database
from utils.db_utils import insert_users, insert_tweets, get_db_connection

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def process_tweets(db, tweets):
    user_data = []
    tweet_data = []

    for tweet in tweets:
        for tweet_type in tweet:
            tweet_info = tweet_type.get("result", {})
            user_info = (
                tweet_info.get("core", {}).get("user_results", {}).get("result", {})
            )
            if user_info:
                user_data.append(user_info)
            if tweet_info:
                tweet_data.append(tweet_info)

    if user_data:
        logging.info(f"Inserting {len(user_data)} users into the database.")
        insert_users(db, user_data)

    # Ensure all tweet authors exist in users table
    user_ids = []
    for tweet_info in tweet_data:
        try:
            user_id = tweet_info["legacy"]["user_id_str"]
            user_ids.append(user_id)
        except KeyError:
            logging.error(
                "Missing user_id_str in tweet_info", extra={"tweet_info": tweet_info}
            )

    if user_ids:
        placeholders = ", ".join(["%s"] * len(user_ids))
        existing = db.run_query(
            f"SELECT rest_id FROM users WHERE rest_id IN ({placeholders})", user_ids
        )
        existing_users = {row[0] for row in existing}
        missing_users = [
            {"rest_id": uid, "legacy": {}, "professional": {}}
            for uid in user_ids
            if uid not in existing_users
        ]

        if missing_users:
            logging.info(f"Inserting {len(missing_users)} minimal user records")
            insert_users(db, missing_users)

    if tweet_data:
        logging.info(f"Inserting {len(tweet_data)} tweets into the database.")
        insert_tweets(db, tweet_data)


def fetch_tweets_to_process(db, limit=1000):
    query = """
        SELECT t.retweeted_tweet, t.quoted_tweet
        FROM tweets t
        LEFT JOIN tweets rt ON (t.retweeted_tweet->'result'->>'rest_id') = rt.tweet_id
        LEFT JOIN tweets qt ON (t.quoted_tweet->'result'->>'rest_id') = qt.tweet_id
        WHERE 
            (
                t.retweeted_tweet IS NOT NULL 
                AND t.retweeted_tweet::text <> '{}' 
                AND rt.tweet_id IS NULL
                AND (t.retweeted_tweet->'result' ? 'legacy')
            )
            OR 
            (
                t.quoted_tweet IS NOT NULL 
                AND t.quoted_tweet::text <> '{}' 
                AND qt.tweet_id IS NULL
                AND (t.quoted_tweet->'result' ? 'legacy')
            )
        LIMIT %s;
    """
    return db.run_query(query, (limit,))


def job():
    with get_db_connection() as db:
        while True:
            try:
                tweets = fetch_tweets_to_process(db)
                if not tweets:
                    logging.info("No tweets to process. Sleeping for 5 minutes...")
                    time.sleep(300)
                    continue

                process_tweets(db, tweets)
                logging.info("Processed batch of tweets")
                time.sleep(10)

            except Exception as e:
                logging.error(f"Error occurred: {e}")
                time.sleep(60)


if __name__ == "__main__":
    job()
