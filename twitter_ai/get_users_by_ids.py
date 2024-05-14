import os
from twitter.scraper import Scraper
from db.database import Database
from utils.twitter_utils import extract_rest_ids, extract_users


def main():
    email = os.getenv("TWITTER_EMAIL")
    login = os.getenv("TWITTER_LOGIN")
    password = os.getenv("TWITTER_PASSWORD")
    db_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME", "crypto-twitter"),
        "user": os.getenv("DB_USER", "myuser"),
        "password": os.getenv("DB_PASSWORD", "mypassword"),
    }

    scraper = Scraper(email, login, password)
    user_ids = ["918804624303382528", "906234475604037637", "899558268795842561"]

    users = scraper.users_by_ids(user_ids)

    db = Database(**db_params)
    db.connect()

    db.close()


if __name__ == "__main__":
    main()
