import requests
import time
from datetime import datetime, timezone
from typing import Any
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(self, max_per_second: float):
        self._max_per_second = max_per_second
        self._api_call_times = []

    def _wait_for_rate_limit(self):
        while True:
            current_time = time.time()
            two_seconds_ago = current_time - 2

            # Check if there are less than maximum number of calls in the last two seconds
            times_in_window = [t for t in self._api_call_times if t > two_seconds_ago]
            if len(times_in_window) < self._max_per_second * 2:
                return

            # Sleep until the oldest call is out of the window
            oldest_call = min(times_in_window)
            slumber = oldest_call - two_seconds_ago
            logger.info(f"rate limiting - sleeping for {slumber}s")
            time.sleep(slumber)

    def get_json(self, url) -> Any:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self._wait_for_rate_limit()
        self._api_call_times.append(time.time())
        logger.info(f"GET {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logger.info(f"response received status_code={response.status_code}")
        return response.json()


def extract_comments(comment_list, depth=0, max_depth=3):
    """Recursively extract comments up to max_depth levels"""
    comments = []

    for item in comment_list:
        if item["kind"] == "more":
            # This is a "load more" placeholder
            continue

        if item["kind"] == "t1":  # This is a comment
            comment_data = item["data"]
            comments.append(
                {
                    "id": comment_data["id"],
                    "subreddit": comment_data["subreddit"],
                    "body": comment_data["body"],
                    "score": comment_data["score"],
                    "controversiality": comment_data["controversiality"],
                    "created_utc": comment_data["created_utc"],
                    "author": comment_data["author"],
                    "edited": comment_data["edited"],
                    "parent_id": comment_data["parent_id"],
                    "depth": comment_data["depth"],
                }
            )

            # Get replies (nested comments)
            if (
                depth < max_depth
                and "replies" in comment_data
                and comment_data["replies"]
            ):
                if isinstance(comment_data["replies"], dict):
                    replies = comment_data["replies"]["data"]["children"]
                    comments.extend(extract_comments(replies, depth + 1, max_depth))

    return comments


def scrape(
    post_filter: str = "new",
    rate_limit: float = 0.5,
    post_limit: int = 5,
):
    """
    Get post and comment data from predetermined list of subreddits.
    """
    logger.info(
        f"scraping reddit/{post_filter} with rate_limit={rate_limit}, post_limit={post_limit}"
    )
    scraper = Scraper(max_per_second=rate_limit)

    all_posts = []
    all_comments = []
    scraped_at = datetime.now(timezone.utc)

    posts_url = (
        f"http://reddit.com/r/{{subreddit}}/{post_filter}.json?limit={post_limit}"
    )
    comments_url = f"http://www.reddit.com/r/{{subreddit}}/comments/{{post_id}}.json"
    subreddits = [
        "wallstreetbets",
        # "stocks",
        # "stockmarket",
        # "investing",
        # "options",
        # "thetagang",
    ]
    for subreddit in subreddits:
        subreddit_posts_url = posts_url.format(subreddit=subreddit)
        response = scraper.get_json(subreddit_posts_url)
        posts = response["data"]["children"]
        for child in posts:
            post_data = child["data"]
            post = {
                "post_id": post_data["id"],
                "subreddit": subreddit,
                "score": post_data["score"],
                "author": post_data["author"],
                "num_comments": post_data["num_comments"],
                "created_utc": post_data["created_utc"],
                "scraped_at": scraped_at,
            }
            all_posts.append(post)

            comments_url = comments_url.format(
                subreddit=subreddit,
                post_id=post_data["id"],
            )
            response = scraper.get_json(comments_url)
            top_level_comments = response[1]["data"]["children"]
            all_comments.append(extract_comments(top_level_comments))

    return all_posts, all_comments


if __name__ == "__main__":

    posts, comments = scrape()
    breakpoint()
