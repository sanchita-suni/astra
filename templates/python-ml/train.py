"""Minimum-viable training loop.

Replace with your model. The point of this file is to give you something that
runs end-to-end on day 1 — random data in, dummy classifier out, accuracy
printed. From here you swap in real data and a real model.
"""

from __future__ import annotations

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


def main() -> None:
    rng = np.random.default_rng(seed=42)
    X = rng.standard_normal((200, 4))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42
    )

    model = DummyClassifier(strategy="most_frequent")
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    print(f"baseline accuracy: {accuracy_score(y_test, preds):.3f}")


if __name__ == "__main__":
    main()
