import argparse
import json

from rpc_client import RPCClient


class Optimizer:
    def __init__(self, server_url, dataset, metrics_list, n_splits, timeout):
        self.client = RPCClient(server_url)
        self.dataset = dataset
        self.metrics_list = metrics_list
        self.n_splits = n_splits
        self.timeout = timeout

    def evaluate_pipeline(self, candidate):
        results = self.client.evaluate_pipeline(
            candidate, self.dataset, self.metrics_list, self.n_splits, self.timeout)

        return results

    def run(self):
        # candidate = '{"input": [[], "input", ["1:0"]], "1": [["1:0"], ["gaussianNB", {}], []]}'
        candidate = '{"input": [[], "input", ["1:0"]], "MLP": [["1:0"], ["MLP", {"max_iter": 20, "verbose": "True"}], []]}'

        results = self.evaluate_pipeline(candidate)

        print('Results:')
        print(json.dumps(results, indent=2, sort_keys=True))

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

    splits = 5

    if args.optimizer_config is not None:
        config = json.load(open(args.optimizer_config))
        metrics_list = config['metrics']
        splits = config['splits']
        timeout = config['timeout']

    print('----- RPC Client configuration -----')
    print('Server url:', server_url)
    print('\nDataset:', args.dataset)
    print('\nMetrics:', metrics_list)
    print('\nSplits:', splits)
    print('\n------------------------------------')

    optimizer = Optimizer(server_url, args.dataset, metrics_list, splits, timeout)
    best_pipeline = optimizer.run()

    print('\n------------------------------------')
    print('Best pipeline:')
    print(best_pipeline)


if __name__ == '__main__':
    args = parse_args()

    main(args)
