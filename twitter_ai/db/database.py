import psycopg2


class Database:
    def __init__(self, host, database, user, password):
        self.conn_params = {
            "host": host,
            "database": database,
            "user": user,
            "password": password,
        }
        self.connection = None
        self.cursor = None

    def __enter__(self):
        try:
            self.connection = psycopg2.connect(**self.conn_params)
            self.cursor = self.connection.cursor()
        except psycopg2.Error as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None
            self.cursor = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            if exc_type is not None:
                self.connection.rollback()
            else:
                self.connection.commit()
            self.connection.close()

    def run_query(self, query, params=None):
        if self.cursor is None:
            raise AttributeError(
                "Cursor is not initialized. Check the database connection."
            )
        self.cursor.execute(query, params or ())
        self.connection.commit()  # Ensure that changes are committed
        try:
            return self.cursor.fetchall()
        except psycopg2.ProgrammingError:
            return None

    def run_batch_query(self, query, params_list):
        if self.cursor is None:
            raise AttributeError(
                "Cursor is not initialized. Check the database connection."
            )
        self.cursor.executemany(query, params_list)
        self.connection.commit()  # Ensure that changes are committed

        return self.cursor.rowcount

    def run_insert_query(self, query, params_list):
        if not isinstance(params_list[0], tuple):
            params_list = [params_list]
        if self.cursor is None:
            raise AttributeError(
                "Cursor is not initialized. Check the database connection."
            )
        self.cursor.executemany(query, params_list)
        self.connection.commit()
        return self.cursor.rowcount

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()


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


def create_actions_table(db):
    query = """
        CREATE TABLE IF NOT EXISTS actions (
            action_id SERIAL PRIMARY KEY,
            action_account_id VARCHAR(255) NOT NULL,
            action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('like', 'tweet', 'retweet', 'reply', 'quote', 'follow')),
            tweet_id VARCHAR(255),
            target_tweet_id VARCHAR(255),
            target_user_id VARCHAR(255),
            llm_raw_text TEXT,
            llm_model VARCHAR(255),
            llm_prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_tweet_id) REFERENCES tweets(tweet_id) ON DELETE CASCADE,
            FOREIGN KEY (target_user_id) REFERENCES users(rest_id) ON DELETE CASCADE
        );
    """
    db.run_query(query)


def create_all_tables(db):
    create_users_table(db)
    create_tweets_table(db)
    create_user_recommendations_table(db)
    create_actions_table(db)
    print("All tables created successfully.")


def drop_all_tables(db):
    drop_queries = [
        "DROP TABLE IF EXISTS actions CASCADE;",
        "DROP TABLE IF EXISTS tweets CASCADE;",
        "DROP TABLE IF EXISTS user_recommendations CASCADE;",
        "DROP TABLE IF EXISTS users CASCADE;",
    ]
    for query in drop_queries:
        db.run_query(query)
        print(f"Successfully dropped table: {query}")
