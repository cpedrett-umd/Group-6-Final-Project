"""Non-neural baselines for the persuasion-tactic classifier.

Trains and evaluates two reference models on the exact split used by
train_hyperopt.py (stratified 70/15/15, seed 42, ads_dataset_merged.csv):

  1. Majority class  — always predicts the most frequent label (Urgency).
  2. TF-IDF + LogReg — word 1-2 grams, class-balanced logistic regression.

These give the "baseline for comparison" context for the tuned DistilBERT's
held-out numbers (accuracy 0.9285, macro F1 0.9191). Run from anywhere:

    python modeling/train_baselines.py
"""

import os

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

SEED = 42
DATA = os.path.join(os.path.dirname(__file__), "..", "datasets",
                    "text_processing", "ads_dataset_merged.csv")


def load_split():
    """Reproduce train_hyperopt.py's stratified 70/15/15 split."""
    df = pd.read_csv(DATA)
    texts, labels = df["ad_text"].tolist(), df["label"].tolist()
    x_train, x_tmp, y_train, y_tmp = train_test_split(
        texts, labels, test_size=0.30, stratify=labels, random_state=SEED)
    x_val, x_test, y_val, y_test = train_test_split(
        x_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=SEED)
    return x_train, y_train, x_val, y_val, x_test, y_test


def report(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    macro = f1_score(y_true, y_pred, average="macro")
    print(f"{name:<18} accuracy {acc:.4f}   macro F1 {macro:.4f}")


def main():
    x_train, y_train, _, _, x_test, y_test = load_split()
    print(f"train {len(x_train)}, test {len(x_test)}")

    majority = DummyClassifier(strategy="most_frequent").fit(x_train, y_train)
    report("Majority class", y_test, majority.predict(x_test))

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    features = vectorizer.fit_transform(x_train)
    logreg = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0)
    logreg.fit(features, y_train)
    report("TF-IDF + LogReg", y_test, logreg.predict(vectorizer.transform(x_test)))


if __name__ == "__main__":
    main()
