CREATE TABLE reddit_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20),
    subreddit VARCHAR(100),
    score INTEGER,
    author VARCHAR(20),
    num_comments INTEGER,
    is_daily_thread BOOLEAN, 
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
    embedding PUBLIC.VECTOR(384),
    embedding_generated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(comment_id, scraped_at)
);

CREATE INDEX idx_comments_comment_id ON reddit_comments(comment_id);
CREATE INDEX idx_comments_parent_id ON reddit_comments(parent_id);
CREATE INDEX idx_comments_created ON reddit_comments(created_utc);
CREATE INDEX idx_comments_scraped ON reddit_comments(scraped_at);
CREATE INDEX idx_comments_subreddit ON reddit_comments(subreddit);
CREATE INDEX idx_reddit_comments_score ON reddit_comments(score DESC);


CREATE VIEW first_reddit_comments AS
SELECT DISTINCT ON (comment_id)
    id,
    comment_id,
    parent_id,
    post_id,
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


CREATE VIEW last_reddit_comments AS
SELECT DISTINCT ON (comment_id)
    id,
    comment_id,
    parent_id,
    post_id,
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
ORDER BY comment_id, scraped_at DESC;


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


CREATE TABLE current_top_reddit_comments (
	id SERIAL NOT NULL,
	comment_id varchar(20) NULL,
	body text NULL,
	score int4 NULL,
	CONSTRAINT current_top_comments_pkey PRIMARY KEY (id)
);

