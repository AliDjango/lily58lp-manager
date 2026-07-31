import logging

from lily58lp_manager.logging_utils import RateLimitedWarnings


def test_rate_limited_warnings_emit_once_per_interval(caplog) -> None:
    warnings = RateLimitedWarnings(logging.getLogger("test"), interval_seconds=60)

    with caplog.at_level(logging.WARNING):
        warnings.warning("device", "Keyboard unavailable")
        warnings.warning("device", "Keyboard unavailable")

    assert caplog.messages == ["Keyboard unavailable"]
