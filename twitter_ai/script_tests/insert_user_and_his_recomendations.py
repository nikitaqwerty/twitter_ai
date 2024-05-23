from twitter.scraper import Scraper
from twitter.util import init_session
from utils.twitter_utils import extract_users_and_ids, get_twitter_scraper
from utils.db_utils import (
    get_db_connection,
    insert_users,
    insert_user_recommendations,
    update_user_recommendations_status,
)
from utils.config import Config


def main():
    scraper = get_twitter_scraper()
    username = "retiredchaddev"

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
        insert_users(db, user_object)

        recommended_users = scraper.recommended_users([user_id])

        for user_chunk in recommended_users:
            entries = user_chunk["data"]["connect_tab_timeline"]["timeline"][
                "instructions"
            ][2]["entries"]
            if not isinstance(entries, list):
                entries = [entries]
            user_chunk_processed = []
            for entry in entries:
                if "mergeallcandidatesmodule" in entry["entryId"]:
                    user_chunk_processed.append(entry)

            users, rest_ids = extract_users_and_ids(user_chunk_processed)

            inserted_user_count = insert_users(db, users)

            inserted_recommendations_count = insert_user_recommendations(
                db, user_id, rest_ids
            )

            update_user_recommendations_status(db, user_id)


if __name__ == "__main__":
    main()
