__author__ = 'Martin'

from xmlrpc.server import SimpleXMLRPCServer
import json
import eval
import method_params
import os
import sys
import multiprocessing
import time
import argparse

stop_server = False

def eval_dags(inputs: multiprocessing.Queue, outputs: multiprocessing.Queue):

    while True:
        try:
            ind_id, ind_dag, filename, log_info = inputs.get(block=False)
            log_info['size'] = len(ind_dag)
            log_info['eval_start'] = time.time()
            errors, id = eval.safe_dag_eval(dag=ind_dag, filename=filename, dag_id=ind_id)
            assert ind_id == id
            log_info['eval_end'] = time.time()
            outputs.put((ind_id, errors, ind_dag, log_info))
        except Exception:
            time.sleep(1)

class DagEvalServer:

    def __init__(self, log_path, n_cpus):
        if n_cpus < 0:
            n_cpus = multiprocessing.cpu_count()
        self.n_cpus = n_cpus
        self.log_path = log_path
        os.makedirs(self.log_path, exist_ok=True)
        self.gen_number = 0
        self.inputs = multiprocessing.Queue()
        self.outputs = multiprocessing.Queue()
        self.processes = [multiprocessing.Process(target=eval_dags, args=(self.inputs, self.outputs)) for _ in range(n_cpus)]
        for p in self.processes:
            p.start()
        self.log = []

    def submit(self, json_string, datafile):

        inds = json.loads(json_string)
        log_info = dict(submitted=time.time())
        for ind in inds:
            ind_id = ind['id']
            ind_dag = ind['code']
            self.inputs.put((ind_id, ind_dag, datafile, log_info))

        return json.dumps('OK')

    def get_evaluated(self):

        evaluated = []

        try:
            while True:
                ind_id, ind_eval, ind_dag, log_info = self.outputs.get(block=False)
                kappa = ind_eval[0] if ind_eval else 'error'
                std = ind_eval[1] if ind_eval else 'error'
                eval_time = ind_eval[2] if ind_eval else 'error'
                in_queue_time = log_info['eval_start'] - log_info['submitted']
                out_queue_time = time.time() - log_info['eval_end']
                self.log.append(dict(dag=ind_dag,
                                     id=ind_id,
                                     kappa=kappa,
                                     std=std,
                                     size=log_info['size'],
                                     eval_time=eval_time,
                                     in_queue_time=in_queue_time,
                                     out_queue_time=out_queue_time))
                if len(self.log) == 100:
                    self.__write_logs()
                evaluated.append([ind_id, ind_eval])
        except:
            return json.dumps(evaluated)

    def get_core_count(self):
        return json.dumps(self.n_cpus)

    def kill_workers(self):
        for p in self.processes:
            p.terminate()


    def eval(self, json_string, datafile):
        """
        Evaluates all dags described by the json_string on the dataset with name datafile.
        :param json_string: JSON string containing the list of dags to evaluate.
        :param datafile: The dataset to evaluate the dags on.
        :return: List of tuples with the scores of each dag on the dataset
        """
        dags = json.loads(json_string)
        for dag in dags:
            self.submit(dag, datafile)

        ret = []
        while len(ret) < len(dags):
            r = self.get_evaluated()
            if not r:
                continue
            ret.append(r)

        ret = [r[1] for r in sorted(ret, key=lambda x: x[0])]
        log_file = os.path.join(self.log_path, 'log_%03d.json' % self.gen_number)
        json.dump(list(zip(dags, ret)), open(log_file, 'w'), indent=1)
        self.gen_number += 1
        return ret

    def get_param_sets(self, datafile):
        """
        Returns the set of possible values of parameters for each method based on the given datafile.
        :return: The JSON string containing the dictionary of the parameter values for each supported method.
        """
        return method_params.create_param_set()

    def quit(self):
        self.__write_logs()
        global stop_server
        stop_server = True
        return json.dumps('OK')

    def __write_logs(self):
        log_fn = os.path.join(self.log_path, 'log_%03d.json' % self.gen_number)
        with open(log_fn, 'w') as log_file:
            json.dump(self.log, log_file)
        self.log = []
        self.gen_number += 1


def parse_args():
    parser = argparse.ArgumentParser(
        description='Start server that evaluates machine learning pipelines.')

    parser.add_argument('-l', '--log_path', required=True, type=str,
                        help='Directory to save the logs.')

    parser.add_argument('-n', '--n_cpus', type=int, default=1,
                        help='Number of CPUs to use.')

    parser.add_argument('-c', '--config', type=str,
                        help='Configuration file.')

    return parser.parse_args()


if __name__ == '__main__':

    args = parse_args()

    log_path = args.log_path
    n_cpus = args.n_cpus

    port_number = 8080

    if args.config:
        config = json.load(open(args.config))
        server_url = config['serverUrl']
        port_number = int(server_url.split(':')[-1])

    print('log', log_path)
    print('port_number', port_number)
    print()

    eval_server = DagEvalServer(log_path, n_cpus)

    server = SimpleXMLRPCServer(('localhost', port_number))
    server.register_instance(eval_server)

    try:
        server.serve_forever()
    except Exception as e:
        stop_server = True
        server.kill_workers()
        print('ERROR: ', str(e))
        print(repr(e))
