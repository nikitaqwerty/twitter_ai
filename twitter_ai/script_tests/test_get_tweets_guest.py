import os
from twitter.scraper import Scraper
from twitter.util import init_session


def fetch_user_tweets(username):
    email = os.getenv("TWITTER_EMAIL")
    login = os.getenv("TWITTER_LOGIN")
    password = os.getenv("TWITTER_PASSWORD")
    scraper = Scraper(email, login, password)

    try:
        user_data = scraper.users([username])
        if (
            not user_data
            or "data" not in user_data[0]
            or "user" not in user_data[0]["data"]
        ):
            print("Error: No user data found or data is incomplete.")
            return []

        user_id = user_data[0]["data"]["user"]["result"]["rest_id"]
        print(user_id)
        tweets = scraper.tweets([user_id])
        return tweets
    except (KeyError, IndexError) as e:
        print(f"Error: {e}. There might be an issue with the data structure.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    tweets = fetch_user_tweets("986sol")
    print(tweets)
