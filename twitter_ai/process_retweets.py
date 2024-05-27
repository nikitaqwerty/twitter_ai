import time
import logging
from db.database import Database
from utils.db_utils import insert_users, insert_tweets, get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def process_tweets(db, tweets):
    """
    Process a batch of tweets to insert users and tweets into the database.
    """
    user_data = []
    tweet_data = []

    for tweet in tweets:
        # Extract user data from retweeted_tweet and quoted_tweet
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

    if tweet_data:
        logging.info(f"Inserting {len(tweet_data)} tweets into the database.")
        insert_tweets(db, tweet_data)


def fetch_tweets_to_process(db, limit=1000):
    """
    Fetch a batch of tweets that have quoted or retweeted tweets to process.
    """
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
                    logging.info("No tweets to process. Sleeping for a while...")
                    time.sleep(300)  # Sleep for 60 seconds if no tweets are found
                    continue

                process_tweets(db, tweets)
                logging.info("Processed a batch of tweets.")

                # Delay between processing batches
                time.sleep(1)  # Sleep for 10 seconds between batches

            except Exception as e:
                logging.error(f"Error occurred: {e}")
                time.sleep(60)  # Sleep for 60 seconds before retrying


if __name__ == "__main__":
    job()
