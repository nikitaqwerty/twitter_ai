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
   - Pay attention to tweets with high engagement (likes, retweets, comments) as indicators of importance.

4. **Summarizing Information:**
   - Summarize the key topics, trends, and events in a concise manner.
   - Use cryptocurrency symbols (e.g., $BTC) where relevant to maintain authenticity and context.

5. **Creating JSON Report:**
   - Organize the summarized information in JSON format.
   - Ensure the topics are ordered by their importance and popularity.

**What Not To Do:**
- **NEVER IGNORE** significant tweets with high engagement.
- **DO NOT OVERLOOK** minor yet emerging trends.
- **AVOID USING** unclear or ambiguous language in summaries.
- **DO NOT FAIL** to use cryptocurrency symbols like $BTC where appropriate.
- **NEVER OUTPUT** information in a format other than JSON.

**Example JSON Output:**
```json
{
  "summary": [
    {
      "topic": "Bitcoin Price Surge",
      "mentions": 45,
      "description": "Significant increase in $BTC price over the past 24 hours, reaching a new monthly high.",
      "importance": 1
    },
    {
      "topic": "Ethereum Network Upgrade",
      "mentions": 30,
      "description": "Discussion around the recent $ETH network upgrade and its potential impacts.",
      "importance": 2
    },
    {
      "topic": "DeFi Protocol Exploit",
      "mentions": 15,
      "description": "News about a security breach in a major DeFi protocol causing significant fund losses.",
      "importance": 3
    },
    {
      "topic": "Crypto Regulation Updates",
      "mentions": 10,
      "description": "Updates on new regulatory measures affecting cryptocurrency trading in various regions.",
      "importance": 4
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
            AND tweet_text !~* '(follow|retweet|reply|comment|giveaway|RT @)'
            AND lang = 'en'
            and quotes > 0
            AND users.rest_id not in (select distinct action_account_id from actions)
            AND (users_mentioned is null or array_length(users_mentioned, 1)  < 3 or users_mentioned::text = '{}')
            ORDER BY tweets.views DESC
            LIMIT 500
        )
        SELECT tweet_text
        FROM top_tweets
        ORDER BY random()
        LIMIT 100;
    """
    return db.run_query(query)


def prepare_request(tweets):
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
