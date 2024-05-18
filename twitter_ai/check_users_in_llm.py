import os
import logging
from utils.db_utils import get_db_connection
from utils.config import Config
from llm.llm_groq import GroqLLM
from datetime import datetime
import re
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize Groq LLM
groq_llm = GroqLLM(Config.GROQ_API_KEY)

# Define the prompt for Groq LLM
prompt_template = """
YOU ARE AN ADVANCED LANGUAGE MODEL, TASKED WITH ANALYZING IF THE FOLLOWING TWEETS ARE ABOUT CRYPTOCURRENCY. 
BASED ON THE CONTENT, PROVIDE A SCORE FROM 0 TO 10, WHERE 0 MEANS THE USER IS NOT WRITING ABOUT CRYPTOCURRENCY AT ALL, AND 10 MEANS THE USER IS EXCLUSIVELY WRITING ABOUT CRYPTOCURRENCY. 
GIVE ME ONLY ONE NUMBER COMBINED BASED ON ALL TWEETS YOU JUST READ AND I WILL TIP YOU 100$

**Tweets:**
{tweets}

**Combined Score:**
"""


def fetch_users_from_db():
    query = """
        SELECT rest_id 
        FROM users
        WHERE llm_check_score IS NULL;
    """
    with get_db_connection() as db:
        return db.run_query(query)


def fetch_latest_tweets_for_user(db, user_id, limit=20):
    query = """
        SELECT tweet_text 
        FROM tweets
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s;
    """
    return db.run_query(query, (user_id, limit))


def analyze_tweets_with_llm(tweets, max_retries=5, backoff_factor=1):
    tweets_text = "\n=============\n".join(tweet[0] for tweet in tweets)
    prompt = prompt_template.format(tweets=tweets_text)

    retries = 0
    while retries < max_retries:
        response = groq_llm.get_response(prompt)
        if response:
            break
        else:
            wait_time = backoff_factor * (2**retries)
            logging.error(
                f"Error fetching LLM response. Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)
            retries += 1

    if not response:
        raise ValueError(
            "Max retries reached or failed to get a valid response from LLM"
        )

    # Use regex to find the score in the response (0-10 range)
    print(response)
    match = re.search(r"\b(10(?:\.0+)?|\d(?:\.\d+)?)\b", response)
    if match:
        score = float(match.group(1))
    else:
        raise ValueError("No valid score found in the response")

    return score


def update_llm_check_score(db, user_id, score):
    query = """
        UPDATE users
        SET llm_check_score = %s, llm_check_last_timestamp = %s
        WHERE rest_id = %s;
    """
    params = (score, datetime.utcnow(), user_id)
    db.run_query(query, params)


def main():
    with get_db_connection() as db:
        users = fetch_users_from_db()
        for user in users:
            user_id = user[0]
            logging.info(f"Processing user: {user_id}")

            tweets = fetch_latest_tweets_for_user(db, user_id)
            if not tweets:
                logging.info(f"No tweets found for user: {user_id}")
                continue

            score = analyze_tweets_with_llm(tweets)
            logging.info(f"User {user_id} LLM check score: {score}")

            update_llm_check_score(db, user_id, score)
            logging.info(f"Updated LLM check score for user: {user_id}")


if __name__ == "__main__":
    main()
