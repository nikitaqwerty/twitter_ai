import os
import json
import datetime
from contextlib import contextmanager
from db.database import Database


def get_db_connection():
    db_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME", "crypto-twitter"),
        "user": os.getenv("DB_USER", "myuser"),
        "password": os.getenv("DB_PASSWORD", "mypassword"),
    }
    return Database(**db_params)


def create_users_table(db):
    query = """
        CREATE TABLE IF NOT EXISTS users (
            rest_id VARCHAR(255) PRIMARY KEY,
            username VARCHAR(255),
            name VARCHAR(255),
            profile_image_url_https TEXT,
            profile_banner_url TEXT,
            description TEXT,
            location VARCHAR(255),
            followers_count INTEGER,
            friends_count INTEGER,
            favourites_count INTEGER,
            statuses_count INTEGER,
            created_at TIMESTAMP,
            is_blue_verified BOOLEAN,
            is_translator BOOLEAN,
            verified BOOLEAN,
            professional_type VARCHAR(255),
            category VARCHAR(255),
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lastmodified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tweets_parsed BOOLEAN DEFAULT FALSE,
            tweets_parsed_last_timestamp TIMESTAMP DEFAULT NULL,
            recommendations_pulled BOOLEAN DEFAULT FALSE,
            recommendations_pulled_last_timestamp TIMESTAMP DEFAULT NULL,
            llm_check_score FLOAT DEFAULT NULL,
            llm_check_last_timestamp TIMESTAMP DEFAULT NULL
        );
    """
    db.run_query(query)


def create_tweets_table(db):
    query = """
        CREATE TABLE IF NOT EXISTS tweets (
            tweet_id VARCHAR(255) PRIMARY KEY,
            tweet_text TEXT,
            likes INTEGER,
            retweets INTEGER,
            replies INTEGER,
            quotes INTEGER,
            bookmarks INTEGER,
            created_at TIMESTAMP,
            views INTEGER,
            has_media BOOLEAN,
            has_user_mentions BOOLEAN,
            users_mentioned TEXT[],
            has_urls BOOLEAN,
            has_hashtags BOOLEAN,
            has_symbols BOOLEAN,
            symbols TEXT[],
            user_id VARCHAR(255) REFERENCES users(rest_id),
            possibly_sensitive BOOLEAN,
            lang VARCHAR(10),
            source TEXT,
            media_urls TEXT[],
            media_types TEXT[],
            media_sizes JSONB,
            retweeted_tweet JSONB,
            quoted_tweet JSONB,
            card JSONB,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lastmodified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    db.run_query(query)


def create_user_recommendations_table(db):
    query = """
        CREATE TABLE IF NOT EXISTS user_recommendations (
            rest_id VARCHAR(255) NOT NULL,
            recommended_user_id VARCHAR(255) NOT NULL,
            PRIMARY KEY (rest_id, recommended_user_id),
            FOREIGN KEY (rest_id) REFERENCES users(rest_id) ON DELETE CASCADE,
            FOREIGN KEY (recommended_user_id) REFERENCES users(rest_id) ON DELETE CASCADE
        );
    """
    db.run_query(query)


def create_all_tables(db):
    create_users_table(db)
    create_tweets_table(db)
    create_user_recommendations_table(db)
    print("All tables created successfully.")


def drop_all_tables(db):
    drop_queries = [
        "DROP TABLE IF EXISTS tweets CASCADE;",
        "DROP TABLE IF EXISTS user_recommendations CASCADE;",
        "DROP TABLE IF EXISTS users CASCADE;",
    ]
    for query in drop_queries:
        db.run_query(query)
        print(f"Successfully dropped table: {query}")


def insert_user(db, user_result):
    query = """
        INSERT INTO users (
            rest_id, username, name, profile_image_url_https, profile_banner_url, description, location,
            followers_count, friends_count, favourites_count, statuses_count, created_at, is_blue_verified,
            is_translator, verified, professional_type, category, tweets_parsed, tweets_parsed_last_timestamp,
            recommendations_pulled, recommendations_pulled_last_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (rest_id) DO NOTHING;
    """
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
    db.run_query(query, params)


def insert_users_bulk(user_results):
    query = """
        INSERT INTO users (
            rest_id, username, name, profile_image_url_https, profile_banner_url, description, location,
            followers_count, friends_count, favourites_count, statuses_count, created_at, is_blue_verified,
            is_translator, verified, professional_type, category, tweets_parsed, tweets_parsed_last_timestamp,
            recommendations_pulled, recommendations_pulled_last_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (rest_id) DO NOTHING
        RETURNING rest_id;
    """
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
    return query, params_list


def insert_tweet(db, tweet_results):
    query = """
        INSERT INTO tweets (
            tweet_id, tweet_text, likes, retweets, replies, quotes, bookmarks, created_at, views, has_media,
            has_user_mentions, users_mentioned, has_urls, has_hashtags, has_symbols, symbols, user_id,
            possibly_sensitive, lang, source, media_urls, media_types, media_sizes, retweeted_tweet, quoted_tweet, card
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tweet_id) DO NOTHING;
    """
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
        [symbol["text"] for symbol in legacy.get("entities", {}).get("symbols", [])],
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
    db.run_query(query, params)


def insert_tweets_bulk(db, tweet_results_list):
    query = """
        INSERT INTO tweets (
            tweet_id, tweet_text, likes, retweets, replies, quotes, bookmarks, created_at, views, has_media,
            has_user_mentions, users_mentioned, has_urls, has_hashtags, has_symbols, symbols, user_id,
            possibly_sensitive, lang, source, media_urls, media_types, media_sizes, retweeted_tweet, quoted_tweet, card
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tweet_id) DO NOTHING;
    """
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
    db.run_batch_query(query, params_list)


def insert_user_recommendations(rest_id, recommended_user_ids):
    query = """
        INSERT INTO user_recommendations (rest_id, recommended_user_id)
        VALUES (%s, %s)
        ON CONFLICT (rest_id, recommended_user_id) DO NOTHING;
    """
    params = [(rest_id, recommended_id) for recommended_id in recommended_user_ids]
    return query, params


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


def update_user_recommendations_status(rest_id):
    query = """
        UPDATE users
        SET recommendations_pulled = %s, recommendations_pulled_last_timestamp = %s
        WHERE rest_id = %s;
    """
    params = (True, datetime.datetime.utcnow(), rest_id)
    return query, params


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
