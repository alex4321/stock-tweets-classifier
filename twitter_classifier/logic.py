"""
Application logic.
"""
import asyncio
import datetime
import json
import logging
import math
from .db import connect, stocks, stock_stats, store_tweets, stock_by_filter, map_tweets_to_stock, find_texts, update_classification, stocks, whitelist_hashtags
from twitter_classifier.twitter import TwitterClient
from .watson_nlc import AsyncNaturalLanguageClassifier, All


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
        await connect(self.configuration.database)

    async def stocks(self):
        """
        Get stocks
        :return: list of name-filter pairs
        :rtype: list[(str, str)]
        """
        return await stocks()

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

    async def _classify_text(self, text):
        """
        Classify texts
        :param texts: texts
        :type texts: list[str]
        :return: classification results (text-class dict)
        :rtype: dict[str, str]
        """
        with self.nlc() as nlc:
            return await nlc.ensemble_classify(self.configuration.nlc.classifiers,
                                               text,
                                               "neutral")

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
        positive, negative, neutral = await stock_stats(stock_id, from_time, to_time)
        if exclude_neutral:
            neutral = 0
            total = positive + negative
        else:
            total = positive + negative + neutral
        if total == 0:
            return 0, 0, 0
        else:
            return positive / total, negative / total, neutral / total

    async def twitter_streams(self):
        """
        Run Twitter Streaming processing
        """
        def _replace_whitelist(whitelist, text):
            text = text.lower()
            for tag in whitelist:
                text = text.replace("#" + tag, "")
            return text

        whitelist = await whitelist_hashtags()
        streams = list((await stocks()).values())
        print("Monitoring stocks {0}".format(streams))
        twitter = self.twitter_client()

        async def tweet_handler(text, clean_text, time, uid):
            if clean_text == '':
                return
            _, tweet_ids = await store_tweets([(clean_text, time, uid)])
            tweet_id = tweet_ids[0]
            print("Stored new tweet with id {0}".format(tweet_ids[0]))
            text_lower = text.lower()
            for stream in streams:
                stream_lower = stream.lower()
                print(text_lower, stream_lower)
                if ('#' + stream_lower) in text_lower or \
                        ('$' + stream_lower) in text_lower:
                    stock_id = await stock_by_filter(stream)
                    await map_tweets_to_stock(stock_id, tweet_ids)
                    print("Tweet {0} mapped to stock {1} ({2})".format(tweet_id, stock_id, stream))
            text_id = (await find_texts([clean_text]))[clean_text]
            classification = await self._classify_text(clean_text)
            print("Tweet {0} has text with ID {1} classified as {2}".format(tweet_id, text_id, classification))
            await update_classification({text_id: classification})
            print(text, clean_text, time, uid)

        await twitter.stream_handle(tweet_handler,
                                    lambda text: _replace_whitelist(whitelist, text),
                                    track=",".join(streams))
