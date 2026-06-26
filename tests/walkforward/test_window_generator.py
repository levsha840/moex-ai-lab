import pytest

from core.walkforward import WalkForwardConfig, WalkForwardWindow, WalkForwardWindowGenerator


def _gen(train_size=100, test_size=50, step_size=50, min_train_size=None):
    return WalkForwardWindowGenerator(
        WalkForwardConfig(
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            min_train_size=min_train_size,
        )
    )


def test_single_window():
    # data_length=150: train=[0,100), test=[100,150) — exactly fits
    windows = _gen().generate(150)
    assert len(windows) == 1
    w = windows[0]
    assert w.index == 0
    assert w.train_start == 0
    assert w.train_end == 100
    assert w.test_start == 100
    assert w.test_end == 150


def test_multiple_windows():
    # data_length=300, step=50: windows at start 0,50,100,150
    windows = _gen().generate(300)
    assert len(windows) == 4
    assert windows[0].train_start == 0
    assert windows[1].train_start == 50
    assert windows[2].train_start == 100
    assert windows[3].train_start == 150
    # last window: test_end=150+100+50=300 <= 300 ✓
    assert windows[3].test_end == 300


def test_insufficient_data_returns_empty_list():
    # need 150 (100+50), only have 100
    windows = _gen().generate(100)
    assert windows == []


def test_exact_boundary():
    # test_end == data_length is still valid (half-open: [start, end))
    windows = _gen(train_size=80, test_size=20, step_size=20).generate(100)
    assert len(windows) >= 1
    assert windows[0].test_end == 100


def test_step_size_greater_than_test_size():
    # step=70 > test=30: windows skip ahead faster than test periods
    windows = _gen(train_size=100, test_size=30, step_size=70).generate(300)
    # start=0: test_end=130 ✓; start=70: test_end=200 ✓; start=140: test_end=270 ✓
    # start=210: test_end=340 > 300 ✗
    assert len(windows) == 3
    assert windows[0].test_end == 130
    assert windows[1].test_end == 200
    assert windows[2].test_end == 270


def test_invalid_train_size():
    with pytest.raises(ValueError, match="train_size"):
        WalkForwardConfig(train_size=0, test_size=50, step_size=50)


def test_invalid_test_size():
    with pytest.raises(ValueError, match="test_size"):
        WalkForwardConfig(train_size=100, test_size=0, step_size=50)


def test_invalid_step_size():
    with pytest.raises(ValueError, match="step_size"):
        WalkForwardConfig(train_size=100, test_size=50, step_size=0)


def test_invalid_min_train_size_zero():
    with pytest.raises(ValueError, match="min_train_size"):
        WalkForwardConfig(train_size=100, test_size=50, step_size=50, min_train_size=0)


def test_invalid_min_train_size_exceeds_train_size():
    with pytest.raises(ValueError, match="min_train_size"):
        WalkForwardConfig(train_size=100, test_size=50, step_size=50, min_train_size=101)


def test_negative_data_length():
    gen = _gen()
    with pytest.raises(ValueError, match="data_length"):
        gen.generate(-1)


def test_deterministic_same_config_same_output():
    gen = _gen()
    result_a = gen.generate(350)
    result_b = gen.generate(350)
    assert result_a == result_b


def test_window_indexes_are_sequential():
    windows = _gen().generate(400)
    for expected, w in enumerate(windows):
        assert w.index == expected


def test_zero_data_length_returns_empty():
    windows = _gen().generate(0)
    assert windows == []


def test_valid_min_train_size_accepted():
    # min_train_size must be accepted when 0 < min <= train_size
    config = WalkForwardConfig(
        train_size=100, test_size=50, step_size=50, min_train_size=60
    )
    assert config.min_train_size == 60


def test_window_intervals_are_contiguous():
    # train_end == test_start for every window
    windows = _gen().generate(400)
    for w in windows:
        assert w.train_end == w.test_start


def test_windows_do_not_exceed_data_length():
    data_length = 275
    windows = _gen().generate(data_length)
    for w in windows:
        assert w.test_end <= data_length
