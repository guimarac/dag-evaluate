import method_params
import json
import custom_models
import pandas as pd
import numpy as np
import functools
import warnings

from sklearn import metrics, preprocessing
from sklearn.model_selection import StratifiedKFold
from multiprocessing import Pool, Value, Lock


class Counter(object):
    def __init__(self, initval=0):
        self.val = Value('i', initval)
        self.lock = Lock()

    def increment(self):
        with self.lock:
            self.val.value += 1

    def value(self):
        with self.lock:
            return self.val.value

warnings.filterwarnings("ignore",category=DeprecationWarning)


def make_grid(param_set, partial_dict):
    if not param_set:
        return [{}]

    if len(param_set) == len(partial_dict):
        return [partial_dict.copy()]

    result = []
    for param_name, param_values in param_set.items():
        if param_name not in partial_dict:
            for value in param_values:
                partial_dict[param_name] = value
                result += make_grid(param_set, partial_dict.copy())
            break
    return result


def test_classifier(parameters, clsClass, feats, targets, filename):
    errors = []

    skf = StratifiedKFold(n_splits=5)

    for train_idx, test_idx in skf(feats, targets):
        cls = clsClass(**parameters)
        train_data = (feats.iloc[train_idx], targets.iloc[train_idx])
        test_data = (feats.iloc[test_idx], targets.iloc[test_idx])

        cls.fit(train_data[0], train_data[1])
        preds = cls.predict(test_data[0])

        acc = metrics.accuracy_score(test_data[1], preds)
        errors.append(acc)

    return errors, parameters


if __name__ == '__main__':

    param_set = json.loads(method_params.create_param_set())
    filename = 'ml-prove.csv'

    data = pd.read_csv('data/' + filename, sep=';')
    feats = data[data.columns[:-1]]
    targets = data[data.columns[-1]]
    le = preprocessing.LabelEncoder()

    ix = targets.index
    targets = pd.Series(le.fit_transform(targets), index=ix)

    best_results = {}

    for model_name in param_set:
        if model_name == 'SGD' or model_name == 'MLP':
            continue
        clsClass = method_params.model_names[model_name]
        if custom_models.is_predictor(clsClass):
            best_results[model_name] = (-100, [], [])
            grid = make_grid(param_set[model_name], {})
            print('running', model_name, 'total', len(grid))
            p = Pool(4)
            f = functools.partial(test_classifier, clsClass=clsClass, feats=feats, targets=targets, filename=filename)
            error_list = p.map(f, grid)

            for errors, params in error_list:
                if best_results[model_name][0] < np.mean(errors):
                    best_results[model_name] = (np.mean(errors), params, errors)

            print(model_name, best_results[model_name])

    print(best_results)
