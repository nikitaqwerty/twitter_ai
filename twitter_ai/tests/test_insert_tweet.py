import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import insert_tweet


class TestInsertTweet(unittest.TestCase):
    @patch("utils.db_utils.Database")
    def test_insert_tweet_basic(self, MockDatabase):
        # Create a mock database instance
        mock_db_instance = MockDatabase.return_value
        mock_db_instance.run_query = MagicMock()

        # Prepare data
        tweet_results = {
            "rest_id": "1234567890",
            "note_tweet": {
                "note_tweet_results": {"result": {"text": "Sample tweet text"}}
            },
            "legacy": {
                "full_text": "This should not be used in this test",
                "favorite_count": 10,
                "retweet_count": 5,
                "reply_count": 2,
                "quote_count": 1,
                "bookmark_count": 0,
                "created_at": "Thu May 10 15:29:45 +0000 2018",
                "user_id_str": "987654321",
                "possibly_sensitive": False,
                "lang": "en",
                "favorited": True,
                "retweeted": False,
                "entities": {
                    "media": [],
                    "user_mentions": [],
                    "urls": [],
                    "hashtags": [],
                    "symbols": [],
                },
            },
            "views": {"count": 50},
            "source": "<a href='http://twitter.com'>Twitter Web Client</a>",
        }

        # Run the test function
        insert_tweet(mock_db_instance, tweet_results)

        # Check if run_query was called (which includes commit)
        mock_db_instance.run_query.assert_called_once()

    @patch("utils.db_utils.Database")
    def test_tweet_with_no_extended_entities(self, MockDatabase):
        # Create a mock database instance
        mock_db_instance = MockDatabase.return_value
        mock_db_instance.run_query = MagicMock()

        # Prepare data
        tweet_results = {
            "rest_id": "1234567890",
            "legacy": {
                "full_text": "This is a sample tweet without extended entities.",
                "favorite_count": 10,
                "retweet_count": 5,
                "reply_count": 2,
                "quote_count": 1,
                "bookmark_count": 0,
                "created_at": "Thu May 10 15:29:45 +0000 2018",
                "user_id_str": "987654321",
                "possibly_sensitive": False,
                "lang": "en",
                "favorited": True,
                "retweeted": False,
                "entities": {
                    "media": [],
                    "user_mentions": [],
                    "urls": [],
                    "hashtags": [],
                    "symbols": [],
                },
            },
            "views": {"count": 50},
            "source": "<a href='http://twitter.com'>Twitter Web Client</a>",
        }

        # Run the test function
        insert_tweet(mock_db_instance, tweet_results)

        # Check if run_query was called (which includes commit)
        mock_db_instance.run_query.assert_called_once()


# Main execution guard
if __name__ == "__main__":
    unittest.main()
