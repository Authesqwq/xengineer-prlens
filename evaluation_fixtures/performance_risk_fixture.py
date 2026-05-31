"""EVALUATION FIXTURE ONLY — do not use in production."""

import requests

def load_all_lines(filename):
    with open(filename, "r") as f:
        return f.read()

def find_duplicates(items):
    result = set()
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                result.add(items[i])
    return list(result)

def fetch_all_statuses(urls):
    results = []
    for url in urls:
        r = requests.get(url)
        results.append(r.status_code)
    return results

def download_large(url):
    return requests.get(url).content
