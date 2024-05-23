import os
import json
import datetime
from db.database import Database
from utils.config import configure_logging

configure_logging()


def get_db_connection():
    db_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME", "crypto-twitter"),
        "user": os.getenv("DB_USER", "myuser"),
        "password": os.getenv("DB_PASSWORD", "mypassword"),
    }
    return Database(**db_params)


def insert_action(
    db,
    action_account_id,
    action_type,
    tweet_id=None,
    target_tweet_id=None,
    target_user_id=None,
    llm_raw_text=None,
    llm_model=None,
    llm_prompt=None,
):
    query = """
        INSERT INTO actions (
            action_account_id, action_type, tweet_id, target_tweet_id, target_user_id, llm_raw_text, llm_model, llm_prompt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """
    params = (
        action_account_id,
        action_type,
        tweet_id,
        target_tweet_id,
        target_user_id,
        llm_raw_text,
        llm_model,
        llm_prompt,
    )
    db.run_query(query, params)


def insert_users(db, user_results):
    query = """
        INSERT INTO users (
            rest_id, username, name, profile_image_url_https, profile_banner_url, description, location,
            followers_count, friends_count, favourites_count, statuses_count, created_at, is_blue_verified,
            is_translator, verified, professional_type, category, tweets_parsed, tweets_parsed_last_timestamp,
            recommendations_pulled, recommendations_pulled_last_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (rest_id) DO UPDATE SET
            username = EXCLUDED.username,
            name = EXCLUDED.name,
            profile_image_url_https = EXCLUDED.profile_image_url_https,
            profile_banner_url = EXCLUDED.profile_banner_url,
            description = EXCLUDED.description,
            location = EXCLUDED.location,
            followers_count = EXCLUDED.followers_count,
            friends_count = EXCLUDED.friends_count,
            favourites_count = EXCLUDED.favourites_count,
            statuses_count = EXCLUDED.statuses_count,
            created_at = EXCLUDED.created_at,
            is_blue_verified = EXCLUDED.is_blue_verified,
            is_translator = EXCLUDED.is_translator,
            verified = EXCLUDED.verified,
            professional_type = EXCLUDED.professional_type,
            category = EXCLUDED.category,
            lastmodified = CURRENT_TIMESTAMP;
    """
    if not isinstance(user_results, list):
        user_results = [user_results]

    params_list = []
    for user_result in user_results:
        legacy = user_result.get("legacy", {})
        professional = user_result.get("professional", {})
        category_name = ""
        if (
            professional.get("category")
            and isinstance(professional.get("category"), list)
            and professional["category"]
        ):
            if isinstance(professional["category"][0], dict):
                category_name = professional["category"][0].get("name", "")

        params = (
            user_result.get("rest_id", ""),
            legacy.get("screen_name", ""),
            legacy.get("name", ""),
            legacy.get("profile_image_url_https", ""),
            legacy.get("profile_banner_url", ""),
            legacy.get("description", ""),
            legacy.get("location", ""),
            legacy.get("followers_count", 0),
            legacy.get("friends_count", 0),
            legacy.get("favourites_count", 0),
            legacy.get("statuses_count", 0),
            legacy.get("created_at", None),
            user_result.get("is_blue_verified", False),
            legacy.get("is_translator", False),
            legacy.get("verified", False),
            professional.get("professional_type", ""),
            category_name,
            False,  # Default value for tweets_parsed
            None,  # Default value for tweets_parsed_last_timestamp
            False,  # Default value for recommendations_pulled
            None,  # Default value for recommendations_pulled_last_timestamp
        )
        params_list.append(params)

    db.run_insert_query(query, params_list)
    return db.cursor.rowcount


def insert_tweets(db, tweet_results_list):
    query = """
        INSERT INTO tweets (
            tweet_id, tweet_text, likes, retweets, replies, quotes, bookmarks, created_at, views, has_media,
            has_user_mentions, users_mentioned, has_urls, has_hashtags, has_symbols, symbols, user_id,
            possibly_sensitive, lang, source, media_urls, media_types, media_sizes, retweeted_tweet, quoted_tweet, card
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tweet_id) DO UPDATE SET
            tweet_text = EXCLUDED.tweet_text,
            likes = EXCLUDED.likes,
            retweets = EXCLUDED.retweets,
            replies = EXCLUDED.replies,
            quotes = EXCLUDED.quotes,
            bookmarks = EXCLUDED.bookmarks,
            created_at = EXCLUDED.created_at,
            views = EXCLUDED.views,
            has_media = EXCLUDED.has_media,
            has_user_mentions = EXCLUDED.has_user_mentions,
            users_mentioned = EXCLUDED.users_mentioned,
            has_urls = EXCLUDED.has_urls,
            has_hashtags = EXCLUDED.has_hashtags,
            has_symbols = EXCLUDED.has_symbols,
            symbols = EXCLUDED.symbols,
            user_id = EXCLUDED.user_id,
            possibly_sensitive = EXCLUDED.possibly_sensitive,
            lang = EXCLUDED.lang,
            source = EXCLUDED.source,
            media_urls = EXCLUDED.media_urls,
            media_types = EXCLUDED.media_types,
            media_sizes = EXCLUDED.media_sizes,
            retweeted_tweet = EXCLUDED.retweeted_tweet,
            quoted_tweet = EXCLUDED.quoted_tweet,
            card = EXCLUDED.card,
            lastmodified = CURRENT_TIMESTAMP;
    """
    if not isinstance(tweet_results_list, list):
        tweet_results_list = [tweet_results_list]

    params_list = []
    for tweet_results in tweet_results_list:
        legacy = tweet_results["legacy"]
        media_entities = legacy.get("extended_entities", {}).get("media", [])

        media_urls = [media["media_url_https"] for media in media_entities]
        media_types = [media["type"] for media in media_entities]
        media_sizes = {media["media_key"]: media["sizes"] for media in media_entities}

        params = (
            tweet_results["rest_id"],
            tweet_results.get("note_tweet", {})
            .get("note_tweet_results", {})
            .get("result", {})
            .get("text", legacy.get("full_text", "")),
            legacy.get("favorite_count", 0),
            legacy.get("retweet_count", 0),
            legacy.get("reply_count", 0),
            legacy.get("quote_count", 0),
            legacy.get("bookmark_count", 0),
            legacy.get("created_at", None),
            tweet_results.get("views", {}).get("count", 0),
            "media" in legacy.get("extended_entities", {}),
            bool(legacy.get("entities", {}).get("user_mentions", [])),
            [
                mention["id_str"]
                for mention in legacy.get("entities", {}).get("user_mentions", [])
            ],
            bool(legacy.get("entities", {}).get("urls", [])),
            bool(legacy.get("entities", {}).get("hashtags", [])),
            bool(legacy.get("entities", {}).get("symbols", [])),
            [
                symbol["text"]
                for symbol in legacy.get("entities", {}).get("symbols", [])
            ],
            legacy.get("user_id_str", ""),
            legacy.get("possibly_sensitive", False),
            legacy.get("lang", ""),
            tweet_results.get("source", ""),
            media_urls,  # Already a list
            media_types,  # Already a list
            json.dumps(media_sizes),
            json.dumps(legacy.get("retweeted_status_result", {})),
            json.dumps(tweet_results.get("quoted_status_result", {})),
            json.dumps(tweet_results.get("card", {})),
        )
        params_list.append(params)

    db.run_insert_query(query, params_list)
    return db.cursor.rowcount


def insert_user_recommendations(db, rest_id, recommended_user_ids):
    query = """
        INSERT INTO user_recommendations (rest_id, recommended_user_id)
        VALUES (%s, %s)
        ON CONFLICT (rest_id, recommended_user_id) DO NOTHING;
    """
    if not isinstance(recommended_user_ids, list):
        recommended_user_ids = [recommended_user_ids]

    params_list = [(rest_id, recommended_id) for recommended_id in recommended_user_ids]

    db.run_insert_query(query, params_list)


def update_user_tweets_status(db, rest_ids):
    """
    Updates the status of user tweets parsing for multiple users in the database.

    Args:
        db (Database): The database connection object.
        rest_ids (list): A list of user rest IDs whose status needs to be updated.
    """
    # Generate a list of placeholders for the rest_ids
    placeholders = ", ".join(["%s"] * len(rest_ids))

    query = f"""
        UPDATE users
        SET tweets_parsed = %s, tweets_parsed_last_timestamp = %s
        WHERE rest_id IN ({placeholders});
    """

    params = (True, datetime.datetime.utcnow(), *rest_ids)
    db.run_query(query, params)


def update_user_recommendations_status(db, rest_id):
    query = """
        UPDATE users
        SET recommendations_pulled = %s, recommendations_pulled_last_timestamp = %s
        WHERE rest_id = %s;
    """
    params = (True, datetime.datetime.utcnow(), rest_id)
    db.run_query(query, params)


def get_most_mentioned_users(db, limit_users=5):
    query = """
        SELECT mentioned_user_id
        FROM (
            SELECT unnest(users_mentioned) AS mentioned_user_id
            FROM tweets
        ) AS mentioned_users
        GROUP BY mentioned_user_id
        ORDER BY COUNT(*) DESC
        LIMIT %s;
    """
    return db.run_query(query, (limit_users,))


def get_most_mentioned_new_users(db, limit_users=5):
    query = """
        WITH mentioned_users AS (
            SELECT unnest(t.users_mentioned) AS mentioned_user_id
            FROM tweets t
            JOIN users u ON t.user_id = u.rest_id
            WHERE u.llm_check_score > 5
        )
        SELECT mentioned_user_id
        FROM mentioned_users
        WHERE mentioned_user_id NOT IN (SELECT rest_id FROM users)
        AND length(mentioned_user_id) > 3
        GROUP BY mentioned_user_id
        ORDER BY COUNT(*) DESC
        LIMIT %s;
    """
    return db.run_query(query, (limit_users,))
