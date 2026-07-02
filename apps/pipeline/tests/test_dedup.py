import time
from drishtiai_pipeline.dedup import PlateDeduplicator


def test_first_read_is_new() -> None:
    d = PlateDeduplicator(window_seconds=5)
    assert d.is_new("BA1PA1234") is True


def test_repeat_within_window_is_not_new() -> None:
    d = PlateDeduplicator(window_seconds=5)
    d.is_new("BA1PA1234")
    assert d.is_new("BA1PA1234") is False


def test_different_plates_are_both_new() -> None:
    d = PlateDeduplicator(window_seconds=5)
    assert d.is_new("BA1PA1234") is True
    assert d.is_new("GA1JA9999") is True


def test_plate_after_window_is_new_again() -> None:
    d = PlateDeduplicator(window_seconds=1)
    d.is_new("BA1PA1234")
    time.sleep(1.1)
    assert d.is_new("BA1PA1234") is True
