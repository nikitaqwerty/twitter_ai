import os
from twitter.scraper import Scraper
from dotenv import load_dotenv

load_dotenv()


def get_twitter_scraper():
    email = os.getenv("TWITTER_EMAIL")
    login = os.getenv("TWITTER_LOGIN")
    password = os.getenv("TWITTER_PASSWORD")
    return Scraper(email, login, password)


def extract_rest_ids(entries):
    return [
        item["item"]["itemContent"]["user_results"]["result"]["rest_id"]
        for entry in entries
        for item in entry["content"]["items"]
        if "socialContext" not in item["item"]["itemContent"]
    ]


def extract_users(entries):
    return [
        item["item"]["itemContent"]["user_results"]["result"]
        for entry in entries
        for item in entry["content"]["items"]
        if "socialContext" not in item["item"]["itemContent"]
    ]
