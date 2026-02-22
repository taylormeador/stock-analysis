import io
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any
import os

import requests
import zstandard as zstd
from sqlalchemy import insert, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert

import app.database.db as db
import app.database.models as models
from app.utils import (
    TICKERS,
    DistributedRateLimiter,
    TaskStatusTracker,
    track_records_processed,
)

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


def extract_tickers(text: str):
    """Returns list of tickers or None"""
    words = set(re.findall(r"\b[A-Z]{2,5}\b", text.upper()))
    found_tickers = words & TICKERS

    return found_tickers or None


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


def scrape_reddit_wsb_daily_thread(filter: str, limit: int, tracker: TaskStatusTracker):
    """Scrape Reddit WSB daily thread for ticker mentions."""
    logger.info("scraping Reddit WSB daily thread...")
    tracker.update_status_message("Scraping...")

    rate_limiter = DistributedRateLimiter(
        name="reddit",
        max_requests=1,
        window_seconds=2,
    )

    url = "https://www.reddit.com/r/wallstreetbets/hot.json?limit=5"
    json_response = get_json(url, rate_limiter)
    posts = json_response["data"]["children"]
    if not posts:
        logger.info("no posts found")
        tracker.complete_task()
        return

    for post in posts:
        post_title = post["data"]["title"]
        if (
            post_title.startswith("Daily Discussion Thread")
            or post_title.startswith("Weekend Discussion Thread")
            or post_title.startswith("What Are Your Moves")
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
            tracker.update_progress(0.3)

            comments_url = f"http://www.reddit.com/r/wallstreetbets/comments/{post_data['id']}.json?sort={filter}&limit={limit}"
            response = get_json(comments_url, rate_limiter)
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

            tracker.update_progress(0.6)
            tracker.update_status_message(f"Scraped {len(comments)} comments")
            track_records_processed(
                task_name="scrape_reddit_wsb_daily_thread",
                count=len(comments),
                record_type="reddit_comment",
            )
            break

    logger.info("Reddit WSB daily thread scraping complete")
    tracker.update_progress(0.8)

    return


class HistoricalRedditTracking:
    def __init__(self):
        self.model = models.historical_reddit_tracking
        self.file_info = self._get_file_info()

    def _get_file_info(self):
        stmt = self.model.select().where(self.model.c.status == "READY").limit(1)
        with db.get_connection() as conn:
            result = conn.execute(stmt).first()

        if result:
            return result

        raise ValueError("No file ready for scraping")

    def set_start_time(self):
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(self.model.c.id == self.file_info.id)
            .values(start_time=now)
        )
        with db.get_connection() as conn:
            conn.execute(stmt)
            conn.commit()

    def set_end_time(self):
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(self.model.c.id == self.file_info.id)
            .values(end_time=now)
        )
        with db.get_connection() as conn:
            conn.execute(stmt)
            conn.commit()

    def set_file_status(self, status: str):
        """`status` should be one of "READY", "IN_PROGRESS", "FAILED", "COMPLETE"."""
        stmt = (
            update(self.model)
            .where(self.model.c.id == self.file_info.id)
            .values(status=status)
        )
        with db.get_connection() as conn:
            conn.execute(stmt)
            conn.commit()

        logger.info(f"updated file {self.file_info.file_name} to {status}")


def scrape_historical_data(tracker: TaskStatusTracker):
    # Get a file to scrape
    try:
        historical_tracking = HistoricalRedditTracking()
        file_info = historical_tracking.file_info
    except ValueError:
        logger.info("no historical reddit files ready")
        return

    # Mark the file as being scraped
    historical_tracking.set_file_status("IN_PROGRESS")
    historical_tracking.set_start_time()
    logger.info(f"scraping file {file_info.file_name}")

    # determine db model
    if file_info.file_type == "comments":
        model = models.historical_reddit_comments
        record_type = "reddit_comment"
        pk = "comment_id"
    elif file_info.file_type == "submissions":
        model = models.historical_reddit_posts
        record_type = "reddit_posts"
        pk = "post_id"
    else:
        historical_tracking.set_file_status("FAILED")
        historical_tracking.set_end_time()
        raise ValueError("unexpected file type for historical reddit data")

    # track progress
    file_size = os.path.getsize(file_info.file_name)
    logger.info(f"File size: {file_size:,} bytes")
    task_name = "scrape_reddit_historical_data"
    tracker.update_status_message(f"Scraping {file_info.file_name} {file_size:,} bytes")

    # Scrape and insert batches
    batch_size = 5000
    batch = []
    try:
        with open(file_info.file_name, "rb") as fh:
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(fh) as reader:
                text_stream = io.TextIOWrapper(reader, encoding="utf-8")
                for i, line in enumerate(text_stream):
                    try:
                        bytes_processed = fh.tell()
                        l = json.loads(line)  # noqa: E741
                        if l.get("subreddit", "").lower() in {
                            "wallstreetbets",
                            "stocks",
                            "investing",
                        }:
                            if file_info.file_type == "comments":
                                permalink = l["permalink"]
                                fields = permalink.split("comments/")
                                post_id = fields[1].split("/")[0]

                            created_utc = datetime.fromtimestamp(
                                l["created_utc"],
                                tz=timezone.utc,
                            )

                            if file_info.file_type == "comments":
                                data = {
                                    "comment_id": l.get("id"),
                                    "parent_id": l.get("parent_id"),
                                    "post_id": post_id,  # type: ignore
                                    "subreddit": l["subreddit"],
                                    "body": l["body"],
                                    "score": l["score"],
                                    "ticker": extract_ticker(l["body"]),
                                    "controversiality": l["controversiality"],
                                    "author": l["author"],
                                    "created_utc": created_utc,
                                }
                            else:
                                data = {
                                    "post_id": l.get("id"),
                                    "subreddit": l["subreddit"],
                                    "score": l["score"],
                                    "title": l["title"],
                                    "body": l.get("selftext"),
                                    "ticker": extract_ticker(l.get("selftext")),
                                    "author": l["author"],
                                    "num_comments": l["num_comments"],
                                    "created_utc": created_utc,
                                }

                            batch.append(data)

                            # Bulk insert to DB
                            if len(batch) >= batch_size:
                                stmt = postgres_insert(model).values(batch)
                                stmt = stmt.on_conflict_do_nothing(index_elements=[pk])
                                with db.get_connection() as conn:
                                    conn.execute(stmt)
                                    conn.commit()
                                batch = []
                                logger.info("inserted batch")

                                track_records_processed(
                                    task_name=task_name,
                                    count=batch_size,
                                    record_type=record_type,
                                )
                                # Let file progress be 1-95% of total completion
                                progress = max(bytes_processed / file_size - 0.05, 0.01)
                                tracker.update_progress(
                                    percent_complete=progress,
                                    persist=True,
                                )

                        if i % 100000 == 0:
                            logger.info(f"Processed {i:,} lines")

                    except json.JSONDecodeError:
                        continue

                    except Exception as e:
                        logger.error(e)
                        logger.error(line)

                if batch:
                    stmt = model.insert().values(batch)
                    with db.get_connection() as conn:
                        conn.execute(stmt)
                        conn.commit()
                        logger.info("inserted final partial batch")

                # Mark the file/task complete
                track_records_processed(
                    task_name=task_name,
                    count=len(batch),
                    record_type=record_type,
                )
                tracker.update_status_message(f"Processed {file_size:,} bytes")

                historical_tracking.set_file_status("COMPLETE")
                historical_tracking.set_end_time()
                logger.info(
                    f"reddit historical data ETL complete for file {file_info.file_name}"
                )

    except Exception as e:
        logger.error(f"error while processing historical reddit file: {e}")
        historical_tracking.set_file_status("FAILED")
        historical_tracking.set_end_time()
        raise


if __name__ == "__main__":
    pass
