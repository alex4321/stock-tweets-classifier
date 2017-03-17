"""
Asynchronyous wrapper for Watson NLC.
"""
from collections import OrderedDict
import json
from urllib.request import quote
import asyncio
import aiohttp


class All(asyncio.Future):
    """
    Wait while all futures will be finished
    """

    def __init__(self, futures):
        """
        :param futures: futures
        :type futures: list[asyncio.Future]
        """
        super(All, self).__init__()
        self._undone = len(futures)
        for future in futures:
            future.add_done_callback(self._one_done)

    def _one_done(self, *args, **kwargs):
        self._undone -= 1
        if self._undone <= 0:
            self.set_result(None)


class WatsonException(Exception):
    def __init__(self, code, message):
        self.text = "Watson returns code {0} with message {1}".format(code, message)
        super(WatsonException, self).__init__()

    def __str__(self):
        return self.text


class AsyncNaturalLanguageClassifier:
    """
    Async wrapper for traine d Watson NLC instances
    """

    def __init__(self, username, password,
                 base_url="https://gateway.watsonplatform.net/natural-language-classifier"):
        """
        Initialize wrapper
        :param username: user name
        :type username: str
        :param password: password
        :type password: str
        :param base_url: base url
        :type base_url: str
        """
        assert len(username) > 0
        assert len(password) > 0
        assert len(base_url) > 0
        self.username = username
        self.password = password
        if base_url[-1] == "/":
            self.base_url = base_url[:-1]
        else:
            self.base_url = base_url
        self.client = None

    def __enter__(self):
        self.client = aiohttp.ClientSession(loop=asyncio.get_event_loop())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    async def classify(self, classifier_id, text):
        """
        Classify one text
        :param classifier_id: classifier id
        :type classifier_id: str
        :param text: text
        :type text: str
        :return: top class and confidences
        :rtype: (str, dict[str, str])
        """
        assert self.client is not None
        url = "{0}/api/v1/classifiers/{1}/classify?text={2}".format(
            self.base_url, classifier_id, quote(text))
        auth = aiohttp.BasicAuth(self.username, self.password)
        async with self.client.get(url, auth=auth) as response:
            response_text = await response.text()
            if response.status != 200:
                raise WatsonException(response.status, response_text)
            result = json.loads(response_text)
        top = result['top_class']
        classes = OrderedDict()
        for item in result['classes']:
            classes[item['class_name']] = item['confidence']
        return top, classes

    async def ensemble_classify(self, classifier_ids, text, default_class):
        """
        Classify with ensemble of classifiers
        :param classifier_ids: classifier ids
        :type classifier_ids: list[str]
        :param text: text
        :type text: str
        :param default_class: default class (if haven't "top" voted-class)
        :type default_class: str
        :return: top voted class or default
        :rtype: str
        """
        async def _one_classify(classifier_id):
            results[classifier_id], _ = await self.classify(classifier_id, text)

        results = {}
        loop = asyncio.get_event_loop()
        classifier_futures = [loop.create_task(_one_classify(classifier_id))
                              for classifier_id in classifier_ids]
        await All(classifier_futures)
        counts = {}
        for _, class_name in results.items():
            counts[class_name] = counts.get(class_name, 0) + 1
        max_class = None
        for class_name, count in counts.items():
            if max_class is None or count > counts[max_class]:
                max_class = class_name
        if counts.get(max_class, 0) <= 1:
            return default_class
        else:
            return max_class
