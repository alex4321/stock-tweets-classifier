"""
Twitter client module
"""
from peony import PeonyClient
from datetime import datetime, timedelta
from email.utils import parsedate_tz
from urllib.request import unquote
import re


class TwitterClient:
    """
    Twitter client
    """
    def __init__(self, consumer_key, consumer_secret, access_token, access_token_secret, timeout=2):
        """
        Initialize client
        :param consumer_key: consumer key
        :type consumer_key: str
        :param consumer_secret: consumer secret
        :type consumer_secret: str
        :param access_token: access token
        :type access_token: str
        :param access_token_secret: access token secret
        :type access_token_secret: str
        :param timeout: timeout between calls to Twitter (in one search session)
        :type timeout: float
        """
        self.peony = PeonyClient(consumer_key, consumer_secret, access_token, access_token_secret)
        self.timeout = timeout

    @staticmethod
    def _clean(text):
        t = re.sub('(#\w+)|(@\w+)|(\$\w+)|(\d+)|(&gt;)|(&lt;)', "", text)
        t = re.sub('(http\S+)', "", t)
        t = re.sub('[^a-zA-z]', " ", t)
        t = re.sub('^\s+', "", t)
        t = re.sub('\\n', " ", t)
        return t

    @staticmethod
    def _time(datestring):
        time_tuple = parsedate_tz(datestring.strip())
        dt = datetime(*time_tuple[:6])
        return dt - timedelta(seconds=time_tuple[-1])

    async def stream_handle(self, tweet_handler, text_preprocessor, **kwargs):
        ctx = self.peony.stream.statuses.filter.post(**kwargs)
        async with ctx as stream:
            async for tweet in stream:
                if 'text' in tweet:
                    text = TwitterClient._clean(text_preprocessor(tweet['text']))
                    time = TwitterClient._time(tweet['created_at'])
                    uid = tweet['user']['id']
                    await tweet_handler(tweet['text'], text, time, uid)
