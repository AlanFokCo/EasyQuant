"""Tests for eqlib.ml.models module."""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os


class TestBaseMLModel:
    def _make_data(self, n=100, n_features=5, seed=42):
        np.random.seed(seed)
        X = pd.DataFrame(
            np.random.randn(n, n_features),
            columns=[f"feat_{i}" for i in range(n_features)],
        )
        y = pd.Series(np.random.choice([0, 1], size=n))
        return X, y

    def test_init_random_forest(self):
        from eqlib.ml.models import BaseMLModel

        model = BaseMLModel("random_forest")
        assert model.model_type == "random_forest"
        assert model._model is not None

    def test_init_logistic_regression(self):
        from eqlib.ml.models import BaseMLModel

        model = BaseMLModel("logistic_regression")
        assert model.model_type == "logistic_regression"
        assert model._model is not None

    def test_init_gradient_boosting(self):
        from eqlib.ml.models import BaseMLModel

        model = BaseMLModel("gradient_boosting")
        assert model.model_type == "gradient_boosting"
        assert model._model is not None

    def test_init_unsupported(self):
        from eqlib.ml.models import BaseMLModel

        with pytest.raises(ValueError, match="Unsupported model_type"):
            BaseMLModel("unsupported_model")

    def test_fit_predict(self):
        from eqlib.ml.models import BaseMLModel

        X, y = self._make_data(n=100)
        model = BaseMLModel("random_forest")
        model.fit(X, y)
        preds = model.predict(X)
        assert len(preds) == len(X)
        assert all(0 <= p <= 1 for p in preds)

    def test_predict_proba(self):
        from eqlib.ml.models import BaseMLModel

        X, y = self._make_data(n=100)
        model = BaseMLModel("random_forest")
        model.fit(X, y)
        proba = model.predict_proba(X)
        assert proba.shape == (len(X), 2)
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_feature_importances(self):
        from eqlib.ml.models import BaseMLModel

        X, y = self._make_data(n=100)
        model = BaseMLModel("random_forest")
        model.fit(X, y)
        importances = model.feature_importances()
        assert len(importances) == X.shape[1]
        assert all(importances >= 0)
        assert abs(importances.sum() - 1.0) < 1e-6

    def test_save_load(self):
        from eqlib.ml.models import BaseMLModel

        X, y = self._make_data(n=100)
        model = BaseMLModel("random_forest")
        model.fit(X, y)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name

        try:
            model.save(path)
            loaded = BaseMLModel.load(path)
            assert loaded.model_type == model.model_type
            preds1 = model.predict(X)
            preds2 = loaded.predict(X)
            np.testing.assert_allclose(preds1, preds2, rtol=1e-5)
        finally:
            os.unlink(path)

    def test_logistic_regression_coef_importance(self):
        from eqlib.ml.models import BaseMLModel

        X, y = self._make_data(n=100)
        model = BaseMLModel("logistic_regression")
        model.fit(X, y)
        importances = model.feature_importances()
        assert len(importances) == X.shape[1]

    def test_fit_aligns_labels_by_index_not_position(self):
        from eqlib.ml.models import BaseMLModel

        X = pd.DataFrame({"x": [1.0, 2.0, 3.0]}, index=["a", "b", "c"])
        y = pd.Series([7.0, 5.0, 3.0], index=["c", "b", "a"])
        model = BaseMLModel("logistic_regression", is_classifier=False)

        model.fit(X, y)

        assert model.predict(pd.DataFrame({"x": [4.0]}))[0] == pytest.approx(9.0)

    def test_classifier_returns_zero_positive_probability_when_class_one_is_absent(
        self,
    ):
        from eqlib.ml.models import BaseMLModel

        X = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
        model = BaseMLModel("random_forest", n_estimators=10)
        model.fit(X, pd.Series([0, 0, 0, 0]))

        assert np.all(model.predict(X) == 0.0)

    def test_prediction_of_missing_row_is_independent_of_other_prediction_rows(self):
        from eqlib.ml.models import BaseMLModel

        X = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0], "z": [1.0, 2.0, 3.0, 4.0]})
        model = BaseMLModel("logistic_regression")
        model.fit(X, pd.Series([0, 0, 1, 1]))

        one = model.predict(pd.DataFrame({"x": [np.nan], "z": [2.0]}))[0]
        together = model.predict(
            pd.DataFrame({"x": [np.nan, 1000.0], "z": [2.0, 2.0]})
        )[0]

        assert one == pytest.approx(together)
