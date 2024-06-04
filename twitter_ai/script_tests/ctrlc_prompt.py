import os
import logging
import pyperclip
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_db_connection
from utils.config import Config
from utils.common_utils import remove_https_links

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

prompt_template = """YOU ARE THE WORLD'S BEST EXPERT IN CRYPTOCURRENCY ANALYSIS AND SOCIAL MEDIA TRENDS, RECOGNIZED FOR YOUR EXCEPTIONAL ABILITY TO IDENTIFY AND SUMMARIZE KEY TOPICS, TRENDS, EVENTS, AND STORIES FROM LARGE VOLUMES OF DATA. YOUR TASK IS TO ANALYZE 100 RANDOM CRYPTO TWEETS POSTED IN THE LAST 24 HOURS, IDENTIFY THE MOST IMPORTANT AND POPULAR TOPICS, AND SUMMARIZE THIS INFORMATION IN A JSON REPORT, USING CRYPTO SYMBOLS LIKE $BTC WHERE APPROPRIATE.

**Key Objectives:**
- **ANALYZE** 100 random crypto tweets from the past 24 hours.
- **IDENTIFY** key topics, trends, events, and stories.
- **SUMMARIZE** the information in a clear and concise manner.
- **OUTPUT** the report in JSON format, ordered by importance and popularity of the topics.
- **LIMIT** the report to a maximum of 3 topics, ensuring summarized but comprehensive information.

**Chain of Thoughts:**
1. **Collecting Data:**
   - Gather 100 random crypto tweets from the last 24 hours.
   - Ensure a diverse representation of tweets to capture a wide range of perspectives and information.

2. **Analyzing Tweets:**
   - Scan through each tweet to identify recurring themes, hashtags, and mentions.
   - Note any significant events or news that are frequently discussed.

3. **Identifying Key Topics:**
   - Determine which topics are most mentioned or discussed.
   - Identify any emerging trends or notable stories.

4. **Summarizing Information:**
   - Summarize the key topics, trends, and events in a informative manner.
   - Use cryptocurrency symbols (e.g., $BTC) where relevant to maintain authenticity and context.
   - Ensure the summary is comprehensive, focusing on key details.
   - Write this summary like it is a newsletter article for CoinDesk or any big crypto journal

5. **Creating JSON Report:**
   - Organize the summarized information in JSON format.
   - Ensure the topics are ordered by their importance and popularity.
   - Limit the report to a maximum of 3 topics.

**What Not To Do:**
- **DO NOT OVERLOOK** minor yet emerging trends.
- **AVOID USING** unclear or ambiguous language in summaries.
- **DO NOT FAIL** to use cryptocurrency symbols like $BTC where appropriate.
- **NEVER OUTPUT** information in a format other than JSON.

**Example JSON Output:**
```json
{
  "trends": [
    {
      "topic": "{topic1}",
      "summary": "{summary}",
      "importance": 1
    },
    {
      "topic": "{topic2}",
      "summary": "{summary}",
      "importance": 2
    },
    {
      "topic": "{topic3}",
      "summary": "{summary}",
      "importance": 3
    }
  ]
}

TWEETS TO ANALYZE:
"""


def fetch_tweets_from_db(db):
    query = """
        WITH top_tweets AS (
            SELECT tweet_text
            FROM tweets
            JOIN users ON tweets.user_id = users.rest_id
            WHERE 
            length(tweet_text) > 50
            AND users.llm_check_score > 6
            AND has_urls = False
            AND tweets.created_at > NOW() - INTERVAL '24 HOURS'
            AND tweet_text !~* '(farm|follow|retweet|reply|comment|giveaway|RT @)'
            AND lang = 'en'
            and quotes > 0
            AND users.rest_id not in (select distinct action_account_id from actions)
            AND (users_mentioned is null or array_length(users_mentioned, 1)  < 3 or users_mentioned::text = '{}')
            AND (symbols is null or array_length(symbols, 1)  < 3 or symbols::text = '{}')
            ORDER BY tweets.views DESC
            LIMIT 500
        )
        SELECT tweet_text
        FROM top_tweets
        ORDER BY random()
        LIMIT 100;
    """
    return db.run_query(query)


def prepare_request(tweets)
    tweets_text = "\n=============\n".join([tweet[0] for tweet in tweets])
    logging.debug(f"Summarizing tweets for the prompt. Input tweets: \n{tweets_text}")

    prompt = remove_https_links(f"{prompt_template} \n\n {tweets_text}")
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
