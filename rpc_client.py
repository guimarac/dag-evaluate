import json
import time

from xmlrpc.client import ServerProxy


class RPCClient(object):
    def __init__(self, server_url):
        self.server_url = server_url
        self.server_proxy = ServerProxy(server_url)

    def evaluate_pipeline(self, candidate, dataset, metrics_list, n_splits, timeout):
        _dataset = dataset + '.csv'

        cand_id = self._submit(candidate, _dataset, metrics_list, n_splits, timeout)

        return self._get_evaluated(cand_id)

    def _submit(self, candidate, dataset, metrics_list, n_splits, timeout):
        return self.server_proxy.submit(
            candidate, dataset, metrics_list, n_splits, timeout)

    def _get_evaluated(self, candidate_id):
        attempts = 0
        step = 2

        ev_id, results = json.loads(
            self.server_proxy.get_evaluated(candidate_id))

        while ev_id != candidate_id:
            time.sleep(attempts)
            attempts += step

            ev_id, results = json.loads(
                self.server_proxy.get_evaluated(candidate_id))

        results['id'] = ev_id

        if 'error' in results.keys():
            raise ValueError(results['error'])

        return results

    def _get_evaluated_time(self, candidate_id):
        attempts = 0
        limit = 20
        step = 2

        ev_id, results = json.loads(
            self.server_proxy.get_evaluated(candidate_id))

        while ev_id != candidate_id and attempts <= limit:
            time.sleep(attempts)
            attempts += step

            ev_id, results = json.loads(
                self.server_proxy.get_evaluated(candidate_id))

        results['id'] = ev_id

        if 'error' in results.keys():
            raise ValueError(results['error'])

        return results

    def get_datasets(self):
        pass

    def get_metrics(self):
        pass
