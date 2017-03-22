"""
Application logic.
"""
import asyncio
import json
import logging
import math
from . import db
from .twitter import TwitterClient

from twitter_classifier.watson_nlc import AsyncNaturalLanguageClassifier, All


class Configuration:
    """
    Application configuration class
    """
    class _TwitterConfiguration:
        def __init__(self, config):
            self.consumer_key = config["consumer_key"]
            self.consumer_secret = config["consumer_secret"]
            self.access_token = config["access_token"]
            self.access_token_secret = config["access_token_secret"]
            self.user_filter_per_request = config["user_filter_per_request"]

    class _NlcConfiguration:
        def __init__(self, config):
            self.username = config["username"]
            self.password = config["password"]
            self.classifiers = config["classifiers"]
            self.text_per_block = config["text_per_block"]

    def __init__(self, config):
        self.twitter = Configuration._TwitterConfiguration(config["twitter"])
        self.nlc = Configuration._NlcConfiguration(config["nlc"])
        self.database = config["db"]
        self.port = config["port"]
        self.log_level = config["log_level"]

    @staticmethod
    def from_file(path):
        """
        Load configuration from file
        :param path: path to config file
        :type path: str
        :return: configuration
        :rtype: Configuration
        """
        logging.info("Reading configuration from {0}".format(path))
        with open(path, "r") as src:
            return Configuration(json.load(src))


class AppLogic:
    """
    Application logic class
    """
    FROM_USERS_FILTER = "$FROM_USERS$"

    def __init__(self, configuration):
        """
        :param configuration: configuration object
        :type configuration: Configuration
        """
        self.configuration = configuration

    async def initialize(self):
        """
        Initialize logic
        """
        logging.info("Initialization DB")
        await db.connect(self.configuration.database)

    async def stocks(self):
        """
        Get stocks
        :return: list of name-filter pairs
        :rtype: list[(str, str)]
        """
        return await db.stocks()

    def twitter_client(self):
        """
        Get twitter client instance
        :return: client
        :rtype: TwitterClient
        """
        return TwitterClient(self.configuration.twitter.consumer_key,
                             self.configuration.twitter.consumer_secret,
                             self.configuration.twitter.access_token,
                             self.configuration.twitter.access_token_secret)

    def nlc(self):
        """
        Get classifier instance
        :return: classifier
        :rtype: AsyncNaturalLanguageClassifier
        """
        return AsyncNaturalLanguageClassifier(self.configuration.nlc.username,
                                              self.configuration.nlc.password)

    async def _classify_texts(self, texts):
        """
        Classify texts
        :param texts: texts
        :type texts: list[str]
        :return: classification results (text-class dict)
        :rtype: dict[str, str]
        """
        async def _text_classify(text_classification_results, nlc, text):
            if text == "":
                return "neutral"
            text_classification_results[text] = await nlc.ensemble_classify(
                self.configuration.nlc.classifiers,
                text,
                "neutral"
            )

        logging.debug("Classifying {0} texts".format(len(texts)))
        # We'll try to send multiple classifiation request (batches) in same time
        loop = asyncio.get_event_loop()
        text_classification_results = {}
        text_per_block = self.configuration.nlc.text_per_block  # classification batch size
        with self.nlc() as client:
            block_count = math.ceil(len(texts) / text_per_block)
            for block in range(0, block_count):
                logging.info("Classifyed {0} texts".format(block * text_per_block))
                block_texts = texts[block * text_per_block:(block + 1) * text_per_block]
                tasks = []
                for text in block_texts:
                    classify_generator = _text_classify(text_classification_results, client, text)
                    tasks.append(loop.create_task(classify_generator))
                await All(tasks)
        return text_classification_results

    async def _get_stock_tweets(self, stock_filter):
        def _replace_whitelist(whitelist, text):
            text = text.lower()
            for tag in whitelist:
                text = text.replace("#" + tag, "")
            return text

        async def _filter_tweets_download(filters, tweets):
            request = stock_filter.replace(AppLogic.FROM_USERS_FILTER, "") \
                      + " AND (" + " OR ".join(filters) + ")"
            real_tweets = await twitter.search(request,
                                               db.all_classified_previously,
                                               lambda text: _replace_whitelist(whitelist, text))
            for tweet in real_tweets:
                tweets.append(tweet)

        whitelist = await db.whitelist_hashtags()
        twitter = self.twitter_client()

        if AppLogic.FROM_USERS_FILTER in stock_filter:
            users_filters = await db.from_users_filter()
            filter_per_block = self.configuration.twitter.user_filter_per_request
            block_count = math.ceil(len(users_filters) / filter_per_block)
            tweets = []
            tasks = []
            loop = asyncio.get_event_loop()
            for block in range(0, block_count):
                block_filters = users_filters[block * filter_per_block: (block + 1) * filter_per_block]
                task = loop.create_task(_filter_tweets_download(block_filters, tweets))
                tasks.append(task)
            await All(tasks)
        else:
            tweets = await twitter.search(stock_filter,
                                          db.all_classified_previously,
                                          lambda text: _replace_whitelist(whitelist, text))
        return tweets

    async def classify_stock_tweets(self, stock_filter):
        """
        Classify tweets for stock with given filter
        :param stock_filter: stock filter (e.g. "AAPL")
        :type stock_filter: str
        :return: stock id
        :rtype: int
        """
        # Get new tweets
        logging.info("Classifying new tweets from {0}".format(stock_filter))
        tweets = await self._get_stock_tweets(stock_filter)
        logging.info("Downloaded {0} new tweets".format(len(tweets)))
        texts_to_ids, tweet_ids = await db.store_tweets(tweets)
        texts = list(texts_to_ids.keys())
        texts.sort()
        # Classify new tweet texts
        text_classification_results = await self._classify_texts(texts)
        # Update text classification
        logging.info("Updating text classification")
        classification_records = {}
        for text, classification in text_classification_results.items():
            text_id = texts_to_ids[text]
            classification_records[text_id] = classification
        await db.update_classification(classification_records)
        # Map tweets to stock
        logging.info("Mapping to stocks")
        stock_id = await db.stock_by_filter(stock_filter)
        await db.map_tweets_to_stock(stock_id, tweet_ids)
        return stock_id

    async def stock_stats(self, stock_id, from_time, to_time, exclude_neutral):
        """
        Build stock stats
        :param stock_id: stock id
        :type stock_id: int
        :param from_time: not analyze older tweets
        :type from_time: datetime.datetime
        :param to_time: not analyzer newer tweets
        :type to_time: datetime.datetime
        :param exclude_neutral: exclude neutral tweets
        :type exclude_neutral: bool
        :return: positive/negative/neutral part (in [0..1] diapazone)
        :rtype: (float, float, float)
        """
        logging.info("Building start for stock {0} in {1}-{2}".format(stock_id, from_time, to_time))
        positive, negative, neutral = await db.stock_stats(stock_id, from_time, to_time)
        if exclude_neutral:
            neutral = 0
            total = positive + negative
        else:
            total = positive + negative + neutral
        if total == 0:
            return 0, 0, 0
        else:
            return positive / total, negative / total, neutral / total
