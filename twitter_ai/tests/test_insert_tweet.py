import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure that the path to the utilities and other dependencies is available
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import insert_tweets


class TestInsertTweet(unittest.TestCase):
    def setUp(self):
        # Setup a mock database connection
        self.mock_db = MagicMock()
        self.mock_db.run_query = MagicMock()

        # Example tweet data with various fields populated
        self.tweet_data = {
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
                    "media": [],  # Media entities will be added in the test
                    "user_mentions": [],
                    "urls": [],
                    "hashtags": [],
                    "symbols": [],
                },
            },
            "views": {"count": 50},
            "source": "<a href='http://twitter.com'>Twitter Web Client</a>",
        }

        self.tweet_data["legacy"]["extended_entities"] = {
            "media": [
                {
                    "media_url_https": "https://example.com/media.jpg",
                    "type": "photo",
                    "media_key": "key1",
                    "sizes": {"size": "large"},
                }
            ]
        }

    @patch("utils.db_utils.Database")
    def test_tweet_with_media(self, MockDatabase):
        # Setup mock
        mock_db_instance = MockDatabase.return_value
        mock_db_instance.run_query = MagicMock()

        # Adjust tweet data
        self.tweet_data["legacy"]["entities"]["media"] = [
            {"media_url_https": "https://example.com/media.jpg", "type": "photo"}
        ]

        # Call function
        insert_tweets(mock_db_instance, self.tweet_data)

        # Verify it was called
        mock_db_instance.run_query.assert_called_once()

        # Check the arguments
        args, kwargs = mock_db_instance.run_query.call_args
        query, params = args

        # Adjust the check to reflect how media_urls are actually passed
        # Assume media_urls are serialized into a JSON string
        expected_media_json = ["https://example.com/media.jpg"]
        self.assertIn(expected_media_json, params)  # Check for JSON string in params


if __name__ == "__main__":
    unittest.main()
