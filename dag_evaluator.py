import os
import sys
import time
import json
import joblib
import pprint
import traceback
import numpy as np
import pandas as pd
import networkx as nx
from available_metrics import available_metrics
from sklearn.model_selection import StratifiedKFold
from sklearn.base import ClassifierMixin, RegressorMixin
from sklearn import preprocessing, decomposition, feature_selection


import custom_models
import utils
import inspect
from dag_parser import normalize_dag


cache_dir = 'cache'
if os.path.exists('/media/ramdisk'):
    cache_dir = '/media/ramdisk/cache'
    print('Using ramdisk')

memory = joblib.Memory(cachedir=cache_dir, verbose=False)


@memory.cache
def fit_model(model, values, targets, sample_weight=None):
    isClass = isinstance(model, ClassifierMixin)
    isRegr = isinstance(model, RegressorMixin)
    isSpl = isinstance(model, custom_models.KMeansSplitter)
    if isClass or isRegr or isSpl:
        if 'sample_weight' in inspect.signature(model.fit).parameters:
            return model.fit(values, targets, sample_weight=sample_weight)
    return model.fit(values, targets)


def data_ready(req, cache):
    """
    Checks that all required data are in the data_cache

    :param req: string or list of string containing the keys of
    required data in cache
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
    :return: a single pandas.DataFrame if input is a string,
    a list of DataFrames if the input is a list of strings
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
    isarray_0 = isinstance(train_data[0], np.ndarray)
    isarray_1 = isinstance(train_data[1], np.ndarray)
    if isarray_0 and isarray_1:
        train_data = (pd.DataFrame(train_data[0]),
                      pd.Series(train_data[1]))

    data_cache[dag['input'][2]] = train_data
    models['input'] = True

    def unfinished_models():
        return [m for m in dag if m not in models]

    def data_available():
        return [m for m in dag if data_ready(dag[m][0], data_cache)]

    def next_methods():
        return [m for m in unfinished_models() if m in data_available()]

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
                sub_dags, initial_dag, input_data = \
                    dag_parser.extract_subgraphs(dag, m)
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

    def unfinished_models():
        return [m for m in dag if m not in finished]

    def data_available():
        return [m for m in dag if data_ready(dag[m][0], data_cache)]

    def next_methods():
        return [m for m in unfinished_models() if m in data_available()]

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


input_cache = {}


def eval_dag_kfold(feats, targets, dag, metrics_dict, scores_dict, times, n_splits):
    skf = StratifiedKFold(n_splits=n_splits)

    try:
        for train_idx, test_idx in skf.split(feats, targets):
            train_data = (feats.iloc[train_idx], targets.iloc[train_idx])
            test_data = (feats.iloc[test_idx], targets.iloc[test_idx])

            start_time = time.time()
            ms = train_dag(dag, train_data)
            preds = test_dag(dag, ms, test_data)
            end_time = time.time()

            for metric, config_dict in metrics_dict.items():
                method = config_dict['method']
                args = config_dict['args']
                score = method(test_data[1], preds, **args)

                scores_dict[metric].append(score)

            times.append(end_time - start_time)

        results = {
            m: {
                'mean': np.mean(scores_dict[m]),
                'std': np.std(scores_dict[m])
            } for m in scores_dict.keys()
        }

        results['time'] = np.sum(times)

        return results
    except ValueError as e:
        results = {}
        results['error'] = str(e)

        return results


def eval_dag(dag, filename, metrics_list, n_splits):
    metrics_dict = {
        metric['name']: {
            'method': available_metrics[metric['metric']],
            'args': metric['args']
        } for metric in metrics_list
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

    results = eval_dag_kfold(
        feats, targets, dag, metrics_dict, scores_dict, times, n_splits)

    return results


def safe_dag_eval(dag, filename, metrics_list, n_splits, dag_id=None):

    try:
        return eval_dag(dag, filename, metrics_list, n_splits), dag_id
    except Exception as e:
        with open('error.' + str(dag_id), 'w') as err:
            err.write(str(e) + '\n')
            for line in traceback.format_tb(e.__traceback__):
                err.write(line)
            err.write(json.dumps(dag))
    return (), dag_id
