import json

if __name__ == "__main__":
    with open("t2.json", "r") as f:
        all_pages = json.load(f)

    for tweets in all_pages:
        for instruction in tweets["data"]["user"]["result"]["timeline_v2"]["timeline"][
            "instructions"
        ]:
            if instruction["type"] == "TimelineAddEntries":
                for entry in instruction["entries"]:
                    if entry["entryId"].startswith("tweet"):
                        try:
                            tweet_results = entry["content"]["itemContent"][
                                "tweet_results"
                            ]["result"]

                            tweet_id = tweet_results["rest_id"]

                            if "note_tweet" in tweet_results:
                                tweet_text = tweet_results["note_tweet"][
                                    "note_tweet_results"
                                ]["result"][
                                    "text"
                                ]  # for long tweets gives full text, but do not exist for short tweets and for retweets
                            else:
                                tweet_text = tweet_results["legacy"]["full_text"]

                            likes = tweet_results["legacy"]["favorite_count"]
                            retweets = tweet_results["legacy"]["retweet_count"]
                            replies = tweet_results["legacy"]["reply_count"]
                            quotes = tweet_results["legacy"]["quote_count"]
                            bookmarks = tweet_results["legacy"]["bookmark_count"]
                            created_at = tweet_results["legacy"]["created_at"]
                            views = tweet_results["views"].get(
                                "count", 0
                            )  # 0 is the default value
                            has_media = "media" in tweet_results["legacy"][
                                "entities"
                            ] and bool(tweet_results["legacy"]["entities"]["media"])
                            has_user_mentions = "user_mentions" in tweet_results[
                                "legacy"
                            ]["entities"] and bool(
                                tweet_results["legacy"]["entities"]["user_mentions"]
                            )
                            if has_user_mentions:
                                users_mentioned = [
                                    mention["id_str"]
                                    for mention in tweet_results["legacy"]["entities"][
                                        "user_mentions"
                                    ]
                                ]
                            has_urls = "urls" in tweet_results["legacy"][
                                "entities"
                            ] and bool(tweet_results["legacy"]["entities"]["urls"])
                            has_hashtags = "hashtags" in tweet_results["legacy"][
                                "entities"
                            ] and bool(tweet_results["legacy"]["entities"]["hashtags"])
                            has_symbols = "symbols" in tweet_results["legacy"][
                                "entities"
                            ] and bool(tweet_results["legacy"]["entities"]["symbols"])
                            if has_symbols:
                                symbols = [
                                    x["text"]
                                    for x in tweet_results["legacy"]["entities"][
                                        "symbols"
                                    ]
                                ]
                            if has_user_mentions and not tweet_text.startswith("RT"):
                                print(tweet_text)
                                print(users_mentioned)
                            # if has_symbols:
                            #     print(tweet_text)
                            #     print(symbols)

                            if "50x leveraged perps" in tweet_text:
                                print("heyhey")
                            print("=*" * 25)
                        except KeyError as e:
                            print(
                                f"ERROR:KeyError: {e}. Entry error, entry: {str(entry)[:100]}"
                            )
        print("<^>" * 25)
