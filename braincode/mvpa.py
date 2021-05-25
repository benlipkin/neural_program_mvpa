from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from data import DataLoader
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.svm import LinearSVC
from tqdm import tqdm


class MVPA:
    def __init__(self, network, feature):
        self._network = network
        self._feature = feature
        self._loader = DataLoader(self.network, self.feature)
        self._score = None
        self._null = None

    @property
    def network(self):
        return self._network

    @property
    def feature(self):
        return self._feature

    @property
    def score(self):
        return self._score

    @property
    def null(self):
        return self._null

    @property
    def pval(self):
        return (self.score < self.null).sum() / self.null.size

    @staticmethod
    def _shuffle_within_runs(y_in, runs):
        y_out = np.zeros(y_in.shape)
        for run in np.unique(runs):
            y_out[runs == run] = np.random.permutation(y_in[runs == run])
        return y_out

    @staticmethod
    def _cross_validate_sparse_model(X, y, runs):
        classes = np.unique(y)
        classifier = LinearSVC(max_iter=1e5)
        cmat = np.zeros((classes.size, classes.size))
        for train, test in LeaveOneGroupOut().split(X, y, runs):
            model = classifier.fit(X[train], y[train])
            cmat += confusion_matrix(y[test], model.predict(X[test]), labels=classes)
        return np.trace(cmat) / cmat.sum()

    @staticmethod
    def _cross_validate_dense_model(X, y, runs):
        raise NotImplementedError()  # resume here

    def _run_mvpa(self, mode):
        subjects = sorted(self._loader.datadir.iterdir())
        scores = np.zeros(len(subjects))
        for idx, subject in enumerate(subjects):
            X, y, runs = self._loader.get_xyr(subject)
            if mode == "null":
                y = self._shuffle_within_runs(y, runs)
            if y.ndim > 1:
                scores[idx] = self._cross_validate_dense_model(X, y, runs)
            else:
                scores[idx] = self._cross_validate_sparse_model(X, y, runs)
        return scores.mean()

    def _run_pipeline(self, mode, iters=1):
        assert mode in ["score", "null"]
        fname = Path(__file__).parent.joinpath(
            "outputs", f"{mode}_{self.feature}_{self.network}.npy"
        )
        if fname.exists():
            setattr(self, "_" + mode, np.load(fname, allow_pickle=True))
            return
        samples = np.zeros((iters))
        for idx in tqdm(range(iters)):
            score = self._run_mvpa(mode)
            if mode == "score":
                self._score = score
                np.save(fname, self.score)
                return
            samples[idx] = score
        self.null = samples
        np.save(fname, self.null)

    def _plot_results(self):
        plt.hist(self.null, bins=25, color="lightblue", edgecolor="black")
        plt.axvline(self.score, color="black", linewidth=3)
        plt.xlim(
            {
                "code": [0.4, 0.9],
                "content": [0.4, 0.65],
                "structure": [0.25, 0.55],
                # "bow":[],
                # "tfidf":[],
            }[self.feature]
        )
        plt.savefig(
            Path(__file__).parent.joinpath(
                "plots", "mvpa", f"{self.feature}_{self.network}.png"
            )
        )
        plt.clf()

    def run(self, perms=True, iters=1000):
        self._run_pipeline("score")
        if perms:
            self._run_pipeline("null", iters)
            self._plot_results()
        return self
