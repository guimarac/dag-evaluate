from sklearn import metrics


available_metrics = {
    'accuracy': metrics.accuracy_score,
    'f1': metrics.f1_score,
    'recall': metrics.recall_score,
    'precision': metrics.precision_score
}

metrics_str = {
    'accuracy': 'sklearn.metrics.accuracy_score',
    'f1': 'sklearn.metrics.f1_score',
    'recall': 'sklearn.metrics.recall_score',
    'precision': 'sklearn.metrics.precision_score'
}


def get_available_metrics():
    return metrics_str
