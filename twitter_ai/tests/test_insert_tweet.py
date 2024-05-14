import unittest
from unittest.mock import MagicMock
from utils.db_utils import insert_tweet


class TestInsertTweet(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()

    def test_insert_tweet_basic(self):
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
        insert_tweet(self.mock_db, tweet_results)
        self.mock_db.run_query.assert_called_once()

    def test_tweet_with_no_extended_entities(self):
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
        insert_tweet(self.mock_db, tweet_results)
        self.mock_db.run_query.assert_called_once()


if __name__ == "__main__":
    unittest.main()
