import data
from watson_developer_cloud import NaturalLanguageClassifierV1

USERNAME=""
PASSWORD=""
NEGATIVE_POSITIVE_CLASSIFIER=""
NEGATIVE_NEUTRAL_CLASSIFIER=""
NEUTRAL_POSITIVE_CLASSIFIER=""

def classify_and_calc(source, target, nlc, classifier_id):
    rows = data.read(source)
    classified = []
    errors = 0
    for i in range(0, len(rows)):
        print("{0}/{1}".format(i+1, len(rows)))
        text = rows[i][0]
        right_class_name = rows[i][1]
        class_name = nlc.classify(classifier_id, text)['top_class']
        if class_name != right_class_name:
            errors += 1
        classified.append([text, class_name])
    print(errors)
    data.write(target, classified)


if __name__ == '__main__':
    nlc = NaturalLanguageClassifierV1(username=USERNAME, password=PASSWORD)
    classify_and_calc("neg-pos-test.csv", "neg-pos-test-watson.csv", nlc, NEGATIVE_POSITIVE_CLASSIFIER)
    classify_and_calc("neu-neg-test.csv", "neu-neg-test-watson.csv", nlc, NEGATIVE_NEUTRAL_CLASSIFIER)
    classify_and_calc("neu-pos-test.csv", "neu-pos-test-watson.csv", nlc, NEUTRAL_POSITIVE_CLASSIFIER)
