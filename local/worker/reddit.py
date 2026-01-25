import requests
from datetime import datetime, timezone
from typing import Any
import logging

from rate_limiter import DistributedRateLimiter

logger = logging.getLogger(__name__)


def get_json(url: str, rate_limiter: DistributedRateLimiter) -> Any:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    logger.info(f"GET {url}")

    rate_limiter.acquire()
    response = requests.get(url, headers=headers)

    response.raise_for_status()
    logger.info(f"response received status_code={response.status_code}")
    return response.json()


def extract_comments(comment_list, depth=0, max_depth=3):
    """Recursively extract comments up to max_depth levels"""
    comments = []
    scraped_at = datetime.now(timezone.utc)

    for item in comment_list:
        if item["kind"] == "more":
            # This is a "load more" placeholder
            continue

        if item["kind"] == "t1":  # This is a comment
            comment_data = item["data"]
            created_utc = datetime.fromtimestamp(
                comment_data["created_utc"],
                tz=timezone.utc,
            )
            comments.append(
                {
                    "comment_id": comment_data["id"],
                    "parent_id": comment_data["parent_id"],
                    "subreddit": comment_data["subreddit"],
                    "body": comment_data["body"],
                    "score": comment_data["score"],
                    "controversiality": comment_data["controversiality"],
                    "author": comment_data["author"],
                    "depth": comment_data["depth"],
                    "created_utc": created_utc,
                    "scraped_at": scraped_at,
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
    post_limit: int = 5,
):
    """
    Get post and comment data from predetermined list of subreddits.
    """
    logger.info(f"scraping reddit /{post_filter} with post_limit={post_limit}")
    rate_limiter = DistributedRateLimiter(
        name="reddit",
        max_requests=1,
        window_seconds=2,
    )

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
        response = get_json(subreddit_posts_url, rate_limiter)

        posts = response["data"]["children"]
        for child in posts:
            post_data = child["data"]
            created_utc = datetime.fromtimestamp(
                post_data["created_utc"],
                tz=timezone.utc,
            )
            post = {
                "post_id": post_data["id"],
                "subreddit": subreddit,
                "score": post_data["score"],
                "author": post_data["author"],
                "num_comments": post_data["num_comments"],
                "created_utc": created_utc,
                "scraped_at": scraped_at,
            }
            all_posts.append(post)

            post_comments_url = comments_url.format(
                subreddit=subreddit,
                post_id=post_data["id"],
            )
            response = get_json(post_comments_url, rate_limiter)
            top_level_comments = response[1]["data"]["children"]
            all_comments.extend(extract_comments(top_level_comments))

    return all_posts, all_comments
