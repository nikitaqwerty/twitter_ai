from utils.twitter_utils import get_twitter_scraper, extract_users_and_ids
from utils.db_utils import (
    get_db_connection,
    insert_users_bulk,
    insert_user_recommendations,
    update_user_recommendations_status,
)


def main():
    scraper = get_twitter_scraper()
    user_ids = ["270119330"]

    recommended_users = scraper.recommended_users(user_ids)

    with get_db_connection() as db:
        for user_chunk, user_id in zip(recommended_users, user_ids):
            entries = user_chunk["data"]["connect_tab_timeline"]["timeline"][
                "instructions"
            ][2]["entries"]
            users, rest_ids = extract_users_and_ids(entries)

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
