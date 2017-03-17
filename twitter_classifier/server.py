import asyncio
import datetime
import json
import logging
import os
import sys
from tornado.platform.asyncio import AsyncIOMainLoop
from tornado.web import Application, RequestHandler
from .logic import Configuration, AppLogic


async def main():
    config = Configuration.from_file("config.json")
    logic = AppLogic(config)
    await logic.initialize()
    stock_id = await logic.classify_stock_tweets("TWTR")
    now = datetime.datetime.now()
    start = now - datetime.timedelta(days=10)
    print(await logic.stock_stats(stock_id, start, now, False))
    print(await logic.stock_stats(stock_id, start, now, True))


class JsonRequestHandler(RequestHandler):
    def send_answer(self, answer):
        json_data = json.dumps(answer)
        wrapper = self.get_argument("jsonp_wrapper", None)
        if wrapper is None:
            self.set_header("Content-Type", "application/json")
            self.write(json_data)
        else:
            self.set_header("Content-Type", "application/javascript")
            self.write(wrapper + "(" + json_data + ")")
        self.finish()

    async def get(self):
        try:
            result = await asyncio.get_event_loop().create_task(self._get())
            self.send_answer({"success": True, "response": result})
        except Exception as err:
            self.send_answer({"success": False})

    async def _get(self):
        raise NotImplementedError()


def run_server(config_path):
    class StocksHandler(JsonRequestHandler):
        async def _get(self):
            return await logic.stocks()

    class StatsHandler(JsonRequestHandler):
        async def _get(self):
            filter = self.get_argument("q", "")
            assert filter != ""
            from_time = datetime.datetime.fromtimestamp(
                int(self.get_argument("from", 0))
            )
            to_time = datetime.datetime.fromtimestamp(
                int(self.get_argument("to", 0))
            )
            exclude_neutral = bool(self.get_argument("no_neutral", False))
            assert to_time >= from_time
            stock_id = await logic.classify_stock_tweets(filter)
            positive, negative, neutral = await logic.stock_stats(stock_id, from_time, to_time, exclude_neutral)
            return {
                "positive": positive,
                "negative": negative,
                "neutral": neutral
            }


    config = Configuration.from_file(config_path)
    logging.basicConfig(level=config.log_level)
    logic = AppLogic(config)
    asyncio.get_event_loop().run_until_complete(logic.initialize())
    AsyncIOMainLoop().install()
    application = Application([
        (r'/stocks', StocksHandler,),
        ('/stats', StatsHandler,)
    ])
    application.listen(config.port)
    asyncio.get_event_loop().run_forever()


def main():
    if len(sys.argv) == 2:
        config = sys.argv[1]
    else:
        config = os.path.join(os.path.dirname(__file__), "config.json")
    run_server(config)