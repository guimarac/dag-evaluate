__author__ = "Martin Pilat"

import sys
import time
import joblib
import pprint
import os

import numpy as np
import pandas as pd
from sklearn import preprocessing, decomposition, feature_selection, metrics
from sklearn.model_selection import StratifiedKFold

import networkx as nx

import custom_models
import utils
import inspect

from sklearn.base import ClassifierMixin, RegressorMixin

cache_dir = 'cache'
if os.path.exists('/media/ramdisk'):
    cache_dir = '/media/ramdisk/cache'
    print('Using ramdisk')

memory = joblib.Memory(cachedir=cache_dir, verbose=False)


@memory.cache
def fit_model(model, values, targets, sample_weight=None):
    if isinstance(model, ClassifierMixin) or isinstance(model, RegressorMixin) or isinstance(model, custom_models.KMeansSplitter):
        if 'sample_weight' in inspect.signature(model.fit).parameters:
            return model.fit(values, targets, sample_weight=sample_weight)
    return model.fit(values, targets)


def data_ready(req, cache):
    """
    Checks that all required data are in the data_cache

    :param req: string or list of string containing the keys of required data in cache
    :param cache: dictionary with the computed data
    :return: Boolean indicating whether all required data are in cache
    """
    if not isinstance(req, list):
        req = [req]
    return all([r in cache for r in req])


def get_data(data_list, data_cache):
    """
    Gets the data specified by the keys in the data_list from the data_cache

    :param data_list: string or list of strings
    :param data_cache: dictionary containing the stored data
    :return: a single pandas.DataFrame if input is a string, a list of DataFrames if the input is a list of strings
    """
    if not isinstance(data_list, list):
        data_list = [data_list]
    tmp = [data_cache[d] for d in data_list]
    if len(tmp) == 1:
        return tmp[0]
    res = ([t[0] for t in tmp], [t[1] for t in tmp])
    return res


def append_all(data_frames):
    if not isinstance(data_frames, list):
        return data_frames
    res = data_frames[0]
    for i in range(1, len(data_frames)):
        res.append(data_frames[i])
    return res


def train_dag(dag, train_data, sample_weight=None):
    models = dict()
    data_cache = dict()

    # happens inside booster
    if isinstance(train_data[0], np.ndarray) and isinstance(train_data[1], np.ndarray):
        train_data = (pd.DataFrame(train_data[0]), pd.Series(train_data[1]))

    data_cache[dag['input'][2]] = train_data
    models['input'] = True

    def unfinished_models(): return [m for m in dag if m not in models]

    def data_available(): return [
        m for m in dag if data_ready(dag[m][0], data_cache)]

    def next_methods(): return [
        m for m in unfinished_models() if m in data_available()]

    while next_methods():

        for m in next_methods():
            # print("Processing:", m)

            # obtain the data
            features, targets, *rest = get_data(dag[m][0], data_cache)
            if rest:
                sample_weight = rest[0]
            ModelClass, model_params = utils.get_model_by_name(dag[m][1])
            out_name = dag[m][2]
            if dag[m][1][0] == 'stacker':
                sub_dags, initial_dag, input_data = extract_subgraphs(dag, m)
                model_params = dict(sub_dags=sub_dags, initial_dag=initial_dag)
                model = ModelClass(**model_params)
                features, targets = data_cache[input_data]
            elif isinstance(out_name, list):
                model = ModelClass(len(out_name), **model_params)
            else:
                if isinstance(ModelClass(), feature_selection.SelectKBest):
                    if 'feat_frac' not in model_params:
                        model_params['feat_frac'] = 1.0
                    model_params = model_params.copy()
                    model_params['k'] = max(
                        1, int(model_params['feat_frac'] * (features.shape[1] - 1)))
                    del model_params['feat_frac']
                if isinstance(ModelClass(), decomposition.PCA):
                    if 'feat_frac' not in model_params:
                        model_params['feat_frac'] = 1.0
                    model_params = model_params.copy()
                    model_params['n_components'] = max(
                        1, int(model_params['feat_frac'] * (features.shape[1] - 1)))
                    del model_params['feat_frac']
                model = ModelClass(**model_params)

            # build the model
            # some models cannot handle cases with only one class, we also need to check we are not working with a list
            # of inputs for an aggregator
            if custom_models.is_predictor(model) and isinstance(targets, pd.Series) and len(targets.unique()) == 1:
                model = custom_models.ConstantModel(targets.iloc[0])
            models[m] = fit_model(model, features, targets,
                                  sample_weight=sample_weight)
            # needed to update model if the result was cached
            model = models[m]

            # use the model to process the data
            if isinstance(model, custom_models.Stacker):
                data_cache[out_name] = model.train, targets.ix[model.train.index]
                continue
            if isinstance(model, custom_models.Aggregator):
                data_cache[out_name] = model.aggregate(features, targets)
                continue
            if custom_models.is_transformer(model):
                trans = model.transform(features)
            else:              # this is a classifier not a preprocessor
                trans = features                # the data do not change
                if isinstance(features, pd.DataFrame):
                    targets = pd.Series(
                        list(model.predict(features)), index=features.index)
                else:  # this should happen only inside booster
                    targets = pd.Series(list(model.predict(features)))

            # save the outputs
            # the previous model divided the data into several data-sets
            if isinstance(trans, list):
                if isinstance(model, custom_models.KMeansSplitter) and sample_weight is not None:
                    trans = [(x, targets.loc[x.index], sample_weight[model.weight_idx[i]])
                             for i, x in enumerate(trans)]  # need to divide the targets and the weights
                else:
                    trans = [(x, targets.loc[x.index])
                             for x in trans]     # need to divide the targets
                for i in range(len(trans)):
                    # save all the data to the cache
                    data_cache[out_name[i]] = trans[i]
            else:
                if isinstance(features, pd.DataFrame):
                    # we have only one output, can be numpy array
                    trans = pd.DataFrame(trans, index=features.index)
                else:
                    trans = pd.DataFrame(trans)
                trans.dropna(axis='columns', how='all', inplace=True)
                data_cache[out_name] = (
                    trans, targets)                 # save it

    return models


def test_dag(dag, models, test_data, output='preds_only'):
    data_cache = dict()
    finished = dict()

    if isinstance(test_data[0], np.ndarray):
        test_data = (pd.DataFrame(test_data[0]), test_data[1])

    if isinstance(test_data[1], np.ndarray):
        test_data = (test_data[0], pd.Series(
            test_data[1], index=test_data[0].index))

    data_cache[dag['input'][2]] = test_data
    finished['input'] = True

    def unfinished_models(): return [m for m in dag if m not in finished]

    def data_available(): return [
        m for m in dag if data_ready(dag[m][0], data_cache)]

    def next_methods(): return [
        m for m in unfinished_models() if m in data_available()]

    while next_methods():

        for m in next_methods():

            # obtain the data
            features, targets = get_data(dag[m][0], data_cache)
            model = models[m]
            out_name = dag[m][2]

            # we got empty dataset (after same division)
            if isinstance(features, pd.DataFrame) and features.empty:
                # and we should divide it further
                if isinstance(out_name, list):
                    for o in out_name:
                        data_cache[o] = (features, targets)
                else:
                    data_cache[out_name] = (features, targets)
                finished[m] = True
                continue

            # use the model to process the data
            if isinstance(model, custom_models.Aggregator):
                data_cache[out_name] = model.aggregate(features, targets)
                finished[m] = True
                continue
            elif custom_models.is_transformer(model):
                trans = model.transform(features)
                targets = pd.Series(targets, index=features.index)
            else:                                                       # this is a classifier not a preprocessor
                trans = features                                        # the data do not change
                if isinstance(features, pd.DataFrame):
                    targets = pd.Series(
                        list(model.predict(features)), index=features.index)
                else:
                    targets = pd.Series(list(model.predict(features)))

            # save the outputs
            # the previous model divided the data into several data-sets
            if isinstance(trans, list):
                trans = [(x, targets.loc[x.index])
                         for x in trans]      # need to divide the targets
                for i in range(len(trans)):
                    # save all the data to the cache
                    data_cache[out_name[i]] = trans[i]
            else:
                if isinstance(features, pd.DataFrame):
                    # we have only one output, can be numpy array
                    trans = pd.DataFrame(trans, index=features.index)
                else:
                    trans = pd.DataFrame(trans)
                trans.dropna(axis='columns', how='all', inplace=True)
                data_cache[out_name] = (
                    trans, targets)                 # save it

            finished[m] = True

    if output == 'all':
        return data_cache['output']
    if output == 'preds_only':
        return data_cache['output'][1]
    if output == 'feats_only':
        return data_cache['output'][0]

    raise AttributeError(output, 'is not a valid output type')


def normalize_spec(spec):
    ins, mod, outs = spec
    if len(ins) == 1:
        ins = ins[0]
    if len(outs) == 1:
        outs = outs[0]
    if len(outs) == 0:
        outs = 'output'
    return ins, mod, outs


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


def normalize_dag(dag):

    dag = process_boosters(dag)

    normalized_dag = {k: normalize_spec(v) for (k, v) in dag.items()}

    original_len = len(normalized_dag)

    aliases = {normalized_dag[k][0]: normalized_dag[k][2]
               for k in normalized_dag if normalized_dag[k][1][0] == "copy"}
    normalized_dag = {
        k: v for (k, v) in normalized_dag.items() if v[1][0] != 'copy'}

    new_len = len(normalized_dag)

    rev_aliases = {v: k for k in aliases for v in aliases[k]}
    for i in range(original_len - new_len):
        normalized_dag = {k: ((rev_aliases[ins] if not isinstance(ins, list) and ins in rev_aliases else ins), mod, out)
                          for (k, (ins, mod, out)) in normalized_dag.items()}

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
                        input_name, ['booster', {'sub_dags': sub_dags}], dag[node][2])
                    sub_dags = []
                    break
        elif spec[1][0] in ['booster', 'booEnd']:
            continue
        else:
            processed_dag[k] = spec

    return processed_dag


input_cache = {}


def eval_dag(dag, filename, dag_id=None):
    metrics_dict = {
        'accuracy': metrics.accuracy_score,
        'f1': metrics.f1_score,
        'recall': metrics.recall_score,
        'precision': metrics.precision_score
    }
    scores_dict = {metric: [] for metric in metrics_dict.keys()}

    dag = normalize_dag(dag)

    if filename not in input_cache:
        input_cache[filename] = pd.read_csv('data/' + filename, sep=';')

    data = input_cache[filename]

    feats = data[data.columns[:-1]]
    targets = data[data.columns[-1]]

    le = preprocessing.LabelEncoder()

    ix = targets.index
    targets = pd.Series(le.fit_transform(targets), index=ix)

    times = []

    start_time = time.time()

    skf = StratifiedKFold(n_splits=5)

    for train_idx, test_idx in skf.split(feats, targets):
        train_data = (feats.iloc[train_idx], targets.iloc[train_idx])
        test_data = (feats.iloc[test_idx], targets.iloc[test_idx])

        start_time = time.time()
        ms = train_dag(dag, train_data)
        end_time = time.time()

        preds = test_dag(dag, ms, test_data)

        for metric, method in metrics_dict.items():
            if metric != 'accuracy':
                sc = method(test_data[1], preds, average='macro')
            else:
                sc = method(test_data[1], preds)
            scores_dict[metric].append(sc)

        times.append(end_time - start_time)

    results = {
        m: {
            'mean': np.mean(scores_dict[m]),
            'std': np.std(scores_dict[m])
        } for m in scores_dict.keys()
    }

    results['time'] = {
        'mean': np.mean(times),
        'std': np.std(times)
    }

    return results


def safe_dag_eval(dag, filename, dag_id=None):

    import traceback
    import json
    try:
        return eval_dag(dag, filename, dag_id), dag_id
    except Exception as e:
        with open('error.' + str(dag_id), 'w') as err:
            err.write(str(e) + '\n')
            for line in traceback.format_tb(e.__traceback__):
                err.write(line)
            err.write(json.dumps(dag))
    return (), dag_id


if __name__ == '__main__':

    datafile = "ml-prove.csv"
    dags = utils.read_json('test_err.json')

    results = dict()

    remaining_dags = [d for d in enumerate(dags) if str(d[0]) not in results]
    print("Starting...", len(remaining_dags))
    pprint.pprint(remaining_dags)

    for e in map(lambda x: safe_dag_eval(x[1], datafile, x[0]), remaining_dags):
        results[str(e[1])] = e
        print(e)
        print("Model %4d: Cross-validation error: %.5f (+-%.5f)" %
              (e[1], e[0][0], e[0][1]))
        sys.stdout.flush()

    print("-" * 80)
    best_error = sorted(
        results.values(), key=lambda x: x[0][0] - 2 * x[0][1], reverse=True)[0]
    print("Best model CV error: %.5f (+-%.5f)" %
          (best_error[0][0], best_error[0][1]))

    import pprint
    print("Model: ", end='')
    pprint.pprint(dags[best_error[1]])
