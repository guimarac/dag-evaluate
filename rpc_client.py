import json
import time

from xmlrpc.client import ServerProxy
# from xmlrpc.client import Fault


class RPCClient(object):
    def __init__(self, server_url):
        self.server_url = server_url
        self.server_proxy = ServerProxy(server_url)

    def evaluate_pipeline(self, candidate, dataset, metrics_list):
        _dataset = dataset + '.csv'

        cand_id = self._submit(candidate, _dataset, metrics_list)

        return cand_id, self._get_evaluated(cand_id)

    def _submit(self, candidate, dataset, metrics_list):
        return self.server_proxy.submit(candidate, dataset, metrics_list)

    def _get_evaluated(self, candidate_id):
        attempts = 0
        limit = 20
        step = 2

        ev_id, metrics = json.loads(
            self.server_proxy.get_evaluated(candidate_id))

        while ev_id != candidate_id and attempts <= limit:
            time.sleep(attempts)
            attempts += step

            ev_id, metrics = json.loads(
                self.server_proxy.get_evaluated(candidate_id))

        metrics['id'] = ev_id

        return metrics

    def get_datasets(self):
        pass

    def get_metrics(self):
        pass
