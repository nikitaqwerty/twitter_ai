import logging
from utils.config import Config, configure_logging
from utils.db_utils import get_db_connection, insert_action, insert_tweets
from utils.twitter_utils import get_twitter_account, get_twitter_scraper
from utils.common_utils import process_and_insert_users
from llm.llm_api import OpenAIAPIHandler, GroqAPIHandler, g4fAPIHandler
from datetime import datetime, timedelta
import random
import time
import re

configure_logging()

CYCLE_DELAY = 60 * 60  # Base delay for the cycle in seconds
COOKIE_UPDATE_INTERVAL = timedelta(hours=24)
FIRST_ACCOUNT_RUN = False

prompt_template = """
YOU ARE A HIGHLY INTELLIGENT LANGUAGE MODEL, THE WORLD'S MOST CREATIVE AND ENGAGING CRYPTO TWITTER USER. YOUR TASK IS TO READ THROUGH 75 RANDOM TWEETS ABOUT CRYPTOCURRENCIES, WEB3, AND CRYPTO POSTED TODAY. USING THIS CONTEXT, YOU WILL GENERATE A RANDOM, CREATIVE, AND PROVOCATIVE TWEET ABOUT CRYPTOCURRENCIES OR WEB3. YOUR TWEET SHOULD APPEAR CASUAL AND AUTHENTIC, AS IF WRITTEN BY A REGULAR CRYPTO TWITTER USER, NOT A PROFESSIONAL.

**Key Objectives:**
- Identify the single most popular and discussed topic from the provided tweets.
- Create an engaging and provocative tweet that reflects this topic.
- Use casual and informal language typical of crypto Twitter users.
- Ensure the tweet is unique and stands out in the crypto Twitter space.
- Avoid using the # sign in the tweet.

**Chain of Thoughts:**
1. **Analyze Tweets:**
   - Read and identify the key themes, sentiments, and trends from the 75 tweets.
   - Determine the most talked-about topic and popular opinions related to it.

2. **Formulate a Tweet:**
   - Craft a tweet that focuses solely on the identified popular topic.
   - Make it engaging and provocative to spark conversation and interest.

3. **Language and Style:**
   - Use casual, informal language that is typical of regular crypto Twitter users.
   - Ensure the tweet has a creative flair and a hint of provocation.

**What Not To Do:**
- DO NOT WRITE A FORMAL OR PROFESSIONAL-SOUNDING TWEET.
- AVOID CREATING A TWEET THAT IS BORING OR UNORIGINAL.
- DO NOT MIX MULTIPLE TRENDS OR TOPICS INTO ONE TWEET.
- AVOID OFFENSIVE OR INAPPROPRIATE CONTENT THAT COULD BE HARMFUL.
- NEVER USE THE # SIGN IN YOUR TWEET.

**Instructions:**
1. Identify the single most popular and discussed topic from the 75 provided tweets about crypto today.
2. Use this context to write an engaging and provocative tweet focused on that topic.
3. Ensure the tweet looks like it was written by a regular crypto Twitter user.
4. Do not use the # sign in the tweet.
5. Use proper formatting characters in the tweet to make it readable.
6. THE MOST IMPORTANT - YOU SHOULD OUTPUT ONLY A FINAL TWEET THAT YOU WROTE, NOTHING MORE.

TWEETS TO ANALYZE:
"""


def fetch_tweets_from_db(db):
    query = """
        WITH top_tweets AS (
            SELECT tweet_text, views
            FROM tweets
            JOIN users ON tweets.user_id = users.rest_id
            WHERE 
            length(tweet_text) > 50
            AND users.llm_check_score > 5
            AND has_urls = False
            AND tweets.created_at > NOW() - INTERVAL '24 HOURS'
            AND tweet_text !~* '(follow|retweet|reply|comment|giveaway|RT @)'
            AND lang = 'en'
            AND users.username != 'rndm_world'
            AND (users_mentioned is null or array_length(users_mentioned, 1)  < 3)
            ORDER BY tweets.views DESC
            LIMIT 400
        )
        SELECT tweet_text
        FROM top_tweets
        ORDER BY random()
        LIMIT 75;
    """
    return db.run_query(query)


def extract_final_tweet(initial_response, llm):
    logging.info("Extracting the final tweet.")

    extraction_prompt = f"""
    You will receive an initial response from another LLM that was asked to write a tweet. Your task is to extract and return only the final tweet from the response, ignoring any other content, labels, quotes or comments. 

    Initial Response:
    {initial_response}

    Now please provide only the final tweet and stop speaking.
    """

    final_tweet_response = llm.get_response(extraction_prompt)
    final_tweet = final_tweet_response.strip()

    # Remove starting and ending quotes if present
    if final_tweet.startswith('"') and final_tweet.endswith('"'):
        final_tweet = final_tweet[1:-1].strip()

    # Check if the tweet meets length criteria
    if len(final_tweet) <= 10 or len(final_tweet) >= 280:
        logging.warning(
            f"Tweet length is invalid: {len(final_tweet)} characters. Tweet: {final_tweet}"
        )
        return None

    return final_tweet


def summarize_tweets(tweets, llm):
    tweets_text = "\n=============\n".join([tweet[0] for tweet in tweets])
    logging.debug(f"Summarizing tweets for the prompt. Input tweets: \n{tweets_text}")

    prompt = f"{prompt_template} \n\n {tweets_text}"
    initial_llm_response = llm.get_response(prompt)
    logging.info(f"Raw LLM response: {initial_llm_response}")

    final_tweet = extract_final_tweet(initial_llm_response, llm)
    if not final_tweet:
        logging.warning(
            "Final tweet extraction failed or tweet did not meet the criteria."
        )
        return None, None

    logging.info(f"Extracted final tweet: {final_tweet}")
    return initial_llm_response, final_tweet


def main():
    # Initialize OpenAI LLM
    logging.info("Initializing OpenAI LLM.")
    # llm = OpenAIAPIHandler(Config.OPENAI_API_KEY, model="gpt-4o")
    llm_g4f = g4fAPIHandler(model="gpt-4o", cookies_dir=Config.COOKIES_DIR)
    llm_groq = GroqAPIHandler(Config.GROQ_API_KEY, model="llama3-70b-8192")

    last_cookie_update_time = datetime.now()  # Initialize to the current time

    account = get_twitter_account()

    with get_db_connection() as db:
        if FIRST_ACCOUNT_RUN:
            scraper = get_twitter_scraper()
            process_and_insert_users(db, scraper, account.id)
        while True:
            try:
                current_time = datetime.now()
                # Check if 24 hours have passed since the last cookie update
                if current_time - last_cookie_update_time >= COOKIE_UPDATE_INTERVAL:
                    logging.info("24 hours have passed, updating cookies.")
                    time.sleep(10)
                    account = get_twitter_account(force_login=True)
                    scraper = get_twitter_scraper(force_login=False)
                    last_cookie_update_time = current_time

                # Fetch tweets from the database
                logging.info("Fetching tweets from the database.")
                tweets = fetch_tweets_from_db(db)
                if not tweets:
                    logging.info("No tweets found that match the criteria.")
                    time.sleep(60)  # Wait a bit before retrying
                    continue

                # Summarize tweets
                logging.info("Summarizing tweets.")
                llm = llm_g4f
                try:
                    raw_output, twit = summarize_tweets(tweets, llm)
                except Exception as e:
                    logging.error(
                        f"Error with g4fAPIHandler: {e}. Retrying with GroqAPIHandler."
                    )
                    llm = llm_groq
                    raw_output, twit = summarize_tweets(tweets, llm)

                if not twit:
                    logging.warning(
                        "Received empty or invalid tweet from LLM. Skipping this cycle."
                    )
                    time.sleep(60)  # Wait a bit before retrying
                    continue

                logging.info(f"Generated tweet: {twit}")

                # Post tweet
                logging.info("Posting tweet.")
                resp = account.tweet(twit)
                tweet_results = resp["data"]["create_tweet"]["tweet_results"]["result"]
                insert_tweets(db, tweet_results)
                insert_action(
                    db,
                    account.id,
                    "tweet",
                    tweet_results["rest_id"],
                    None,
                    None,
                    raw_output,
                    llm.model,
                    prompt_template,
                )

                logging.info("Cycle complete. Waiting for the next cycle.")
                random_sleep_time = random.uniform(CYCLE_DELAY * 0.5, CYCLE_DELAY * 1.5)
                time.sleep(random_sleep_time)

            except Exception as e:
                logging.error(f"An error occurred: {e}", exc_info=True)
                time.sleep(60)  # Sleep for 1 minute before retrying


if __name__ == "__main__":
    main()
