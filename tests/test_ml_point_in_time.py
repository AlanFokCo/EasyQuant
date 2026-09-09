"""Historical labels, features and model reuse must respect decision time."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import eqlib._state as state
from eqlib.data_cache import PreloadedData
from eqlib.ml.selection import MLSelector


@pytest.fixture
def history_session():
    old = state.get_session()
    session = state.BacktestSession()
    session._context = SimpleNamespace(current_dt=pd.Timestamp("2024-06-03 09:30"))
    preloaded = PreloadedData()
    dates = pd.bdate_range("2024-01-01", "2024-06-03")
    frames = {}
    for code, offset in [("A", 100), ("B", 200)]:
        prices = pd.Series(np.arange(len(dates)) + offset, index=dates, dtype=float)
        frames[code] = pd.DataFrame({"close": prices, "high": prices + 1,
                                     "low": prices - 1, "volume": 10000.0})
    preloaded._field_series = {code: {col: df[col] for col in df} for code, df in frames.items()}
    session._preloaded = preloaded
    state._set_session(session)
    yield session, frames
    state._set_session(old)


def labels():
    return pd.DataFrame([
        {"security": code, "date": date, "label": value, "available_at": available}
        for date, available in [("2024-05-20", "2024-05-27 15:01"),
                                ("2024-05-21", "2024-05-28 15:01"),
                                ("2024-06-03", "2024-06-10 15:01")]
        for code, value in [("A", -.2), ("B", .3)]
    ])


def selector(panel, **kwargs):
    return MLSelector(model="logistic_regression", target="forward_return_5d",
                      features=["last_close"],
                      custom_features={"last_close": lambda close, high, low, volume: close.iloc[-1]},
                      label_data=panel, top_n=1, **kwargs)


def test_unavailable_labels_cannot_change_predictions(history_session):
    session, frames = history_session
    panel = labels()
    first = selector(panel, train_end="2024-05-24")
    expected = first.rank(["A", "B"], session._context)
    assert first._is_trained and expected == ["B"]
    panel.loc[panel.date == "2024-06-03", "label"] = [10000, -10000]
    second = selector(panel, train_end="2024-05-24")
    assert second.rank(["A", "B"], session._context) == expected
    current = first.pipeline.compute(["A", "B"], session._context)
    np.testing.assert_allclose(first._model.predict(current), second._model.predict(current))


def test_historical_features_align_by_date_and_security(history_session):
    session, frames = history_session
    subject = selector(labels(), train_start="2024-05-20", train_end="2024-05-21")
    before = session._context.current_dt
    X, y = subject._build_training_set_from_labels(["A", "B"], session._context)
    assert len(X) == len(y) == 4
    assert X.index.is_unique and X.index.equals(y.index)
    for (date, code), row in X.iterrows():
        assert row.last_close == frames[code].loc[frames[code].index < date, "close"].iloc[-1]
    assert session._context.current_dt == before
    # Changing prices after both historical sample dates cannot rewrite X.
    for fields in session._preloaded._field_series.values():
        fields["close"].loc[fields["close"].index >= pd.Timestamp("2024-05-21")] = 99999
    again, _ = subject._build_training_set_from_labels(["A", "B"], session._context)
    pd.testing.assert_frame_equal(X, again)


def test_training_bounds_are_applied(history_session):
    session, _ = history_session
    subject = selector(labels(), train_start="2024-05-21", train_end="2024-05-21")
    X, _ = subject._build_training_set_from_labels(["A", "B"], session._context)
    assert len(X) == 2 and set(X.index.get_level_values("date")) == {pd.Timestamp("2024-05-21")}
    with pytest.raises(ValueError, match="train_start"):
        selector(labels(), train_start="2024-06-01", train_end="2024-05-01")


def test_labels_need_explicit_availability(history_session):
    session, _ = history_session
    with pytest.raises(ValueError, match="available_at"):
        selector(labels().drop(columns="available_at")).train(["A", "B"], session._context)


@pytest.mark.parametrize("availability,expected_rows", [
    ("2024-06-03", 0), ("2024-06-03 09:30", 0),
    ("2024-06-03 09:29", 2), ("2024-06-03T01:29:00Z", 2),
])
def test_availability_instant_is_strict_and_date_only_is_conservative(history_session, availability, expected_rows):
    session, _ = history_session
    panel = labels().iloc[:2].copy()
    panel["available_at"] = availability
    X, _ = selector(panel)._build_training_set_from_labels(["A", "B"], session._context)
    assert (0 if X is None else len(X)) == expected_rows


def test_duplicate_samples_are_rejected(history_session):
    session, _ = history_session
    panel = pd.concat([labels(), labels().iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        selector(panel).train(["A", "B"], session._context)


def test_rewinding_selector_does_not_keep_future_model(history_session):
    session, _ = history_session
    subject = selector(labels())
    subject.train(["A", "B"], session._context)
    assert subject._is_trained
    session._context.current_dt = pd.Timestamp("2024-05-22 09:30")
    subject.rank(["A", "B"], session._context)
    assert not subject._is_trained  # neither forward label has matured yet


def test_simple_training_respects_train_end(history_session):
    session, frames = history_session
    subject = MLSelector(features=["momentum"], train_end="2024-05-20")
    X, y = subject._build_training_set_simple(["A"], session._context)
    close = frames["A"].loc[frames["A"].index < pd.Timestamp("2024-05-20"), "close"]
    assert X.loc["A", "momentum"] == pytest.approx(close.iloc[-1] / close.iloc[-21] - 1)
    assert y.loc["A"] == pytest.approx(close.iloc[-1] / close.iloc[-6] - 1)
