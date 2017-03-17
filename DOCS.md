Installation
============
You'll need installed software:
- python3.5 - see [python downloads](https://www.python.org/downloads/) or use repositories of your system
- postgresql - see [postgres downloads](https://www.postgresql.org/download/) (or use repositories of your system)

To install this software - you can make next:
- run ```python3 setup.py install```. If you'll not see error messages - you'll can run it.

If you'll have errors - you'll can try to install it manually :

- python3-pip (buildin in Windows distributive of python, in debian-based systems - use ```apt install python3-pip```)
- peony-twitter (use ```pip3 install peony-twitter[all]```) 
    or download latest version from [github](https://github.com/odrling/peony-twitter) and run ```python3 setup.py install```
- aiopg - ```pip3 install aiopg```
- aiohttp - ```pip3 install aiohttp```
- tornado - ```pip3 install tornado```

Classification notes
====================
Currently it use ensemble of multiple Watson NL classifiers
    (with 1 - I had good score for positive-nagative classification, but bad when I also added neutral tweets).
And use class with bigger votes count - or mark text as "neutral"
I trained 3 classifiers trained on different subsets of source dataset:
- positive-negative
- positive-neutral
- negative-neutral

So - e.g. for "positive" text we have good chance that 2 of 3 classifiers will mark it as positive.
    Same for other classes.

To train it - use neg-pos-train.csv, neg-neu-train.csv, neu-pos-train.csv from dataset directory.

Optinally - you'll can "imporve" it with neg-pos-test.csv, neg-neu-test.csv, neu-pos-test.csv with Watson NLC toolkit.
    
Database
========
You can see database creation script in "create.sql".
DB have next stucture
- stocks (store stock name/filters (or - only filter if user sended custom filter text))
    - id - stock key
    - name - unique name of stock or NULL (for user custom filters).
    - filter - Twitter search request. E.g. - ("AAPL" for $AAPL)
- tweet_texts - store unique texts (separeted to avoid storing and reclassification of duplicates)
    - id - key
    - text - cleaned tweet text
    - classification - tweet text classification (when maked). One of "positive"/"negative"/"neutral"
- tweets - tweets
    - id - key (not Twitter tweet ID!)
    - uid - user id
    - text - foreign key to text
    - time - posting time
- tweet_stocks - mapping between stocks and tweets
    - tweet - tweet key
    - stock - stock key
- users - users 
    - id - key (same as twitter user id)
    - k - cooficient to change user tweets weight (during calculation of "total" results)
- whitelist of  hashtags - whitelist_hashtags
    - tag - tag name. E.g. - you need to replace "#yield" tag to "yield" word - so tag='yield'

Configuration
=============
Config file is a JSON with structure like next:
```
{
  "twitter": {
    "consumer_key": "ConsumerKey",
    "consumer_secret": "ConsumerSecret",
    "access_token": "AccessToken",
    "access_token_secret": "AccessTokenSecret"
  },
  "nlc": {
    "username": "Username",
    "password": "Password",
    "classifiers": ["classifierId1", "classifierId2", "classifierId3"],
    "text_per_block": 10
  },
  "db": "dbname=twitter user=twitter password=password host=127.0.0.1",
  "port": 8000,
  "log_level": 10
}
```
Where:
- twitter - twitter app auth data. See it in [https://apps.twitter.com](https://apps.twitter.com)
- nlc.username, nlc.password - Watson NLC service creditentials
- nlc.classifiers - array of classifier ID's
- nlc.text_per_block - I try to classify tweets by "batches", there is batch count. 
    E.g. - we have 25 tweets - so it'll make 10 requests, when all finished - next ten and - last 5
- db - aiopg connection string for Postgresql database
- port - tornado will listen for given port
- log_level - level of log messages to show. One of next:
    - CRITICAL = 50
    - ERROR = 40
    - WARNING = 30
    - INFO = 20
    - DEBUG = 10
    - NOTSET = 0

Running
=======
You'll can run it by something like next command:
```
twitter_classifier_server config.json
```

Usage
=====

Basics
------
Each call returns JSON or JSONP. To use JSONP - you can add "jsonp_wrapper" params and it'll return javascript code.
E.g.
```
GET http://127.0.0.1:8000/stock?jsonp_wrapper=alert
...
alert({"success": true, "response": ...})
```
Also - response contains 2 values:
- success - boolean
- response - optional, sended if request is success
 
Stocks
------
Response will contain named stocks. E.g. :
```
GET http://127.0.0.1:8000/stocks
...
{
    "response": {
        "Twitter": "TWTR",
        "Apple": "AAPL",
        "Paypal": "PYPL",
        "Microsoft": "MSFT",
        "Yahoo": "YHOO"
    },
    "success": true
}
```
As you can see - response field contains dictionary  (from name to filter)

Statistics
----------
Response will contains "part" of positive/negative/neutral tweets in given period.
E.g.
```
GET http://127.0.0.1:8000/stats?q=TWTR&from=0&to=1488776745
...
{
    "response": {
        "negative": 0.18795888399412627, 
        "positive": 0.2143906020558003, 
        "neutral": 0.5976505139500734
    },
    "success": true
}
```
There you can see params:
- q - stock filter
- from - not include older tweets in calculation. Unix time
- to - not include newer tweets. Unix time.

Also - there 1 optional param ("no_neutral"). E.g.:
```
GET http://127.0.0.1:8000/stats?q=TWTR&from=0&to=1488776745&no_neutral=1
...
{
    "response": {
        "negative": 0.45907473309608543, 
        "positive": 0.5409252669039146, 
        "neutral": 0.0
    },
    "success": true
}
```

It calculates next way (see db.stock_stats):
- filter tweets by stock and time
- for each tweet get 3 values
    - positive=1 if text marked as positive, else - 0
    - negative=1 if text marked as negative, else - 0
    - neutral=1 if text marked as neutral, else - 0
- for each tweet - get user.k (if found user with given uid, else - 1.0) as k
- calculate positive * k, negative * k, neutral * k for each tweet
- get sum of this 3 values
At last part :
- if not found tweets (all values is zeros) - return 0, 0, 0
- if neutral excluded - returns positive/(positive+negative), negative/(positive+negative), 0
- if not - returns positive/(positive+negative+neutral), negative/(positive+negative+neutral), neutral/(positive+negative+neutral)

Dataset processing, error calculation
=====================================
Let's define error value for tweet next way:
- error(tweet) = 1.0 if classification result != right class
- else - error(tweet) 0.0

And define error value for list of tweets as
- errorCount(tweets) = sum(error(tweet) for tweet in tweets) 
- errorPercentage(tweets) = errorCount(tweets) / count(tweets)

For dataset processing - see scripts in "dataset" directory. 
You'll need to add your username/password/classifier ids in scripts.
Also - you'll need to install watson-developer-cloud library (use ```pip3 install pip install watson-developer-cloud```).
I used it next way:
- splitted "ds.csv" to individual subsets by split.py. This script also start training new classifiers, 
  so you'll see id's in console output
- when it trained (you can see it in Watson NLC toolkit. 
    In my case - above 1 hour for 3 classifiers)

I tested accuracy on individual classifiers on 
    "their" test subsets.
  Results:
  - negative-positive classifier: 64 error of 712 texts ~= 9% errors
  - negative-neutral classifier: 146 or 742 ~= 20%
  - negative-positive classifier: 160 of 712 ~= 22%
- when test finished - calculated error of ensemble classifier:
  256 errors on 1097 texts ~= 23%
