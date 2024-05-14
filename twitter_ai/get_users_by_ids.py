import os
from utils.twitter_utils import get_twitter_scraper, extract_users
from utils.db_utils import get_db_connection, insert_users_bulk
from utils.config import Config


def main():
    scraper = get_twitter_scraper()
    user_ids = ["1333467482", "906234475604037637", "899558268795842561"]

    # Fetch user data from Twitter API
    users_data = scraper.users_by_ids(user_ids)

    if not users_data:
        print("No user data fetched from Twitter.")
        return
    # Extract user data

    users = []
    for user_data in users_data[0]["data"]["users"]:
        try:
            entries = user_data["result"]
            users.append(entries)
        except KeyError as e:
            print(f"KeyError while extracting users: {e}")
            continue

    if not users:
        print("No valid user data extracted.")
        return

    # Insert user data into the database
    with get_db_connection() as db:
        insert_users_query, users_params = insert_users_bulk(users)
        db.run_batch_query(insert_users_query, users_params)

    print("User data successfully inserted into the database.")


if __name__ == "__main__":
    main()
