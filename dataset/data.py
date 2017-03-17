import csv


def read(source):
    with open(source, "r", encoding="utf-8") as src:
        return list(csv.reader(src))


def write(target, data):
    with open(target, "w", encoding="utf-8", newline="") as file:
        csv.writer(file).writerows(data)