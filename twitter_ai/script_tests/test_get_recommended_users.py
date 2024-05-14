import os
from twitter.scraper import Scraper
from twitter.util import init_session

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    email = os.getenv("TWITTER_EMAIL")
    login = os.getenv("TWITTER_LOGIN")
    password = os.getenv("TWITTER_PASSWORD")
    scraper = Scraper(email, login, password)

    user_ids = [
        918804624303382528,
        906234475604037637,
        899558268795842561,
        79714172,
        878219545785372673,
        983993370048630785,
        942999039192186882,
        1484112393361891328,
        2327407569,
        4107711,
        868760548674072576,
    ]

    recommended_users = scraper.recommended_users(user_ids)
    print(recommended_users)
