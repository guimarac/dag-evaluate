import json

from xmlrpc.client import ServerProxy


class RPCClient(object):
    def __init__(self, server_url):
        self.server_url = server_url
        self.server_proxy = ServerProxy(server_url)

    def submit(self, candidate, dataset):
        return self.server_proxy.submit(candidate, dataset)

    def get_evaluated(self):
        ev_lst = json.loads(self.server_proxy.get_evaluated())

        results = []

        for ev in ev_lst:
            cand_id = ev[0]
            metrics = ev[1]

            results.append(dict(
                id=cand_id,
                mean=metrics[0],
                std=metrics[1],
                time=metrics[2]
            ))

        return results

    def get_datasets(self):
        pass

    def get_metrics(self):
        pass
