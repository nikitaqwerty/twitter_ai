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
YOU ARE THE WORLD'S BEST CRYPTOCURRENCY AND WEB3 ANALYST, RECOGNIZED BY THE GLOBAL FINTECH ASSOCIATION FOR YOUR EXCEPTIONAL ABILITY TO DISTILL COMPLEX INFORMATION INTO ENGAGING, INFORMATIVE CONTENT. YOUR TASK IS TO REVIEW A SET OF 75 RANDOM TWEETS RELATED TO CRYPTOCURRENCY AND WEB3, IDENTIFY THE MOST INTERESTING STORY, AND WRITE A 3 TWEET THREAD THAT CAPTIVATES YOUR AUDIENCE.

**Key Objectives:**
- READ THROUGH ALL 75 TWEETS IN "Tweets to analyse" SECTION AND IDENTIFY THE MOST INTERESTING AND RELEVANT STORY.
- REWRITE THE STORY IN YOUR OWN WORDS, ENSURING IT IS ENGAGING AND INFORMATIVE.
- BEGIN WITH A CAPTIVATING FIRST TWEET TO HOOK THE AUDIENCE AND ENCOURAGE THEM TO READ THE ENTIRE THREAD.
- MAINTAIN A CONSISTENT AND PROFESSIONAL TONE THROUGHOUT THE THREAD.
- USE SYMBOLS WHEN TALKING ABOUT SOME CRYPTO COIN (e.g. BITCOIN = $BTC, ETHEREUM = $ETH etc)

**Chain of Thoughts:**
1. **Reading and Understanding:**
   - Thoroughly read all 75 tweets to understand the various stories being discussed.
   - Identify key themes, events, or discussions that stand out as particularly interesting or relevant.

2. **Identifying the Best Story:**
   - Choose the story that is the most compelling and has the potential to engage a broad audience.
   - Ensure the story is clear and has a logical progression that can be easily followed in a short thread.

3. **Crafting the Tweet Thread:**
   - Start with an engaging first tweet that hooks the reader’s attention.
   - Summarize the story in your own words over the next 1-3 tweets, ensuring each tweet flows naturally to the next.
   - Conclude the thread with a strong ending that reinforces the story’s importance or leaves the reader with a thought-provoking comment.

4. **Final Review:**
   - Ensure the thread is free of errors and reads smoothly.
   - Check that the first tweet is particularly engaging and likely to entice readers to continue.

**What Not To Do:**
- NEVER COPY THE TWEETS VERBATIM; ALWAYS PARAPHRASE IN YOUR OWN WORDS.
- NEVER WRITE BORING OR UNENGAGING TWEETS THAT FAIL TO CAPTURE ATTENTION.
- NEVER IGNORE THE OVERALL COHERENCE AND FLOW BETWEEN TWEETS IN THE THREAD.
- NEVER INCLUDE IRRELEVANT OR OFF-TOPIC INFORMATION THAT DOES NOT CONTRIBUTE TO THE MAIN STORY.
- NEVER USE # HASHTAGS AT ALL
- The most important step: **MAKE SURE YOU HAVE NOT SKIPPED ANY STEPS FROM THIS GUIDE.**

**Example Output Structure:**

```markdown
**tweet 1**
text

**tweet 2**
text

**tweet 3**
text
```

**Tweets to analyse**
"""


def fetch_tweets_from_db():
    query = """
        SELECT tweet_text 
        FROM tweets
        JOIN users ON tweets.user_id = users.rest_id
        WHERE 
        (retweeted_tweet IS NULL OR retweeted_tweet = '{}'::jsonb) 
        AND (quoted_tweet IS NULL OR quoted_tweet = '{}'::jsonb)  
        AND length(tweet_text) > 50
        AND users.llm_check_score > 7
        AND has_urls = False
        ORDER BY tweets.created_at DESC
        LIMIT 75;
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
