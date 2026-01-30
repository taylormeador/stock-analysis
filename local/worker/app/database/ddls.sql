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

CREATE INDEX idx_posts_score ON reddit_posts(score);
CREATE INDEX idx_posts_created ON reddit_posts(created_utc);
CREATE INDEX idx_posts_scraped ON reddit_posts(scraped_at);

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


CREATE VIEW first_reddit_comments AS
SELECT DISTINCT ON (comment_id)
    id,
    comment_id,
    parent_id,
    subreddit,
    body,
    score,
    controversiality,
    author,
    depth,
    created_utc,
    scraped_at,
    ticker
FROM reddit_comments
ORDER BY comment_id, scraped_at ASC;


CREATE TABLE reddit_comment_sentiment_predictions (
	id serial4 NOT NULL,
	reddit_comments_id int4 NULL,
	"label" varchar(20) NULL,
	confidence float8 NULL,
	model_version varchar(50) NULL,
	predicted_at timestamptz DEFAULT now() NULL,
	CONSTRAINT reddit_comment_sentiment_predictions_pkey PRIMARY KEY (id)
);

ALTER TABLE reddit_comment_sentiment_predictions ADD CONSTRAINT reddit_comment_sentiment_predictions_reddit_comments_id_fkey FOREIGN KEY (reddit_comments_id) REFERENCES public.reddit_comments(id);

-- Historical stock price data table
CREATE TABLE stock_prices (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,

    sma_9 DECIMAL(10, 2),
    sma_10 DECIMAL(10, 2),
    sma_12 DECIMAL(10, 2),
    sma_26 DECIMAL(10, 2),
    sma_50 DECIMAL(10, 2),
    sma_100 DECIMAL(10, 2),
    sma_200 DECIMAL(10, 2),

    ema_9 DECIMAL(10, 2),
    ema_10 DECIMAL(10, 2),
    ema_12 DECIMAL(10, 2),
    ema_26 DECIMAL(10, 2),
    ema_50 DECIMAL(10, 2),
    ema_100 DECIMAL(10, 2),
    ema_200 DECIMAL(10, 2),

    rsi_14 DECIMAL(10, 2),
    macd_12_26_9 DECIMAL(10, 2),
    macdh_12_26_9 DECIMAL(10, 2),
    macds_12_26_9 DECIMAL(10, 2),

    bbl_20 DECIMAL(10, 2),
    bbm_20 DECIMAL(10, 2),
    bbu_20 DECIMAL(10, 2),
    bbb_20 DECIMAL(10, 2),
    bbp_20 DECIMAL(10, 2),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(ticker, date)
);

CREATE INDEX idx_stock_prices_ticker ON stock_prices(ticker);
CREATE INDEX idx_stock_prices_date ON stock_prices(date);
CREATE INDEX idx_stock_prices_ticker_date ON stock_prices(ticker, date);
