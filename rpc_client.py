import json

from xmlrpc.client import ServerProxy


class RPCClient(object):
    def __init__(self, server_url):
        self.server_url = server_url
        self.server_proxy = ServerProxy(server_url)

    def submit(self, candidate, dataset):
        return self.server_proxy.submit(candidate, dataset)

    def get_evaluated(self):
        cand_id, metrics = json.loads(self.server_proxy.get_evaluated())

        metrics['id'] = cand_id

        return metrics

    def get_datasets(self):
        pass

    def get_metrics(self):
        pass
