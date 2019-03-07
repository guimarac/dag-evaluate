#!/usr/bin/env python3

import time

from rpc_client import RPCClient


client = RPCClient('http://localhost:8080')

json_string =   '{"input": [[], "input", ["1:0"]], "1": [["1:0"], ["gaussianNB", {}], []]}'
dataset = 'winequality-white.csv'

cand_id = client.submit(json_string, dataset)

print('Candidate id:', cand_id)

time.sleep(6)

results = client.get_evaluated()

print('\nResults:')
for r in results:
    print(r)
