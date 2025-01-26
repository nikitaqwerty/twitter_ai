import os
import logging
import pyperclip
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_db_connection
from utils.config import Config
from utils.common_utils import remove_https_links

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)





def fetch_tweets_from_db(db):
    query = """
        WITH top_tweets AS (
            SELECT tweet_text, users.name
            FROM tweets
            JOIN users ON tweets.user_id = users.rest_id
            WHERE 
            length(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(tweet_text, 'https?://[^\s]+', '', 'g'), 
                            '@[A-Za-z0-9_]+', '', 'g'
                        ), 
                        '\$[A-Za-z0-9]+', '', 'g'
                    ), 
                    '#[A-Za-z0-9_]+', '', 'g'
                )
            ) > 50            
            AND users.llm_check_score > 6
            AND has_urls = False
            AND tweets.created_at > NOW() - INTERVAL '24 HOURS'
            AND tweet_text !~* '(farm|follow|retweet|reply|comment|giveaway|RT @)'
            AND lang = 'en'
            AND quotes > 0
            AND users.rest_id not in (select distinct action_account_id from actions)
            AND (users_mentioned is null or array_length(users_mentioned, 1)  < 3 or users_mentioned::text = '{}')
            AND (symbols is null or array_length(symbols, 1)  < 4 or symbols::text = '{}')
            ORDER BY tweets.views DESC
            LIMIT 400
        )
        SELECT tweet_text, name
        FROM top_tweets
        -- ORDER BY random()
        LIMIT 400;
    """
    return db.run_query(query)


def prepare_request(tweets):
    tweets_list = [{"username": tweet[1], "tweet": tweet[0]} for tweet in tweets]
    logging.debug(f"Summarizing tweets for the prompt. Input tweets: \n{tweets_list}")

    prompt = remove_https_links(
        f"{prompt_template} \n\n {json.dumps(tweets_list, indent=0,ensure_ascii=False)}"
    )
    return prompt


def main():
    # Fetch tweets from the database
    with get_db_connection() as db:
        tweets = fetch_tweets_from_db(db)
    if not tweets:
        logging.info("No tweets found that match the criteria.")
        return

    # Prepare the request
    request = prepare_request(tweets)
    print("Request to be sent: ", request)

    # Copy to clipboard
    pyperclip.copy(request)
    logging.info("Request copied to clipboard.")


if __name__ == "__main__":
    main()
