import unittest
import os
import sys

# Ensure that the path to the utilities and other dependencies is available
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import Database
from utils.db_utils import get_most_mentioned_new_users


class TestGetMostMentionedNewUsers(unittest.TestCase):
    def setUp(self):
        self.db = Database(
            host="localhost",
            database="crypto-twitter",
            user="myuser",
            password="mypassword",
        )
        self.db.__enter__()

    def tearDown(self):
        self.db.__exit__(None, None, None)

    def test_get_most_mentioned_new_users(self):
        try:
            result = get_most_mentioned_new_users(self.db, limit_users=5)
            print(result)
            self.assertIsInstance(result, list)
            for user_id_tuple in result:
                self.assertIsInstance(user_id_tuple, tuple)
                self.assertIsInstance(
                    user_id_tuple[0], str
                )  # Assuming user IDs are strings
        except Exception as e:
            self.fail(f"Exception occurred: {e}")


if __name__ == "__main__":
    unittest.main()
