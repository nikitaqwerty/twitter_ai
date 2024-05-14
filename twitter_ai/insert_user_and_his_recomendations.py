from twitter.scraper import Scraper
from twitter.util import init_session
from utils.twitter_utils import extract_rest_ids, extract_users, get_twitter_scraper
from utils.db_utils import (
    get_db_connection,
    insert_user,
    insert_users_bulk,
    insert_user_recommendations,
    update_user_recommendations_status,
)
from utils.config import Config


def main():
    scraper = get_twitter_scraper()
    username = "coindesk"

    user_data = scraper.users([username])

    if (
        not user_data
        or "data" not in user_data[0]
        or "user" not in user_data[0]["data"]
    ):
        print("Error: No user data found or data is incomplete.")
        return

    user_object = user_data[0]["data"]["user"]["result"]
    user_id = user_object["rest_id"]

    with get_db_connection() as db:
        insert_user(db, user_object)

        recommended_users = scraper.recommended_users([user_id])

        for user_chunk in recommended_users:
            user_chunk_processed = user_chunk["data"]["connect_tab_timeline"][
                "timeline"
            ]["instructions"][2]["entries"][2]
            rest_ids = extract_rest_ids(user_chunk_processed)
            users = extract_users(user_chunk_processed)

            insert_users_query, users_params = insert_users_bulk(users)
            db.run_batch_query(insert_users_query, users_params)

            insert_recommendations_query, recommendations_params = (
                insert_user_recommendations(user_id, rest_ids)
            )
            db.run_batch_query(insert_recommendations_query, recommendations_params)

            update_status_query, status_params = update_user_recommendations_status(
                user_id
            )
            db.run_query(update_status_query, status_params)


if __name__ == "__main__":
    main()
