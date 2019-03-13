from xmlrpc.server import SimpleXMLRPCServer
import json
import dag_evaluator
import method_params
import os
import sys
import multiprocessing
import time
import argparse
from hashlib import md5

stop_server = False


def eval_dags(inputs: multiprocessing.Queue, evaluated_list):
    while True:
        try:
            ind_id, ind_dag, filename, metrics_list = inputs.get(block=False)

            ind_scores, _ind_id = dag_evaluator.safe_dag_eval(
                dag=ind_dag,
                filename=filename,
                dag_id=ind_id,
                metrics_list=metrics_list
            )

            assert ind_id == _ind_id

            evaluated_list.append([ind_id, ind_scores])
        except Exception:
            time.sleep(1)


class DagEvalServer:

    def __init__(self, n_cpus):
        self.manager = multiprocessing.Manager()
        self.evaluated_list = self.manager.list()

        if n_cpus < 0:
            n_cpus = multiprocessing.cpu_count()
        self.n_cpus = n_cpus

        self.gen_number = 0

        self.inputs = multiprocessing.Queue()

        self.processes = [multiprocessing.Process(target=eval_dags, args=(
            self.inputs,
            self.evaluated_list)
        ) for _ in range(n_cpus)]

        for p in self.processes:
            p.start()

    def submit(self, candidate_string, datafile, metrics_list):
        candidate = json.loads(candidate_string)

        sub_time = time.time()

        m = md5()
        m.update((candidate_string + str(sub_time)).encode())
        cand_id = m.hexdigest()

        self.inputs.put((cand_id, candidate, datafile, metrics_list))

        return cand_id

    def get_evaluated(self, ind_id):
        for ind in self.evaluated_list:
            if ind[0] == ind_id:
                self.evaluated_list.remove(ind)
                return json.dumps(ind)

        return json.dumps([None, None])

    def get_core_count(self):
        return json.dumps(self.n_cpus)

    def kill_workers(self):
        for p in self.processes:
            p.terminate()

    def get_param_sets(self, datafile):
        """
        Returns the set of possible values of parameters for each method
        based on the given datafile.
        :return: The JSON string containing the dictionary of the parameter 
                 values for each supported method.
        """
        return method_params.create_param_set()

    def quit(self):
        global stop_server
        stop_server = True
        return json.dumps('OK')


def parse_args():
    parser = argparse.ArgumentParser(
        description='Start server that evaluates machine learning pipelines.')

    parser.add_argument('-p', '--port-number',
                        required=True, type=int, default=80,
                        help='Port in which the server is supposed to run.')

    parser.add_argument('-n', '--n_cpus',
                        type=int, default=1,
                        help='Number of CPUs to use.')

    parser.add_argument('-c', '--config',
                        type=str,
                        help='Configuration file.')

    return parser.parse_args()


if __name__ == '__main__':

    args = parse_args()

    n_cpus = args.n_cpus

    port_number = args.port_number
    server_url = '0.0.0.0'

    if args.config:
        config = json.load(open(args.config))
        server_url = config['serverUrl']
        port_number = int(server_url.split(':')[-1])

    print('=============== Server Settings:')
    print('Server URL: ', server_url)
    print('Port Number:', port_number)
    print()

    eval_server = DagEvalServer(n_cpus)

    server = SimpleXMLRPCServer((server_url, port_number))
    server.register_instance(eval_server)

    try:
        server.serve_forever()
    except Exception as e:
        stop_server = True
        server.kill_workers()
        print("ERROR: ", str(e))
        print(repr(e))
