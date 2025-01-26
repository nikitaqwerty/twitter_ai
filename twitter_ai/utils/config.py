# config.py

import os
from dotenv import load_dotenv
import logging


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],  # Log to sys.stderr by default
    )


load_dotenv()


class Config:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "crypto_twitter")
    DB_USER = os.getenv("DB_USER", "myuser")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "mypassword")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    COOKIES_DIR = os.getenv("COOKIES_DIR")

    @staticmethod
    def get_twitter_accounts():
        accounts = []
        i = 1
        while os.getenv(f"TWITTER_EMAIL_{i}"):
            accounts.append(
                {
                    "email": os.getenv(f"TWITTER_EMAIL_{i}"),
                    "login": os.getenv(f"TWITTER_LOGIN_{i}"),
                    "password": os.getenv(f"TWITTER_PASSWORD_{i}"),
                }
            )
            i += 1
        return accounts
