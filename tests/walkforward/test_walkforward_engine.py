import pytest

from core.walkforward import (
    WalkForwardConfig,
    WalkForwardEngine,
    WalkForwardWindow,
    WalkForwardWindowGenerator,
)


def _engine(train_size=100, test_size=50, step_size=50) -> WalkForwardEngine:
    config = WalkForwardConfig(
        train_size=train_size, test_size=test_size, step_size=step_size
    )
    return WalkForwardEngine(WalkForwardWindowGenerator(config))


def test_no_windows():
    engine = _engine()
    summary = engine.run(data_length=10, runner=lambda w: None)
    assert summary.runs == []


def test_single_window():
    engine = _engine()
    summary = engine.run(data_length=150, runner=lambda w: "ok")
    assert len(summary.runs) == 1
    assert summary.runs[0].result == "ok"


def test_multiple_windows():
    engine = _engine()
    summary = engine.run(data_length=300, runner=lambda w: w.index)
    assert len(summary.runs) == 4


def test_callback_called_expected_count():
    call_count = 0

    def counter(window: WalkForwardWindow):
        nonlocal call_count
        call_count += 1
        return call_count

    engine = _engine()
    engine.run(data_length=300, runner=counter)
    assert call_count == 4


def test_callback_receives_correct_window():
    received: list[WalkForwardWindow] = []

    def capture(window: WalkForwardWindow):
        received.append(window)
        return None

    engine = _engine(train_size=100, test_size=50, step_size=50)
    engine.run(data_length=150, runner=capture)

    assert len(received) == 1
    w = received[0]
    assert w.train_start == 0
    assert w.train_end == 100
    assert w.test_start == 100
    assert w.test_end == 150


def test_preserves_result_order():
    engine = _engine()
    summary = engine.run(data_length=300, runner=lambda w: w.index * 10)
    results = [r.result for r in summary.runs]
    assert results == [0, 10, 20, 30]


def test_run_result_contains_correct_window():
    engine = _engine()
    summary = engine.run(data_length=150, runner=lambda w: "done")
    run = summary.runs[0]
    assert run.window.index == 0
    assert run.window.train_start == 0
    assert run.window.test_end == 150


def test_propagates_exceptions():
    def failing_runner(window: WalkForwardWindow):
        raise RuntimeError("runner failed")

    engine = _engine()
    with pytest.raises(RuntimeError, match="runner failed"):
        engine.run(data_length=150, runner=failing_runner)


def test_deterministic():
    engine = _engine()
    runner = lambda w: w.index
    summary_a = engine.run(data_length=300, runner=runner)
    summary_b = engine.run(data_length=300, runner=runner)

    assert len(summary_a.runs) == len(summary_b.runs)
    for a, b in zip(summary_a.runs, summary_b.runs):
        assert a.window == b.window
        assert a.result == b.result


def test_result_can_hold_any_type():
    engine = _engine()

    def dict_runner(window: WalkForwardWindow):
        return {"sharpe": 1.2, "max_dd": 0.08, "trades": 42}

    summary = engine.run(data_length=150, runner=dict_runner)
    assert summary.runs[0].result["sharpe"] == 1.2


def test_window_in_run_result_matches_generated_window():
    config = WalkForwardConfig(train_size=100, test_size=50, step_size=50)
    generator = WalkForwardWindowGenerator(config)
    engine = WalkForwardEngine(generator)

    expected_windows = generator.generate(300)
    summary = engine.run(data_length=300, runner=lambda w: None)

    for run, expected in zip(summary.runs, expected_windows):
        assert run.window == expected
