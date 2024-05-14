import os
from twitter.scraper import Scraper
from twitter.util import init_session
from db.database import (
    Database,
    insert_user,
    insert_users_bulk,
    insert_user_recommendations,
    update_user_recommendations_status,
)


def extract_rest_ids(data):
    screen_names = []
    entries = data["data"]["connect_tab_timeline"]["timeline"]["instructions"][2][
        "entries"
    ]
    for entry in entries:
        items = entry["content"]["items"]
        for item in items:
            screen_name = item["item"]["itemContent"]["user_results"]["result"][
                "rest_id"
            ]
            if not "socialContext" in item["item"]["itemContent"]:
                screen_names.append(screen_name)
    return screen_names


def extract_users(data):
    users = []
    entries = data["data"]["connect_tab_timeline"]["timeline"]["instructions"][2][
        "entries"
    ]
    for entry in entries:
        items = entry["content"]["items"]
        for item in items:
            user = item["item"]["itemContent"]["user_results"]["result"]
            if not "socialContext" in item["item"]["itemContent"]:
                users.append(user)
    return users


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    db = Database(
        os.getenv("DB_HOST"),
        os.getenv("DB_NAME"),
        os.getenv("DB_USER"),
        os.getenv("DB_PASSWORD"),
    )
    db.connect()

    email = os.getenv("TWITTER_EMAIL")
    login = os.getenv("TWITTER_LOGIN")
    password = os.getenv("TWITTER_PASSWORD")
    scraper = Scraper(email, login, password)
    username = "blknoiz06"

    user_data = scraper.users([username])

    if (
        not user_data
        or "data" not in user_data[0]
        or "user" not in user_data[0]["data"]
    ):
        print("Error: No user data found or data is incomplete.")

    user_object = user_data[0]["data"]["user"]["result"]
    user_id = user_object["rest_id"]
    insert_user(db, user_object)

    recommended_users = scraper.recommended_users([user_id])

    for user_chunk, user_id in zip(recommended_users, [user_id]):
        rest_ids = extract_rest_ids(user_chunk)
        users = extract_users(user_chunk)

        insert_users_bulk(db, users)
        insert_user_recommendations(db, user_id, rest_ids)
        update_user_recommendations_status(db, user_id)

    db.close()
