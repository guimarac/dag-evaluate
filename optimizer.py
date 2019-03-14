import argparse
import json

from rpc_client import RPCClient


class Optimizer:
    def __init__(self, server_url):
        self.client = RPCClient(server_url)

    def evaluate_pipeline(self, candidate, dataset, metrics_list):
        cand_id, metrics = self.client.evaluate_pipeline(
            candidate, dataset, metrics_list)

        return cand_id, metrics

    def run(self, dataset, metrics_list):
        candidate = '{"input": [[], "input", ["1:0"]], "1": [["1:0"], ["gaussianNB", {}], []]}'

        cand_id, metrics = self.evaluate_pipeline(
            candidate, dataset, metrics_list)

        print(cand_id)
        print()
        print(metrics)

        return candidate


def parse_args():
    parser = argparse.ArgumentParser(
        description='TODO')

    parser.add_argument('-d', '--dataset',
                        required=True, type=str,
                        help='Name of the dataset.')

    parser.add_argument('-p', '--optimizer_config',
                        type=str,
                        help='File that configures the optimizer.')

    parser.add_argument('-s', '--server_config',
                        type=str,
                        help='File that configures the connection with '
                             'the server.')

    return parser.parse_args()


def main(args):
    server_url = 'http://automl.speed.dcc.ufmg.br:80'

    if args.server_config is not None:
        server_url = json.load(open(args.server_config))['serverUrl']

    metrics_list = [{
        'metric': 'f1',
        'args': {'average': 'micro'},
        'name': 'f1_score'
    }]

    if args.optimizer_config is not None:
        config = json.load(open(args.optimizer_config))
        metrics_list = config['metrics']

    print('----- RPC Client configuration -----')
    print('Server url:', server_url)
    print('Metrics:   ', metrics_list)
    print('------------------------------------\n')

    optimizer = Optimizer(server_url)
    best_pipeline = optimizer.run(args.dataset, metrics_list)

    print('\n------------------------------------')
    print('Best pipeline:')
    print(best_pipeline)


if __name__ == '__main__':
    args = parse_args()

    main(args)
