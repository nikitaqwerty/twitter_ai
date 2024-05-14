import os
from twitter.scraper import Scraper
from db.database import Database


def extract_rest_ids(entries):
    return [
        item["item"]["itemContent"]["user_results"]["result"]["rest_id"]
        for entry in entries
        for item in entry["content"]["items"]
        if not "socialContext" in item["item"]["itemContent"]
    ]


def extract_users(entries):
    return [
        item["item"]["itemContent"]["user_results"]["result"]
        for entry in entries
        for item in entry["content"]["items"]
        if not "socialContext" in item["item"]["itemContent"]
    ]


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
