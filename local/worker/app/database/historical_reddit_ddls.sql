CREATE TABLE historical_reddit_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) NOT NULL,
    subreddit VARCHAR(100),
    score INTEGER,
    title TEXT,
    body TEXT,
    ticker VARCHAR(4),
    author VARCHAR(20),
    num_comments INTEGER,
    created_utc TIMESTAMPTZ,
    UNIQUE(post_id)
);

CREATE INDEX idx_historical_posts_ticker ON historical_reddit_posts(ticker);
CREATE INDEX idx_historical_posts_created ON historical_reddit_posts(created_utc);
CREATE INDEX idx_historical_posts_post_id ON historical_reddit_posts(post_id);


CREATE TABLE historical_reddit_comments (
    id SERIAL PRIMARY KEY,
    comment_id VARCHAR(20) NOT NULL,
    parent_id VARCHAR(20),
    post_id VARCHAR(20),
    subreddit VARCHAR(100),
    body TEXT,
    score INTEGER,
    ticker VARCHAR(4),
    controversiality INTEGER,
    author VARCHAR(100),
    depth INTEGER,
    created_utc TIMESTAMPTZ,
    UNIQUE(comment_id)
);

CREATE INDEX idx_historical_comments_comment_id ON historical_reddit_comments(comment_id);
CREATE INDEX idx_historical_comments_ticker ON historical_reddit_comments(ticker);
CREATE INDEX idx_historical_comments_created ON historical_reddit_comments(created_utc);
CREATE INDEX idx_historical_comments_post_id ON historical_reddit_comments(post_id);


CREATE TABLE historical_reddit_comment_sentiment_predictions (
    id SERIAL PRIMARY KEY,
    historical_reddit_comments_id INTEGER NOT NULL,
    label VARCHAR(20),
    confidence FLOAT,
    model_version VARCHAR(50),
    predicted_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT historical_comment_sentiment_unique UNIQUE (historical_reddit_comments_id),
    CONSTRAINT historical_reddit_comment_sentiment_predictions_fkey 
        FOREIGN KEY (historical_reddit_comments_id) 
        REFERENCES historical_reddit_comments(id)
);

CREATE INDEX idx_historical_comment_sentiment_comment_id ON historical_reddit_comment_sentiment_predictions(historical_reddit_comments_id);
