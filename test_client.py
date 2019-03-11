#!/usr/bin/env python3

import time

from rpc_client import RPCClient

client = RPCClient('http://localhost:8080')
# client = RPCClient('http://automl.speed.dcc.ufmg.br:80')

json_string =   '{"input": [[], "input", ["1:0"]], "1": [["1:0"], ["gaussianNB", {}], []]}'
dataset = 'winequality-white.csv'

metrics_list = [
    {'metric': 'accuracy', 'args': {}, 'name': 'accuracy'},
    {'metric': 'f1', 'args': {'average': 'micro'}, 'name': 'f1_micro'},
    {'metric': 'f1', 'args': {'average': 'macro'}, 'name': 'f1_macro'},
    {'metric': 'f1', 'args': {'average': 'weighted'}, 'name': 'f1_weighted'}
]

cand_id = client.submit(json_string, dataset, metrics_list)

print('Candidate id:', cand_id)

time.sleep(6)

results = client.get_evaluated()

print('\nResults:')
print(results)
