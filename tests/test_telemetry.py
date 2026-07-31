import struct

from lily58lp_manager.telemetry import (
    REPORT_FORMAT,
    TELEMETRY_PAYLOAD_LENGTH,
    pack_metrics,
    room_temperature,
)


def test_pack_metrics_is_fixed_size_and_clamps_values() -> None:
    payload = pack_metrics(-1, 999, 999999, -1, -50, 999999)

    assert len(payload) == TELEMETRY_PAYLOAD_LENGTH == 16
    assert struct.unpack(REPORT_FORMAT, payload) == (
        0,
        255,
        0,
        0,
        65535,
        0,
        0,
        0,
        0,
        65535,
    )


def test_room_temperature_skips_network_when_not_configured(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("HTTP must not be called when sensors are disabled")

    monkeypatch.setattr("lily58lp_manager.telemetry.requests.get", fail_if_called)

    assert room_temperature(None, "temperature", 2) == 0
