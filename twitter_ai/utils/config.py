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
    TWITTER_EMAIL = os.getenv("TWITTER_EMAIL")
    TWITTER_LOGIN = os.getenv("TWITTER_LOGIN")
    TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "crypto-twitter")
    DB_USER = os.getenv("DB_USER", "myuser")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "mypassword")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    COOKIES_DIR = os.getenv("COOKIES_DIR")
