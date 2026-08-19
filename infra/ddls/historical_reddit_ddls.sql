CREATE TABLE historical_reddit_posts (
    post_id VARCHAR(20) PRIMARY KEY NOT NULL,
    subreddit VARCHAR(100),
    score INTEGER,
    title TEXT,
    body TEXT,
    ticker VARCHAR(10),
    author VARCHAR(20),
    num_comments INTEGER,
    created_utc TIMESTAMPTZ
);

CREATE INDEX idx_historical_posts_ticker ON historical_reddit_posts(ticker);
CREATE INDEX idx_historical_posts_created ON historical_reddit_posts(created_utc);
CREATE INDEX idx_historical_posts_post_id ON historical_reddit_posts(post_id);


CREATE TABLE historical_reddit_comments (
    comment_id VARCHAR(20) PRIMARY KEY NOT NULL,
    parent_id VARCHAR(20),
    post_id VARCHAR(20),
    subreddit VARCHAR(100),
    body TEXT,
    score INTEGER,
    ticker VARCHAR(10),
    controversiality INTEGER,
    author VARCHAR(100),
    depth INTEGER,
    created_utc TIMESTAMPTZ
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


CREATE TABLE historical_reddit_tracking (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(200),  -- relative to mount on prod vm
    file_type VARCHAR(16),  -- comments, or submissions
    status VARCHAR(20)  -- READY, IN_PROGRESS, COMPLETE, FAILED
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ
)

-- new comment sentiment table
CREATE TABLE comment_sentiment (
    comment_id BIGINT PRIMARY KEY REFERENCES historical_reddit_comments(comment_id),
    vader_compound FLOAT,
    vader_pos FLOAT,
    vader_neg FLOAT,
    vader_neu FLOAT,
    finbert_label VARCHAR(20),
    finbert_score FLOAT,
    custom_sentiment FLOAT,
    custom_confidence FLOAT,
    processed_at TIMESTAMP
);
CREATE INDEX idx_comment_sentiment_vader ON comment_sentiment(vader_compound) WHERE vader_compound IS NOT NULL;
CREATE INDEX idx_comment_sentiment_finbert ON comment_sentiment(finbert_label) WHERE finbert_label IS NOT NULL;
CREATE INDEX idx_comment_sentiment_custom ON comment_sentiment(custom_sentiment) WHERE custom_sentiment IS NOT NULL;
CREATE INDEX idx_comment_sentiment_processed_at ON comment_sentiment(processed_at);