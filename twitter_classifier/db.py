"""
Module that wraps database class
"""
import aiopg


_pool = None


async def connect(dsn):
    """
    Connect to Postgresql
    :param dsn: connection string
    :type dsn: str
    """
    global _pool
    _pool = await aiopg.create_pool(dsn)


async def _query(builder, result=None):
    async def _nop(_):
        return None

    assert _pool is not None
    if result is None:
        result = _nop
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            sql = await builder(cur)
            await cur.execute(sql)
            return await result(cur)


async def _fetchall(cur):
    return await cur.fetchall()


async def stocks():
    """
    Get stocks
    :return: list of name-filter pairs
    :rtype: list[(str, str)]
    """
    async def _builder(cur):
        return "SELECT name, filter FROM stocks WHERE name IS NOT NULL"

    data = await _query(_builder, _fetchall)
    result = {}
    for name, stock_filter in data:
        result[name] = stock_filter
    return result


async def store_texts(texts):
    """
    Store texts in DB
    :param texts: texts
    :type texts: list[str]
    :return: text-to-text id dict
    :rtype: dict[str, int]
    """
    async def _builder(cur):
        values = []
        for text in texts:
            values.append((await cur.mogrify("(%s, %s)", [text, ''])).decode("utf-8"))
        sql = "INSERT INTO tweet_texts (text, classification) VALUES " + \
              ",".join(values) + \
              " ON CONFLICT DO NOTHING " + \
              " RETURNING id, text"
        return sql

    result = {}
    sql_answer = await _query(_builder, _fetchall)
    for text_id, text in sql_answer:
        result[text] = text_id
    return result


async def all_classified_previously(tweets):
    """
    Is all tweets classified previously?
    :param tweets: tweets
    :type tweets: list[(str, datetime.datetime, int)]
    :return: is classified?
    :rtype: bool
    """
    async def _builder(cur):
        texts_mogrified = []
        for text in unqiue_texts:
            texts_mogrified.append((await cur.mogrify("(%s)", [text])).decode("utf-8"))
        sql = "SELECT COUNT(*)=0" + \
              " FROM ( VALUES " + ",".join(texts_mogrified) + " ) AS data (text) " + \
              " LEFT JOIN tweet_texts ON tweet_texts.text = data.text" + \
              " WHERE tweet_texts.text IS NULL"
        return sql

    texts = [tweet[0] for tweet in tweets]
    unqiue_texts = list(set(texts))
    is_classified = (await _query(_builder, _fetchall))[0][0]
    return is_classified


async def find_texts(texts):
    """
    Finf text ids
    :param texts: texts
    :type texts: list[str]
    :return: ids
    :rtype: dict[str, int]
    """
    async def _builder(cur):
        values = []
        for text in texts:
            values.append((await cur.mogrify("%s", [text])).decode("utf-8"))
        sql = "SELECT id, text FROM tweet_texts " + \
              " WHERE tweet_texts.text IN (" + ",".join(values) + ")"
        return sql

    result = {}
    sql_answer = await _query(_builder, _fetchall)
    for text_id, text in sql_answer:
        result[text] = text_id
    return result


async def store_tweets(tweets):
    """
    Store tweets
    :param tweets: tweets
    :type tweets: list[(str, datetime.datetime, int)]
    :return: text-to-text id dict, tweet ids
    :rtype: (dict[str, int], list[int])
    """
    async def _builder(cur):
        values = []
        for text, time, uid in tweets:
            values.append((await cur.mogrify("(%s, %s, %s)", [
                uid, time, text_ids[text]
            ])).decode("utf-8"))
        return "INSERT INTO tweets (uid, time, text) VALUES " + \
               ",".join(values) + " RETURNING tweets.id"

    texts = [tweet[0] for tweet in tweets]
    await store_texts(texts)
    text_ids = await find_texts(texts)
    tweet_ids = [item[0] for item in await _query(_builder, _fetchall)]
    return text_ids, tweet_ids


async def update_classification(classifications):
    """
    Update classification of texts
    :param classifications: text id - classification dict
    :type classifications: dict[int, str]
    """
    async def _builder(cur):
        subsqls = []
        for text_id, classification in classifications.items():
            subsql = (await cur.mogrify(
                "UPDATE tweet_texts SET classification = %s WHERE tweet_texts.id = %s",
                [classification, text_id]
            )).decode("utf-8")
            subsqls.append(subsql)
        return ";".join(subsqls)

    await _query(_builder)


async def stock_by_filter(stock_filter):
    """
    Find stock by filter
    :param stock_filter: filter
    :type stock_filter: str
    :return: stock id
    :rtype: int
    """
    async def _stock_id_builder(cur):
        return (await cur.mogrify("SELECT id FROM stocks WHERE filter = %s",
                                  [stock_filter])).decode("utf-8")

    async def _insert_stock_builder(cur):
        return (await cur.mogrify("INSERT INTO stocks (filter) VALUES (%s) RETURNING id", [stock_filter]))

    stock_id_rows = await _query(_stock_id_builder, _fetchall)
    if len(stock_id_rows) == 0:
        stock_id_rows = await _query(_insert_stock_builder, _fetchall)
    return stock_id_rows[0][0]


async def map_tweets_to_stock(stock_id, tweet_ids):
    """
    Map tweets to stock
    :param stock_id: stock id
    :type stock_id: int
    :param tweet_ids: tweet ids
    :type tweet_ids: list[int]
    """
    async def _builder(cur):
        insertions = []
        for tweet_id in tweet_ids:
            insertions.append((await cur.mogrify(
                "INSERT INTO tweets_stocks (stock, tweet) VALUES (%s, %s)",
                [stock_id, tweet_id]
            )).decode("utf-8"))
        return ";".join(insertions)
    await _query(_builder)


async def stock_stats(stock_id, from_time, to_time):
    """
    Build stats about stock
    :param stock_id: stock id
    :type stock_id: int
    :param from_time: not analyze older tweets
    :type from_time: datetime.datetime
    :param to_time: not analyzer newer tweets
    :type to_time: datetime.datetime
    :return: positive/negative/neutral tweet counts
    :rtype: (float, float, float)
    """
    async def _builder(cur):
        sql = "SELECT " + \
              "    SUM(subQuery.positive * subQuery.k) positive, " + \
              "    SUM(subQuery.negative * subQuery.k) negative, " + \
              "    SUM(subQuery.neutral * subQuery.k)  neutral " + \
              "  FROM ( " + \
              "    SELECT " + \
              "      CASE " + \
              "        WHEN tweet_texts.classification = 'positive' THEN 1 " + \
              "        ELSE 0 " + \
              "      END positive, " + \
              "      CASE " + \
              "        WHEN tweet_texts.classification = 'negative' THEN 1 " + \
              "        ELSE 0 " + \
              "      END negative, " + \
              "      CASE " + \
              "        WHEN tweet_texts.classification = 'neutral' THEN 1 " + \
              "        ELSE 0 " + \
              "      END neutral, " + \
              "      CASE " + \
              "        WHEN users.k IS NOT NULL THEN users.k " + \
              "        ELSE 1.0 " + \
              "      END k " + \
              "    FROM tweets " + \
              "    INNER JOIN tweet_texts ON tweets.text = tweet_texts.id " + \
              "    INNER JOIN tweets_stocks ON tweets.id = tweets_stocks.tweet " + \
              "    LEFT JOIN users ON tweets.uid = users.id " + \
              "    WHERE tweets.time >= %s AND tweets.time <= %s AND tweets_stocks.stock = %s " + \
              "  ) subQuery "
        return (await cur.mogrify(sql, [from_time, to_time, stock_id])).decode("utf-8")

    positive, negative, neutral = (await _query(_builder, _fetchall))[0]
    if positive is None:
        positive = 0
    if negative is None:
        negative = 0
    if neutral is None:
        neutral = 0
    return positive, negative, neutral


async def whitelist_hashtags():
    """
    Return list of hashtags
    :return: hashtags to be whitelisted
    :rtype: list[str]
    """
    async def _builder(cur):
        return "SELECT tag FROM whitelist_hashtags"

    return list(map(lambda row: row[0],
                    await _query(_builder, _fetchall)))


async def from_users_filter():
    """
    Return user filter
    :return: user filter (e.g. "(from:alex4321 OR from:ibm)")
    :rtype: str
    """
    async def _builder(cur):
        return "SELECT name FROM users"

    users = list(map(lambda row: row[0],
                     await _query(_builder, _fetchall)))
    user_filters = map(lambda name: "from:{0}".format(name),
                       users)
    return "(" + " OR ".join(list(user_filters)) + ")"
