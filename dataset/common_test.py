import data
from watson_developer_cloud import NaturalLanguageClassifierV1

USERNAME=""
PASSWORD=""
CLASSIFIERS=[]

def read_test_data():
    test = data.read("neg-pos-test.csv") + data.read("neu-neg-test.csv") + data.read("neu-pos-test.csv")
    unique_test = []
    unique_texts = set()
    for row in test:
        if row[0] not in unique_texts:
            unique_texts.add(row[0])
            unique_test.append(row)
    return unique_test


def classify(nlc, text):
    votes = {}
    max_class = None
    for classifier_id in CLASSIFIERS:
        top = nlc.classify(classifier_id, text)['top_class']
        votes[top] = votes.get(top, 0) + 1
        if max_class is None or votes.get(max_class, 0) < votes[top]:
            max_class = top
    if votes[max_class] < 2:
        return "neutral"
    else:
        return max_class


if __name__ == '__main__':
    nlc = NaturalLanguageClassifierV1(username=USERNAME, password=PASSWORD)
    test_data = read_test_data()
    predictions = []
    data.write("test-full.csv", test_data)
    errors = 0
    for i in range(0, len(test_data)):
        print("{0}/{1}".format(i+1, len(test_data)))
        text = test_data[i][0]
        right_class = test_data[i][1]
        prediction_class = classify(nlc, text)
        predictions.append([text, prediction_class])
        if prediction_class != right_class:
            errors += 1
    data.write("test-full-watson.csv", predictions)
    print("Errors : {0}".format(errors))
