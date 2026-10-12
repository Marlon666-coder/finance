"""Model AI untuk memprediksi arah BTC (naik/turun candle berikutnya).

Dua implementasi:
  1. Kalau scikit-learn terpasang → pakai RandomForest (lebih kuat).
  2. Kalau tidak → fallback Logistic Regression yang ditulis MURNI Python
     (tanpa library), supaya tetap jalan di mana saja & bisa diuji.

Model disimpan ke file JSON (untuk logreg) atau pickle (untuk sklearn), jadi
dilatih sekali lalu dipakai berulang.

⚠️ AI ini TETAP sering salah. Pasar mendekati acak. Bukan nasihat finansial.
"""

from __future__ import annotations

import json
import math
import os
from typing import List, Optional

try:
    from sklearn.ensemble import RandomForestClassifier  # type: ignore
    import pickle
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

LOGREG_PATH = "model_logreg.json"
SKLEARN_PATH = "model_rf.pkl"


# ----------------------------------------------------------------------------
# Util: standardisasi fitur (mean 0, std 1) — penting untuk logreg.
# ----------------------------------------------------------------------------
def _standardize_fit(X: List[List[float]]):
    cols = list(zip(*X))
    means = [sum(c) / len(c) for c in cols]
    stds = []
    for c, m in zip(cols, means):
        var = sum((v - m) ** 2 for v in c) / max(len(c) - 1, 1)
        stds.append(math.sqrt(var) or 1.0)
    return means, stds


def _standardize_apply(X, means, stds):
    return [[(v - m) / s for v, m, s in zip(row, means, stds)] for row in X]


# ----------------------------------------------------------------------------
# Logistic Regression murni Python (gradient descent).
# ----------------------------------------------------------------------------
def _sigmoid(z: float) -> float:
    if z < -60:
        return 0.0
    if z > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def _train_logreg(X, y, epochs=400, lr=0.1, l2=0.001):
    n_features = len(X[0])
    w = [0.0] * n_features
    b = 0.0
    m = len(X)
    for _ in range(epochs):
        dw = [0.0] * n_features
        db = 0.0
        for xi, yi in zip(X, y):
            z = b + sum(wj * xj for wj, xj in zip(w, xi))
            pred = _sigmoid(z)
            err = pred - yi
            for j in range(n_features):
                dw[j] += err * xi[j]
            db += err
        for j in range(n_features):
            w[j] -= lr * (dw[j] / m + l2 * w[j])
        b -= lr * (db / m)
    return w, b


def _predict_logreg(w, b, row) -> float:
    z = b + sum(wj * xj for wj, xj in zip(w, row))
    return _sigmoid(z)


# ----------------------------------------------------------------------------
# API publik
# ----------------------------------------------------------------------------
class Model:
    """Pembungkus model: train, predict, save, load."""

    def __init__(self, kind: str, payload: dict):
        self.kind = kind          # "sklearn" | "logreg"
        self.payload = payload    # berisi weights / objek model + scaler

    # ---- Training ----
    @classmethod
    def train(cls, X, y, feature_names, prefer_sklearn=True) -> "Model":
        if prefer_sklearn and _HAS_SKLEARN:
            clf = RandomForestClassifier(
                n_estimators=200, max_depth=6, min_samples_leaf=20,
                random_state=42, n_jobs=-1,
            )
            clf.fit(X, y)
            return cls("sklearn", {"model": clf, "features": feature_names})
        # Fallback logreg (standardisasi dulu).
        means, stds = _standardize_fit(X)
        Xs = _standardize_apply(X, means, stds)
        w, b = _train_logreg(Xs, y)
        return cls("logreg", {
            "w": w, "b": b, "means": means, "stds": stds,
            "features": feature_names,
        })

    # ---- Prediksi: kembalikan probabilitas NAIK (0..1) ----
    def predict_proba_up(self, row: List[float]) -> float:
        if self.kind == "sklearn":
            clf = self.payload["model"]
            proba = clf.predict_proba([row])[0]
            classes = list(clf.classes_)
            idx = classes.index(1) if 1 in classes else -1
            return float(proba[idx]) if idx >= 0 else float(proba[-1])
        p = self.payload
        rows = _standardize_apply([row], p["means"], p["stds"])[0]
        return _predict_logreg(p["w"], p["b"], rows)

    # ---- Simpan / muat ----
    def save(self) -> str:
        if self.kind == "sklearn":
            with open(SKLEARN_PATH, "wb") as fh:
                pickle.dump(self.payload, fh)
            return SKLEARN_PATH
        with open(LOGREG_PATH, "w", encoding="utf-8") as fh:
            json.dump(self.payload, fh)
        return LOGREG_PATH

    @classmethod
    def load(cls) -> Optional["Model"]:
        if _HAS_SKLEARN and os.path.exists(SKLEARN_PATH):
            with open(SKLEARN_PATH, "rb") as fh:
                return cls("sklearn", pickle.load(fh))
        if os.path.exists(LOGREG_PATH):
            with open(LOGREG_PATH, "r", encoding="utf-8") as fh:
                return cls("logreg", json.load(fh))
        return None


def evaluate(model: "Model", X, y) -> dict:
    """Hitung akurasi + beberapa metrik pada data uji (yang belum dilatih)."""
    correct = tp = tn = fp = fn = 0
    for row, actual in zip(X, y):
        p = model.predict_proba_up(row)
        pred = 1 if p >= 0.5 else 0
        if pred == actual:
            correct += 1
        if pred == 1 and actual == 1:
            tp += 1
        elif pred == 0 and actual == 0:
            tn += 1
        elif pred == 1 and actual == 0:
            fp += 1
        else:
            fn += 1
    total = len(y) or 1
    return {
        "accuracy": correct / total,
        "n": total,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "up_rate_actual": sum(y) / total,
    }
