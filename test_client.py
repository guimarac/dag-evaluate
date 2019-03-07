#!/usr/bin/env python3

import time

from rpc_client import RPCClient


client = RPCClient('http://localhost:8080')

# json_string = '[{"input": [[], "input", ["1:0"]], "1": [["1:0"], ["gaussianNB", {}], []]}, {"input": [[], "input", ["2:0"]], "2": [["2:0"], ["SVC", {"tol": 0.01, "C": 0.1, "gamma": 0.1}], []]}]'
# json_string = '[{"code": {"input": [[], "input", ["1:0"]], "1": [["1:0"], ["gaussianNB", {}], []]}, "id": 0}, {"code": {"input": [[], "input", ["2:0"]], "2": [["2:0"], ["SVC", {"tol": 0.01, "C": 0.1, "gamma": 0.1}], []]}, "id": 1}]'
json_string = '[{"input": [[], "input", ["1:0"]], "1": [["1:0"], ["gaussianNB", {}], []]}, {"input": [[], "input", ["2:0"]], "2": [["2:0"], ["SVC", {"tol": 0.01, "C": 0.1, "gamma": 0.1}], []]}]'
dataset = 'winequality-white.csv'

ids = client.submit(json_string, dataset)

print('Candidate ids:', ids)

time.sleep(6)

results = client.get_evaluated()

print('\nResults:')
for r in results:
    print(r)
