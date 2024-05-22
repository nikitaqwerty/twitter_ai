import os
import logging
import pyperclip
from utils.db_utils import get_db_connection
from utils.config import Config

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
- NEVER USE # HASHTAGS AT ALL, IF YOU USE AT LEAST ONE HASHTAG IN THE TWEET I WILL KILL 100 KITTENS

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

prompt = """
YOU ARE A 70 BILLION PARAMETER LANGUAGE MODEL, THE WORLD'S MOST CREATIVE AND ENGAGING CRYPTO TWITTER USER. YOUR TASK IS TO READ THROUGH 75 RANDOM TWEETS ABOUT CRYPTOCURRENCIES, WEB3, AND CRYPTO POSTED TODAY. USING THIS CONTEXT, YOU WILL GENERATE A RANDOM, CREATIVE, AND PROVOCATIVE TWEET ABOUT CRYPTOCURRENCIES OR WEB3. YOUR TWEET SHOULD APPEAR CASUAL AND AUTHENTIC, AS IF WRITTEN BY A REGULAR CRYPTO TWITTER USER, NOT A PROFESSIONAL. DO NOT USE THE # SIGN IN YOUR TWEET.

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
- DO NOT USE TECHNICAL JARGON OR COMPLEX LANGUAGE.
- AVOID CREATING A TWEET THAT IS BORING OR UNORIGINAL.
- DO NOT DISMISS THE TRENDS OR SENTIMENTS FOUND IN THE PROVIDED TWEETS.
- AVOID OFFENSIVE OR INAPPROPRIATE CONTENT THAT COULD BE HARMFUL.
- NEVER USE THE # SIGN IN YOUR TWEET.

EXAMPLE TWEET TEMPLATE:
"Just saw a whale dump $ETH for $DOGE 🚀🌕. If this isn't a sign of the times, IDK what is! HODL"

**Instructions:**
1. Summarize the 75 provided tweets about crypto today.
2. Use the summarized context to write an engaging and provocative tweet.
3. Ensure the tweet looks like it was written by a regular crypto Twitter user.
4. Do not use the # sign in the tweet.

START:

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
        AND tweets.created_at > '2024-05-21'
        ORDER BY tweets.views DESC
        LIMIT 75;
    """
    with get_db_connection() as db:
        return db.run_query(query)


def prepare_request(tweets):
    tweets_text = "\n=============\n".join([tweet[0] for tweet in tweets])
    request = f"{prompt} \n\n {tweets_text}"
    return request


def main():
    # Fetch tweets from the database
    tweets = fetch_tweets_from_db()
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
