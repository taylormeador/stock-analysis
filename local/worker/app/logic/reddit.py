import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import insert

import app.database.db as db
import app.database.models as models
from app.logic.rate_limiter import DistributedRateLimiter
from app.logic.tickers import TICKERS

logger = logging.getLogger(__name__)


def get_json(url: str, rate_limiter: DistributedRateLimiter) -> Any:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    attempt, max_attempt = 1, 3
    while attempt <= 3:
        rate_limiter.acquire()
        time.sleep(random.uniform(0.2, 5.0))  # jitter
        logger.info(f"GET {url}")
        response = requests.get(url, headers=headers)
        if not response.ok:
            if attempt == max_attempt:
                logger.warning(
                    f"max retries reached while getting {url}: status_code={response.status_code}"
                )
                return

            # reddit will throw 429, read headers to figure when to try again.
            if response.status_code == 429:
                reset_time = int(response.headers.get("x-ratelimit-reset", 60))
                logger.warning(f"rate limited - sleeping {reset_time}s")
                time.sleep(reset_time + 1)
                continue

            # status_code >=400 but not 429 - could be anything. Back off and try again
            logger.info(f"GET {url} attempt #{attempt} failed, trying again")
            attempt += 1
            time.sleep((attempt + 1) ** 3)

        logger.info(f"response received status_code={response.status_code}")
        return response.json()


def extract_comments(
    comment_list,
    post_id: str,
    parent_ticker: str | None,
    scraped_at,
    depth=0,
    max_depth=3,
):
    """Recursively extract comments up to max_depth levels"""
    comments = []

    for item in comment_list:
        if item["kind"] == "more":
            # This is a "load more" placeholder
            continue

        if item["kind"] == "t1":  # This is a comment
            comment_data = item["data"]

            # If the comment has a ticker, we want to use it for sentiment.
            # Otherwise, use the parent's ticker (comment or post).
            comment_ticker = extract_ticker(comment_data["body"])
            ticker = comment_ticker or parent_ticker

            created_utc = datetime.fromtimestamp(
                comment_data["created_utc"],
                tz=timezone.utc,
            )
            comments.append(
                {
                    "comment_id": comment_data["id"],
                    "parent_id": comment_data["parent_id"],
                    "post_id": post_id,
                    "subreddit": comment_data["subreddit"],
                    "body": comment_data["body"],
                    "score": comment_data["score"],
                    "controversiality": comment_data["controversiality"],
                    "ticker": ticker,
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
                    comments.extend(
                        extract_comments(
                            comment_list=replies,
                            post_id=post_id,
                            parent_ticker=ticker,
                            scraped_at=scraped_at,
                            depth=depth + 1,
                            max_depth=max_depth,
                        )
                    )

    return comments


def extract_ticker(text: str):
    """Returns single ticker or None"""
    words = set(re.findall(r"\b[A-Z]{2,5}\b", text.upper()))
    found_tickers = words & TICKERS

    if len(found_tickers) == 1:
        return found_tickers.pop()

    return None


def insert_post(post):
    posts_statement = insert(models.reddit_posts)
    with db.get_connection() as conn:
        logger.info(f"inserting post {post['post_id']}")
        conn.execute(posts_statement, [post])
        conn.commit()


def insert_comments(comments):
    comments_statement = insert(models.reddit_comments)
    with db.get_connection() as conn:
        logger.info(f"inserting {len(comments)} comments")
        conn.execute(comments_statement, comments)
        conn.commit()


def scrape(
    post_filter: str,
    post_limit: int,
):
    """
    Get post and comment data from predetermined list of subreddits.
    """
    logger.info(f"scraping reddit /{post_filter} with post_limit={post_limit}")
    rate_limiter = DistributedRateLimiter(
        name="reddit",
        max_requests=1,
        window_seconds=3,
    )

    scraped_at = datetime.now(timezone.utc)

    posts_url = (
        f"http://reddit.com/r/{{subreddit}}/{post_filter}.json?limit={post_limit}"
    )
    comments_url = "http://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    subreddits = [
        "wallstreetbets",
        "stocks",
        "stockmarket",
        "investing",
        "options",
        "thetagang",
    ]
    for subreddit in subreddits:
        subreddit_posts_url = posts_url.format(subreddit=subreddit)
        response = get_json(subreddit_posts_url, rate_limiter)
        if not response:
            break

        posts = response["data"]["children"]
        for child in posts:
            post_data = child["data"]

            post_text = f"{post_data['title']} {post_data.get('selftext', '')}"
            ticker = extract_ticker(post_text)

            created_utc = datetime.fromtimestamp(
                post_data["created_utc"],
                tz=timezone.utc,
            )
            post = {
                "post_id": post_data["id"],
                "subreddit": subreddit,
                "score": post_data["score"],
                "title": post_data["title"],
                "body": post_data.get("selftext"),
                "ticker": ticker,
                "author": post_data["author"],
                "num_comments": post_data["num_comments"],
                "is_daily_thread": True,  # TODO this is technically not right but it does what it needs to do for now
                "created_utc": created_utc,
                "scraped_at": scraped_at,
            }
            insert_post(post)

            post_comments_url = comments_url.format(
                subreddit=subreddit,
                post_id=post_data["id"],
            )
            response = get_json(post_comments_url, rate_limiter)
            if not response:
                logger.warning(f"unable to get comments for {post_data['id']}")
                continue

            top_level_comments = response[1]["data"]["children"]
            comments = extract_comments(top_level_comments, post_data["id"], ticker)
            insert_comments(comments)


def scrape_reddit_wsb_daily_thread():
    """Scrape Reddit WSB daily thread for ticker mentions."""
    logger.info("scraping Reddit WSB daily thread...")

    rate_limiter = DistributedRateLimiter(
        name="reddit",
        max_requests=1,
        window_seconds=2,
    )

    url = "https://www.reddit.com/r/wallstreetbets/hot.json?limit=5"
    json_response = get_json(url, rate_limiter)
    posts = json_response["data"]["children"]
    for post in posts:
        post_title = post["data"]["title"]
        if post_title.startswith("Daily Discussion Thread") or post_title.startswith(
            "Weekend Discussion Thread"
        ):
            logger.info("found WSB daily thread")
            post_data = post["data"]

            scraped_at = datetime.now(timezone.utc)
            created_utc = datetime.fromtimestamp(
                post_data["created_utc"],
                tz=timezone.utc,
            )
            post = {
                "post_id": post_data["id"],
                "subreddit": "wallstreetbets",
                "score": post_data["score"],
                "title": post_data["title"],
                "body": post_data.get("selftext"),
                "ticker": None,
                "author": post_data["author"],
                "num_comments": post_data["num_comments"],
                "is_daily_thread": True,
                "created_utc": created_utc,
                "scraped_at": scraped_at,
            }
            insert_post(post)

            comments_url = f"http://www.reddit.com/r/wallstreetbets/comments/{post_data['id']}.json"
            post_comments_url = comments_url.format(
                subreddit="wallstreetbets",
                post_id=post_data["id"],
            )
            response = get_json(post_comments_url, rate_limiter)
            if not response:
                logger.warning(f"unable to get comments for {post_data['id']}")
                continue

            top_level_comments = response[1]["data"]["children"]
            comments = extract_comments(
                comment_list=top_level_comments,
                post_id=post_data["id"],
                parent_ticker=None,
                scraped_at=scraped_at,
            )
            insert_comments(comments)
            break

    logger.info("Reddit WSB daily thread scraping complete")
    return


if __name__ == "__main__":
    scrape_reddit_wsb_daily_thread()
