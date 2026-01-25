CREATE TABLE reddit_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20),
    subreddit VARCHAR(100),
    score INTEGER,
    author VARCHAR(20),
    num_comments INTEGER,
    created_utc TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(post_id, scraped_at)
);

CREATE INDEX idx_posts_score ON raw_reddit_posts(score);
CREATE INDEX idx_posts_created ON raw_reddit_posts(created_utc);
CREATE INDEX idx_posts_scraped ON raw_reddit_posts(scraped_at);

CREATE TABLE reddit_comments (
    id SERIAL PRIMARY KEY,
    comment_id VARCHAR(20),
    parent_id VARCHAR(20),
    subreddit VARCHAR(100),
    body TEXT,
    score INTEGER,
    controversiality INTEGER,
    author VARCHAR(100),
    depth INTEGER,
    created_utc TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(comment_id, scraped_at)
);

CREATE INDEX idx_comments_comment_id ON reddit_comments(comment_id);
CREATE INDEX idx_comments_parent_id ON reddit_comments(parent_id);
CREATE INDEX idx_comments_created ON reddit_comments(created_utc);
CREATE INDEX idx_comments_scraped ON reddit_comments(scraped_at);
CREATE INDEX idx_comments_subreddit ON reddit_comments(subreddit);