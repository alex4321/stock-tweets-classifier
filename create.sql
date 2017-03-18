CREATE TABLE stocks
(
    id SERIAL PRIMARY KEY NOT NULL,
    name VARCHAR(256),
    filter VARCHAR(256)
);
CREATE UNIQUE INDEX stocks_name_uindex ON stocks (name);
CREATE UNIQUE INDEX stocks_filter_uindex ON stocks (filter);
CREATE TABLE tweet_texts
(
    id SERIAL PRIMARY KEY NOT NULL,
    text TEXT,
    classification VARCHAR(20)
);
CREATE UNIQUE INDEX tweet_texts_text_uindex ON tweet_texts (text);
CREATE TABLE tweets
(
    id SERIAL PRIMARY KEY NOT NULL,
    uid bigint,
    text INTEGER,
    time TIMESTAMP,
    CONSTRAINT tweets_tweet_texts_id_fk FOREIGN KEY (text) REFERENCES tweet_texts (id)
);
CREATE TABLE tweets_stocks
(
    stock INTEGER,
    tweet INTEGER,
    CONSTRAINT tweets_stocks_stocks_id_fk FOREIGN KEY (stock) REFERENCES stocks (id),
    CONSTRAINT tweets_stocks_tweets_id_fk FOREIGN KEY (tweet) REFERENCES tweets (id)
);
CREATE TABLE users
(
    id bigint PRIMARY KEY NOT NULL,
    k DOUBLE PRECISION
);
CREATE TABLE whitelist_hashtags
(
    tag VARCHAR(256) PRIMARY KEY NOT NULL
);
