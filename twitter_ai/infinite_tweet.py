import logging
from utils.config import Config
from utils.db_utils import get_db_connection
from utils.twitter_utils import get_twitter_account
from llm.llm_api import OpenAIAPIHandler, GroqAPIHandler
from datetime import datetime
import random
import time
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

CYCLE_DELAY = 60 * 60  # Base delay for the cycle in seconds

# Define the prompt for LLM
prompt_template = """
YOU ARE A HIGHLY INTELLIGENT LANGUAGE MODEL, THE WORLD'S MOST CREATIVE AND ENGAGING CRYPTO TWITTER USER. YOUR TASK IS TO READ THROUGH 75 RANDOM TWEETS ABOUT CRYPTOCURRENCIES, WEB3, AND CRYPTO POSTED TODAY. USING THIS CONTEXT, YOU WILL GENERATE A RANDOM, CREATIVE, AND PROVOCATIVE TWEET ABOUT CRYPTOCURRENCIES OR WEB3. YOUR TWEET SHOULD APPEAR CASUAL AND AUTHENTIC, AS IF WRITTEN BY A REGULAR CRYPTO TWITTER USER, NOT A PROFESSIONAL.

**Key Objectives:**
- Summarize the main themes and sentiments from the provided tweets.
- Create an engaging and provocative tweet that reflects the current crypto discussion.
- Use casual and informal language typical of crypto Twitter users.
- Ensure the tweet is unique and stands out in the crypto Twitter space.
- Avoid using the # sign in the tweet.

**Chain of Thoughts:**
1. **Analyze Tweets:**
   - Read and summarize the key themes, sentiments, and trends from the 75 tweets.
   - Identify the most talked-about topics, popular opinions, and any emerging controversies or memes.

2. **Formulate a Tweet:**
   - Craft a tweet that incorporates the summarized themes and sentiments.
   - Make it engaging and provocative to spark conversation and interest.

3. **Language and Style:**
   - Use casual, informal language that is typical of regular crypto Twitter users.
   - Ensure the tweet has a creative flair and a hint of provocation.

**What Not To Do:**
- DO NOT WRITE A FORMAL OR PROFESSIONAL-SOUNDING TWEET.
- AVOID CREATING A TWEET THAT IS BORING OR UNORIGINAL.
- DO NOT DISMISS THE TRENDS OR SENTIMENTS FOUND IN THE PROVIDED TWEETS.
- AVOID OFFENSIVE OR INAPPROPRIATE CONTENT THAT COULD BE HARMFUL.
- NEVER USE THE # SIGN IN YOUR TWEET.

**Instructions:**
1. Summarize the 75 provided tweets about crypto today.
2. Use the summarized context to write an engaging and provocative tweet.
3. Ensure the tweet looks like it was written by a regular crypto Twitter user.
4. Do not use the # sign in the tweet.
5. Use proper formating characters in the tweet to make it readable
6. THE MOST IMPORTANT - YOU SHOULD OUTPUT ONLY A FINAL TWEET THAT YOU WROTE, NOTHING MORE

TWEETS TO ANALYZE:
"""


def fetch_tweets_from_db(db):
    query = """
        WITH top_tweets AS (
            SELECT tweet_text, views
            FROM tweets
            JOIN users ON tweets.user_id = users.rest_id
            WHERE 
            (retweeted_tweet IS NULL OR retweeted_tweet = '{}'::jsonb) 
            AND length(tweet_text) > 50
            AND users.llm_check_score > 7
            AND has_urls = False
            AND tweets.created_at > NOW() - INTERVAL '24 HOURS'
            ORDER BY tweets.views DESC
            LIMIT 150
        )
        SELECT tweet_text
        FROM top_tweets
        ORDER BY random()
        LIMIT 75;
    """
    return db.run_query(query)


def summarize_tweets(tweets, llm):
    tweets_text = "\n=============\n".join([tweet[0] for tweet in tweets])
    logging.info("Summarizing tweets for the prompt.")

    prompt = f"{prompt_template} \n\n {tweets_text}"
    summary = llm.get_response(prompt)
    logging.info(f"Raw LLM response: {summary}")

    # Using regular expression to find text inside the longest pair of quotes
    match = re.findall(r'"([^"]{50,})"', summary)
    if match:
        summary = max(
            match, key=len
        )  # Select the longest string if multiple matches found

    return summary


def main():
    # Initialize OpenAI LLM
    logging.info("Initializing OpenAI LLM.")
    llm = OpenAIAPIHandler(Config.OPENAI_API_KEY, model="gpt-4o")
    # llm = GroqAPIHandler(Config.GROQ_API_KEY, model="llama3-70b-8192")

    account = get_twitter_account()
    with get_db_connection() as db:
        while True:
            try:
                # Fetch tweets from the database
                logging.info("Fetching tweets from the database.")
                tweets = fetch_tweets_from_db(db)
                if not tweets:
                    logging.info("No tweets found that match the criteria.")
                    time.sleep(60)  # Wait a bit before retrying
                    continue

                # Summarize tweets
                logging.info("Summarizing tweets.")
                twit = summarize_tweets(tweets, llm)
                if not twit:
                    logging.warning(
                        "Received empty tweet from LLM. Skipping this cycle."
                    )
                    time.sleep(60)  # Wait a bit before retrying
                    continue

                logging.info(f"Generated tweet: {twit}")

                # Post tweet
                logging.info("Posting tweet.")
                account.tweet(twit)

                logging.info("Cycle complete. Waiting for the next cycle.")
                random_sleep_time = random.uniform(CYCLE_DELAY * 0.5, CYCLE_DELAY * 1.5)
                time.sleep(random_sleep_time)

            except Exception as e:
                logging.error(f"An error occurred: {e}", exc_info=True)
                time.sleep(60)  # Sleep for 1 minute before retrying


if __name__ == "__main__":
    main()
