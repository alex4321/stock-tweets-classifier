import random
import data
from watson_developer_cloud import NaturalLanguageClassifierV1

USERNAME=""
PASSWORD=""


def cls_to_text(cls):
    if int(cls) == 0:
        return "neutral"
    elif int(cls) > 0:
        return "positive"
    else:
        return "negative"


def split(splitter, data):
    to = int(len(data) * splitter)
    return data[:to], data[to:]


def save_subset(cls1, cls2, path):
    to = min(len(cls1), len(cls2))
    data.write(path, cls1[:to] + cls2[:to])


if __name__ == '__main__':
    source = list(map(lambda row: [row[1], cls_to_text(row[2])],
                      data.read("ds.csv")))
    random.shuffle(source)
    nlc = NaturalLanguageClassifierV1(username=USERNAME, password=PASSWORD)

    splitter = 0.7
    positive = list(filter(lambda row: row[1] == "positive", source))
    negative = list(filter(lambda row: row[1] == "negative", source))
    neutral = list(filter(lambda row: row[1] == "neutral", source))
    positive_train, positive_test = split(splitter, positive)
    negative_train, negative_test = split(splitter, negative)
    neutral_train, neutral_test = split(splitter, neutral)

    save_subset(negative_train, positive_train, "neg-pos-train.csv")
    save_subset(negative_test, positive_test, "neg-pos-test.csv")
    with open("neg-pos-train.csv", "r", encoding="utf-8") as source:
        print(nlc.create(source, "NegativePositive", "en"))

    save_subset(neutral_train, positive_train, "neu-pos-train.csv")
    save_subset(neutral_test, positive_test, "neu-pos-test.csv")
    with open("neu-pos-train.csv", "r", encoding="utf-8") as source:
        print(nlc.create(source, "NeutralPositive", "en"))

    save_subset(neutral_train, negative_train, "neu-neg-train.csv")
    save_subset(neutral_test, negative_test, "neu-neg-test.csv")
    with open("neu-neg-train.csv", "r", encoding="utf-8") as source:
        print(nlc.create(source, "NeutralNegative", "en"))