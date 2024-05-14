import os
from llm.llm_groq import GroqLLM
from utils.db_utils import get_db_connection
from utils.config import Config
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

prompt = """
YOU ARE AN ADVANCED 70 BILLION PARAMETER MODEL, TASKED WITH ANALYZING THE CURRENT CRYPTOCURRENCY MARKET SENTIMENT BASED ON 70 RECENT TWEETS FROM TODAY. YOUR GOAL IS TO EXTRACT THE THREE HOTTEST STORIES OR TRENDS FROM THESE TWEETS AND COMPOSE A CREATIVE AND ENGAGING TWEET THAT HIGHLIGHTS THESE TRENDS. YOUR TWEET SHOULD CAPTURE THE ESSENCE OF THE MARKET SENTIMENT AND BE INTERESTING AND INFORMATIVE TO READ.

**Key Objectives:**
- ANALYZE AND UNDERSTAND THE CONTENT AND SENTIMENT OF THE 80 TWEETS.
- IDENTIFY THE THREE MOST PROMINENT OR DISCUSSED STORIES OR TRENDS IN TODAY'S CRYPTOCURRENCY CONVERSATIONS.
- COMPOSE A SINGLE TWEET THAT IS CREATIVE, ENGAGING, AND REFLECTIVE OF THESE TRENDS.

**Chain of Thoughts:**
1. **Content Analysis:**
   - SCAN THROUGH THE 80 TWEETS TO GRASP THE OVERALL MARKET SENTIMENT AND KEY THEMES DISCUSSED.
   - EVALUATE THE FREQUENCY AND INTENSITY OF DISCUSSION AROUND DIFFERENT CRYPTOCURRENCY TOPICS.

2. **Identifying Key Stories:**
   - DETERMINE WHICH THREE STORIES OR TRENDS ARE THE MOST TALKED ABOUT OR HAVE THE GREATEST IMPACT ON TODAY'S MARKET.
   - CONSIDER THE RELEVANCE AND RECENTNESS OF THE INFORMATION.

3. **Creative Tweet Composition:**
   - CRAFT A TWEET THAT INCORPORATES THE IDENTIFIED TRENDS IN A CLEVER AND APPEALING WAY.
   - USE ENGAGING LANGUAGE AND CREATIVE EXPRESSIONS TO DRAW ATTENTION AND EVOKE INTEREST.

4. **Finalizing the Tweet:**
   - ENSURE THE TWEET IS NOT ONLY INFORMATIVE BUT ALSO CAPTIVATES THE AUDIENCE'S INTEREST.
   - DOUBLE-CHECK FOR CLARITY, GRAMMAR, AND OVERALL FLOW TO MAXIMIZE IMPACT.

**What Not To Do:**
- DO NOT SIMPLY LIST THE TRENDS WITHOUT PROVIDING INSIGHT OR ANALYSIS.
- AVOID USING JARGON THAT MAY CONFUSE OR ALIENATE NON-EXPERT READERS.
- NEVER IGNORE THE OVERALL SENTIMENT OF THE MARKET IN YOUR TWEET.
- DO NOT EXCEED THE TYPICAL LENGTH OF A TWEET, KEEP IT CONCISE AND TO THE POINT.
- NEVER POST CONTENT THAT IS DULL OR LACKS CREATIVITY.


**Context**
"""


def fetch_tweets_from_db():
    query = """
        SELECT tweet_text 
        FROM tweets
        WHERE 
        (retweeted_tweet IS NULL OR retweeted_tweet = '{}'::jsonb) 
        AND (quoted_tweet IS NULL OR quoted_tweet = '{}'::jsonb)  
        AND has_symbols = TRUE
        AND length(tweet_text) > 120
        ORDER BY created_at DESC
        LIMIT 70;
    """
    with get_db_connection() as db:
        return db.run_query(query)


def summarize_tweets(tweets, groq_llm):
    tweets = "\n=============\n".join(list([tweet[0] for tweet in tweets]))
    print("Input: ", tweets)

    summary = groq_llm.get_response(f"{prompt} \n\n {tweets}")

    return summary


def main():
    # Fetch tweets from the database
    tweets = fetch_tweets_from_db()
    if not tweets:
        logging.info("No tweets found that match the criteria.")
        return

    # Initialize GroqLLM
    groq_llm = GroqLLM(Config.GROQ_API_KEY)

    # Summarize tweets
    tweet_summary = summarize_tweets(tweets, groq_llm)
    print("Output: ", tweet_summary)


if __name__ == "__main__":
    main()
