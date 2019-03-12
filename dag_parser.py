# -*- coding: utf-8 -*-

import numpy as np
import networkx as nx

import utils


def normalize_spec(spec):
    ins, mod, outs = spec
    if len(ins) == 1:
        ins = ins[0]
    if len(outs) == 1:
        outs = outs[0]
    if len(outs) == 0:
        outs = 'output'
    return ins, mod, outs


def normalize_dag(dag):
    dag = process_boosters(dag)

    normalized_dag = {k: normalize_spec(v)
                      for (k, v) in dag.items()}

    original_len = len(normalized_dag)

    aliases = {normalized_dag[k][0]: normalized_dag[k][2]
               for k in normalized_dag
               if normalized_dag[k][1][0] == "copy"}
    normalized_dag = {
        k: v for (k, v) in normalized_dag.items() if v[1][0] != 'copy'}

    new_len = len(normalized_dag)

    rev_aliases = {v: k for k in aliases for v in aliases[k]}
    for i in range(original_len - new_len):
        normalized_dag = {k: ((rev_aliases[ins]
                          if not isinstance(ins, list) and
                          ins in rev_aliases else ins), mod, out)
                          for (k, (ins, mod, out)) in
                          normalized_dag.items()}

    return normalized_dag


def process_boosters(dag):

    dag_nx = utils.dag_to_nx(dag)

    processed_dag = dict()
    sub_dags = []
    for k, spec in dag.items():
        if spec[1][0] == 'booBegin':
            input_name = spec[0]
            for node in nx.dfs_preorder_nodes(dag_nx, k):
                node_type = dag[node][1][0]
                if node == k:
                    continue
                if node_type == 'booster':
                    sub_dags.append(dag[node][1][2])
                if node_type == 'booEnd':
                    sub_dags = [normalize_dag(sd) for sd in sub_dags]
                    processed_dag[k] = (
                        input_name, ['booster', {'sub_dags': sub_dags}],
                        dag[node][2])
                    sub_dags = []
                    break
        elif spec[1][0] in ['booster', 'booEnd']:
            continue
        else:
            processed_dag[k] = spec

    return processed_dag


def extract_subgraphs(dag, node):
    out = []

    dag_nx = utils.dag_to_nx(dag)
    reverse_dag_nx = dag_nx.reverse()

    for p in dag_nx.predecessors(node):
        out.append({k: v for k, v in dag.items() if k in list(
            nx.dfs_preorder_nodes(reverse_dag_nx, p))})

    common_nodes = [n for n in out[0] if all((n in o for o in out))]

    toposort = list(nx.topological_sort(dag_nx))
    sorted_common = sorted(common_nodes, key=lambda k: -toposort.index(k))

    inputs = np.unique([dag[n][0] for n in dag_nx.successors(
        sorted_common[0]) if any([n in o for o in out])])
    assert len(inputs) == 1
    input_id = inputs[0]
    remove_common = sorted_common

    nout = []

    for o in out:
        no = dict()
        no['input'] = ([], 'input', input_id)
        for k, v in o.items():
            if k in remove_common:
                continue
            ins = v[2]
            if not isinstance(ins, list):
                ins = [ins]
            if ins[0] in dag[node][0]:
                no[k] = v[0], v[1], 'output'
                continue
            no[k] = v
        nout.append(no)

    initial_dag = {k: v for k, v in dag.items() if k in common_nodes}
    for k, v in initial_dag.items():
        if isinstance(v[2], list) and input_id in v[2]:
            initial_dag[k] = (
                v[0], v[1], [x if x != input_id else 'output' for x in v[2]])
            break
        if v[2] == input_id:
            initial_dag[k] = (v[0], v[1], 'output')

    return nout, initial_dag, input_id

