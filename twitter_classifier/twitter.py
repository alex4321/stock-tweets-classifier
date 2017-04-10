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
    def _next_results_params(next_results_str):
        args = next_results_str.replace("?", "").split("&")
        result = {}
        for item in args:
            param, value = item.split("=")
            result[param] = unquote(value)
        return result

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

    #async def search(self, request, terminator=None, text_preprocessor=None):
    #    """
    #    Search for tweets
    #    :param request: search request
    #    :type request: str
    #    :param terminator: function that'll return true to stop search
    #    :type terminator: (list[(str, datetime.datetime, int)])->bool
    #    :param text_preprocessor: function that preprocess tweet texts before cleaning
    #    :type text_preprocessor: (str)->str
    #    :return: pairs text-uid
    #    :rtype: list[(str, datetime, int)]
    #    """
    #    async def nop(_):
    #        return False
    #
    #    def text_nop(txt):
    #        return txt
    #
    #    if terminator is None:
    #        terminator = nop
    #    if text_preprocessor is None:
    #        text_preprocessor = text_nop
    #    print("q")
    #    params = {
    #        "q": request,
    #        "count": 30,
    #    }
    #    statuses = []
    #    while True:
    #        response = await self.peony.api.search.tweets.get(**params)
    #        new_statuses = list(map(
    #            lambda status: (
    #                TwitterClient._clean(text_preprocessor(status['text'])),
    #                TwitterClient._time(status['created_at']),
    #                status['user']['id'],
    #            ),
    #            response["statuses"]))
    #        print("Loaded {0} new statueses".format(len(new_statuses)))
    #        statuses += new_statuses
    #        if "search_metadata" in response and "next_results" in response["search_metadata"]:
    #            params = TwitterClient._next_results_params(response["search_metadata"]["next_results"])
    #        else:
    #            break
    #        if await terminator(new_statuses):
    #            print("Downloading terminated")
    #            break
    #    return statuses

    async def stream_handle(self, tweet_handler, **kwargs):
        ctx = self.peony.stream.statuses.filter.post(**kwargs)
        async with ctx as stream:
            async for tweet in stream:
                if 'text' in tweet:
                    text = TwitterClient._clean(tweet['text'])
                    time = TwitterClient._time(tweet['created_at'])
                    uid = tweet['user']['id']
                    await tweet_handler(tweet['text'], text, time, uid)
