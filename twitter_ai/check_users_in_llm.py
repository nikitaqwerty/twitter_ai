import logging
from utils.db_utils import get_db_connection
from utils.config import Config, configure_logging
from llm.llm_api import GroqAPIHandler
from datetime import datetime
import re
import time

configure_logging()

# Initialize Groq LLM
groq_llm = GroqAPIHandler(Config.GROQ_API_KEY)

# Define the prompt for Groq LLM
prompt_template = """
YOU ARE AN ADVANCED LANGUAGE MODEL, TASKED WITH ANALYZING IF THE FOLLOWING TWEETS ARE ABOUT CRYPTOCURRENCY. 
BASED ON THE CONTENT, PROVIDE A SCORE FROM 0 TO 10, WHERE 0 MEANS THE USER IS NOT WRITING ABOUT CRYPTOCURRENCY AT ALL, AND 10 MEANS THE USER IS EXCLUSIVELY WRITING ABOUT CRYPTOCURRENCY. 
GIVE ME ONLY ONE NUMBER COMBINED BASED ON ALL TWEETS YOU JUST READ AND I WILL TIP YOU 100$

**Username:** {username}
**Bio:** {bio}
**Tweets:**
{tweets}

**Combined Score:**
"""


def fetch_users_from_db():
    query = """
        SELECT u.rest_id, u.name, u.description 
        FROM users u
        JOIN tweets t ON u.rest_id = t.user_id
        WHERE u.llm_check_score IS NULL
        GROUP BY u.rest_id, u.name, u.description
        HAVING COUNT(t.tweet_id) >= 5;
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


def analyze_tweets_with_llm(username, bio, tweets, max_retries=5, backoff_factor=1):
    def get_prompt_from_tweets(username, bio, tweets_list):
        tweets_text = "\n=============\n".join(tweet[0] for tweet in tweets_list)
        return prompt_template.format(username=username, bio=bio, tweets=tweets_text)

    prompt = get_prompt_from_tweets(username, bio, tweets)
    retries = 0

    while retries < max_retries:
        try:
            response = groq_llm.get_response(prompt)
            if isinstance(response, dict) and (
                response.get("error")
                in ["rate_limit_exceeded", "context_length_exceeded"]
            ):
                logging.error(
                    "Context length exceeded, reducing the number of tweets and retrying..."
                )
                if len(tweets) > 1:
                    tweets = tweets[
                        : len(tweets) // 2
                    ]  # Reduce the number of tweets by half
                    prompt = get_prompt_from_tweets(username, bio, tweets)
                else:
                    raise ValueError(
                        "Cannot reduce tweets length further, only one tweet left."
                    )
            elif response:
                break
            else:
                wait_time = backoff_factor * (2**retries)
                logging.error(
                    f"Error fetching LLM response. Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
                retries += 1
        except Exception as e:
            logging.error(f"Exception during LLM API call: {e}")
            wait_time = backoff_factor * (2**retries)
            logging.error(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            retries += 1

    if not response:
        raise ValueError(
            "Max retries reached or failed to get a valid response from LLM"
        )

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
        while True:
            try:
                logging.info("Fetching users from the database")
                users = fetch_users_from_db()
                if not users:
                    logging.info("No users found needing LLM check")
                    time.sleep(300)
                    continue

                for user in users:
                    user_id, username, bio = user
                    logging.info(f"Processing user: {user_id}")

                    tweets = fetch_latest_tweets_for_user(db, user_id)
                    if not tweets:
                        logging.info(f"No tweets found for user: {user_id}")
                        continue

                    try:
                        score = analyze_tweets_with_llm(username, bio, tweets)
                        logging.info(f"User {user_id} LLM check score: {score}")
                        update_llm_check_score(db, user_id, score)
                        logging.info(f"Updated LLM check score for user: {user_id}")
                    except Exception as e:
                        logging.error(
                            f"Failed to analyze tweets for user {user_id}: {e}"
                        )

                logging.info("Sleeping for 5 minutes before next cycle")
                time.sleep(300)  # Sleep for 5 minutes before checking again

            except Exception as e:
                logging.error(f"An error occurred in the main loop: {e}")
                time.sleep(60)  # Sleep for 1 minute before retrying


if __name__ == "__main__":
    main()
